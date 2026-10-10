"""
Attendance: the 05:00 PM → 09:20 AM Check-In window (server time, IST), check-out at any time for an open record,
separate permissions, office hours and approved permission, weekly / office holidays, the dashboard, employees,
leave / permission requests, calendar, reports and settings. TEST records only; the clock is fixed.
(October 2026: the 4th and 11th are Sundays.)
"""
from datetime import date, datetime, time
from unittest import mock

from django.test import TestCase
from rest_framework.test import APIClient

from apps.attendance import permissions as perms
from apps.attendance import window
from apps.attendance.models import AttendanceRecord, AttendanceSettings, Employee, LeaveRequest, OfficeHoliday

from .helpers import API, client_for, make_user

IST = window.IST


def at(y, m, d, hh, mm):
    return datetime(y, m, d, hh, mm, tzinfo=IST)


class WindowLoopTests(TestCase):
    """The PDF's examples, in order (one continuous overnight window filed under the day it opened)."""

    def test_loop(self):
        s = AttendanceSettings.load()
        cases = [((16, 59), False), ((17, 0), True), ((20, 0), True), ((23, 59), True), ((0, 0), True), ((6, 0), True),
                 ((9, 19), True), ((9, 20), False), ((10, 0), False), ((16, 59), False), ((17, 0), True)]
        for (hh, mm), is_open in cases:
            self.assertEqual(window.state(at(2026, 10, 8, hh, mm), s).is_open, is_open, f"{hh:02d}:{mm:02d}")

    def test_check_in_day_and_check_out_deadline(self):
        s = AttendanceSettings.load()
        evening = window.state(at(2026, 10, 8, 17, 0), s)  # from 05:00 PM a check-in counts for tomorrow
        self.assertEqual(evening.checkin_date, date(2026, 10, 9))
        morning = window.state(at(2026, 10, 9, 8, 55), s)  # until 09:20 AM: this morning's work day
        self.assertEqual((morning.checkin_date, morning.closes_at), (date(2026, 10, 9), at(2026, 10, 9, 9, 20)))
        closed = window.state(at(2026, 10, 9, 12, 0), s)
        self.assertEqual((closed.checkin_date, closed.opens_at), (None, at(2026, 10, 9, 17, 0)))
        self.assertEqual(window.finished_date(closed), date(2026, 10, 9))  # no check-in by 09:20 = absent today
        self.assertEqual(closed.checkout_deadline(date(2026, 10, 9)), at(2026, 10, 10, 9, 20))  # check-out until next morning
        self.assertEqual(window.closed_message(closed), "Check-In is closed. It opens again at 5:00 PM.")

    def test_browser_time_never_matters(self):
        """The server decides: the same request is accepted or refused only by the server clock."""
        with mock.patch("apps.attendance.window.now", return_value=at(2026, 10, 8, 12, 0)):
            self.assertFalse(window.state().is_open)


class AttendanceBase(TestCase):
    def setUp(self):
        self.admin = make_user("admin")
        self.admin_api = client_for(self.admin)

    def employee(self, user=None, code="TEST-001", **extra):
        return Employee.objects.create(employee_code=code, name=f"TEST {code}", department="Production", user=user,
                                       joining_date=date(2026, 9, 1), **extra)

    def worker(self, *codes, username="worker"):
        user = make_user("sales", username=username)
        perms.set_granted(user, codes)
        self.employee(user=user, code=f"TEST-{username}")
        return user, client_for(user)

    def clock(self, value):
        patcher = mock.patch("apps.attendance.window.now", return_value=value)
        patcher.start()
        self.addCleanup(patcher.stop)


class CheckInOutTests(AttendanceBase):
    def test_morning_check_in_and_evening_check_out_make_one_work_day(self):
        _user, api = self.worker("check_in", "check_out")
        self.clock(at(2026, 10, 8, 8, 50))
        res = api.post(f"{API}/attendance/check-in/", {"check_in_at": "2020-01-01T00:00:00"}, format="json")  # ignored
        self.assertEqual(res.status_code, 201, res.data)
        self.assertTrue(res.data["record"]["check_in_at"].startswith("2026-10-08T08:50"))
        self.assertEqual((res.data["work_date"], res.data["can_check_in"], res.data["can_check_out"]), (date(2026, 10, 8), False, True))  # can check out at any time
        self.assertEqual(api.post(f"{API}/attendance/check-in/").status_code, 400)  # once per work day
        self.clock(at(2026, 10, 8, 12, 0))  # Check-In closed; check-out still possible
        status = api.get(f"{API}/attendance/status/").data
        self.assertEqual((status["record"]["status"], status["can_check_in"], status["can_check_out"]), ("Checked in", False, True))
        self.assertEqual((status["scheduled_duration"], status["office_hours"]), ("08h 30m", "9:00 AM – 5:30 PM"))
        self.clock(at(2026, 10, 8, 17, 20))
        self.assertTrue(api.get(f"{API}/attendance/status/").data["can_check_out"])
        res = api.post(f"{API}/attendance/check-out/")
        self.assertEqual(res.status_code, 200, res.data)
        r = res.data["record"]
        self.assertEqual((r["attendance_date"], r["scheduled_duration"], r["total_duration"], r["permission_duration"],
                          r["working_duration"], r["status"]),
                         (date(2026, 10, 8), "08h 30m", "08h 30m", "00h 00m", "08h 30m", "Attendance completed"))
        self.assertEqual(api.post(f"{API}/attendance/check-out/").status_code, 400)
        self.assertEqual(AttendanceRecord.objects.count(), 1)

    def test_late_check_out_after_midnight_still_ends_that_day(self):
        _user, api = self.worker("check_in", "check_out")
        self.clock(at(2026, 10, 8, 9, 0))
        api.post(f"{API}/attendance/check-in/")
        self.clock(at(2026, 10, 9, 1, 0))
        self.assertEqual(api.post(f"{API}/attendance/check-out/").status_code, 200)
        self.assertEqual(AttendanceRecord.objects.get().attendance_date, date(2026, 10, 8))

    def test_check_in_times(self):
        """09:19 AM allowed, 09:20 AM and 04:59 PM rejected, 05:00 PM allowed (for the next work day)."""
        _user, api = self.worker("check_in", "check_out")
        expected = [((9, 19), 201), ((9, 20), 400), ((10, 0), 400), ((16, 59), 400), ((17, 0), 201)]
        for (hh, mm), code in expected:
            self.clock(at(2026, 10, 8, hh, mm))
            res = api.post(f"{API}/attendance/check-in/")
            self.assertEqual(res.status_code, code, f"{hh:02d}:{mm:02d}")
            if code == 400:
                self.assertEqual(res.data["detail"], "Check-In is closed. It opens again at 5:00 PM.")
                status = api.get(f"{API}/attendance/status/").data
                self.assertEqual((status["window"]["is_open"], status["can_check_in"]), (False, False))
        self.assertEqual(sorted(AttendanceRecord.objects.values_list("attendance_date", flat=True)),
                         [date(2026, 10, 8), date(2026, 10, 9)])

    def test_check_out_after_9_20_is_allowed(self):
        _user, api = self.worker("check_in", "check_out")
        self.clock(at(2026, 10, 8, 9, 10))
        api.post(f"{API}/attendance/check-in/")
        self.clock(at(2026, 10, 8, 9, 25))
        res = api.post(f"{API}/attendance/check-out/")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["record"]["total_duration"], "00h 15m")

    def test_evening_check_in_can_be_checked_out_the_next_day(self):
        _user, api = self.worker("check_in", "check_out")
        self.clock(at(2026, 10, 8, 18, 0))
        api.post(f"{API}/attendance/check-in/")
        self.clock(at(2026, 10, 9, 14, 0))  # Check-In closed, the record is still open
        self.assertTrue(api.get(f"{API}/attendance/status/").data["can_check_out"])
        self.assertEqual(api.post(f"{API}/attendance/check-out/").status_code, 200)
        self.assertEqual(AttendanceRecord.objects.get().attendance_date, date(2026, 10, 9))

    def test_nobody_is_checked_out_automatically(self):
        _user, api = self.worker("check_in", "check_out")
        self.clock(at(2026, 10, 8, 9, 0))
        api.post(f"{API}/attendance/check-in/")
        self.clock(at(2026, 10, 9, 12, 0))
        api.get(f"{API}/attendance/status/")
        self.assertIsNone(AttendanceRecord.objects.get().check_out_at)

    def test_evening_check_in_counts_for_the_next_work_day(self):
        _user, api = self.worker("check_in")
        self.clock(at(2026, 10, 8, 18, 0))
        self.assertEqual(api.get(f"{API}/attendance/status/").data["check_in_for"], date(2026, 10, 9))
        self.assertEqual(api.post(f"{API}/attendance/check-in/").status_code, 201)
        self.assertEqual(AttendanceRecord.objects.get().attendance_date, date(2026, 10, 9))

    def test_every_active_employee_checks_in_and_out_without_permissions(self):
        """No Check-In / Check-Out permission has to be given: signing in as an active employee is enough."""
        user, api = self.worker(username="plain")  # no Attendance permissions at all
        self.assertEqual(perms.granted(user), [])
        self.clock(at(2026, 10, 8, 8, 30))
        status = api.get(f"{API}/attendance/status/").data
        self.assertEqual((status["can_check_in"], status["can_check_out"]), (True, False))
        self.assertEqual(api.post(f"{API}/attendance/check-in/").status_code, 201)
        self.assertEqual(api.post(f"{API}/attendance/check-in/").status_code, 400)  # duplicate check-in
        self.assertTrue(api.get(f"{API}/attendance/status/").data["can_check_out"])
        self.clock(at(2026, 10, 8, 18, 0))  # open window: check out
        self.assertEqual(api.post(f"{API}/attendance/check-out/").status_code, 200)
        self.assertEqual(api.post(f"{API}/attendance/check-out/").status_code, 400)  # duplicate check-out
        self.assertEqual(AttendanceRecord.objects.count(), 1)

    def test_check_out_after_9_20_without_permissions(self):
        _user, api = self.worker(username="plain")
        self.clock(at(2026, 10, 8, 9, 12))
        api.post(f"{API}/attendance/check-in/")
        self.clock(at(2026, 10, 8, 9, 36))  # Check-In closed; the open record can still be checked out
        status = api.get(f"{API}/attendance/status/").data
        self.assertEqual((status["window"]["is_open"], status["can_check_out"]), (False, True))
        self.assertEqual(api.post(f"{API}/attendance/check-out/").status_code, 200)
        self.assertEqual(api.post(f"{API}/attendance/check-in/").status_code, 400)  # Check-In stays closed

    def test_no_open_record_means_no_check_out(self):
        _user, api = self.worker(username="plain")
        self.clock(at(2026, 10, 8, 12, 0))
        self.assertFalse(api.get(f"{API}/attendance/status/").data["can_check_out"])
        res = api.post(f"{API}/attendance/check-out/")
        self.assertEqual((res.status_code, res.data["detail"]), (400, "You have no open check-in to check out."))

    def test_nobody_can_check_out_another_employees_record(self):
        _a, api_a = self.worker(username="a")
        b, _api_b = self.worker(username="b")
        rec = AttendanceRecord.objects.create(employee=b.employee, attendance_date=date(2026, 10, 8), check_in_at=at(2026, 10, 8, 9, 0))
        self.clock(at(2026, 10, 8, 17, 30))
        res = api_a.post(f"{API}/attendance/check-out/", {"record_id": rec.id, "employee_id": b.employee.id}, format="json")
        self.assertEqual(res.status_code, 400)  # A has no open record; the request body is ignored
        rec.refresh_from_db()
        self.assertIsNone(rec.check_out_at)

    def test_anonymous_and_inactive_employees_are_refused(self):
        self.clock(at(2026, 10, 8, 8, 30))
        anonymous = APIClient()
        self.assertEqual(anonymous.post(f"{API}/attendance/check-in/").status_code, 401)
        self.assertEqual(anonymous.post(f"{API}/attendance/check-out/").status_code, 401)
        user, api = self.worker(username="left")
        AttendanceRecord.objects.create(employee=user.employee, attendance_date=date(2026, 10, 8), check_in_at=at(2026, 10, 8, 8, 0))
        Employee.objects.filter(pk=user.employee.pk).update(status=Employee.Status.INACTIVE)
        for action in ("check-in", "check-out"):
            res = api.post(f"{API}/attendance/{action}/")
            self.assertEqual(res.status_code, 400, action)
            self.assertIn("isn't linked to an active employee", res.data["detail"])
        self.assertIsNone(AttendanceRecord.objects.get().check_out_at)
        status = api.get(f"{API}/attendance/status/").data
        self.assertEqual((status["can_check_in"], status["can_check_out"]), (False, False))

    def test_other_attendance_permissions_are_still_enforced(self):
        _user, api = self.worker(username="plain")
        for url in ("dashboard/", "employees/", "reports/?type=daily", "settings/", "leave/?scope=all"):
            self.assertEqual(api.get(f"{API}/attendance/{url}").status_code, 403, url)
        self.assertEqual(api.post(f"{API}/attendance/holidays/", {"name": "TEST", "date": "2026-11-11"}, format="json").status_code, 403)

    def test_login_without_an_employee_is_told_so(self):
        user = make_user("sales", username="nolink")
        perms.set_granted(user, ["check_in"])
        self.clock(at(2026, 10, 8, 8, 0))
        res = client_for(user).post(f"{API}/attendance/check-in/")
        self.assertEqual(res.status_code, 400)
        self.assertIn("isn't linked to an active employee", res.data["detail"])

    def test_not_checked_out_once_the_check_out_time_is_over(self):
        _user, api = self.worker("check_in", "check_out")
        self.clock(at(2026, 10, 8, 8, 0))
        api.post(f"{API}/attendance/check-in/")
        self.clock(at(2026, 10, 9, 10, 0))
        res = api.post(f"{API}/attendance/check-out/")
        self.assertEqual((res.status_code, res.data["detail"]), (400, "You have no open check-in to check out."))
        self.assertEqual(api.get(f"{API}/attendance/history/").data["results"][0]["status"], "Not checked out")

    def test_super_admin_has_every_permission(self):
        self.employee(user=self.admin, code="TEST-ADM")
        self.clock(at(2026, 10, 8, 8, 0))
        self.assertEqual(self.admin_api.post(f"{API}/attendance/check-in/").status_code, 201)


class WorkingHoursTests(AttendanceBase):
    """Actual working hours = check-in -> check-out minus the APPROVED permission inside it and inside office hours."""

    def setUp(self):
        super().setUp()
        self.user, self.api = self.worker("check_in", "check_out")
        self.emp = self.user.employee
        self.record = AttendanceRecord.objects.create(employee=self.emp, attendance_date=date(2026, 10, 8), status="completed",
                                                      check_in_at=at(2026, 10, 8, 9, 0), check_out_at=at(2026, 10, 8, 17, 30))
        self.clock(at(2026, 10, 9, 12, 0))

    def permission(self, start, end, status="approved"):
        return LeaveRequest.objects.create(employee=self.emp, type="permission", date=date(2026, 10, 8), from_time=start,
                                           to_time=end, reason="TEST", status=status)

    def row(self):
        return self.api.get(f"{API}/attendance/history/").data["results"][0]

    def test_only_approved_permission_is_deducted(self):
        self.permission(time(11), time(12))
        for st in ("pending", "rejected", "cancelled"):
            self.permission(time(14), time(16), status=st)
        r = self.row()
        self.assertEqual((r["total_duration"], r["permission_duration"], r["working_duration"]), ("08h 30m", "01h 00m", "07h 30m"))

    def test_the_requirement_example(self):
        """Office 9:00 AM – 5:30 PM, permission 4:30 – 5:30 PM: 7h 30m."""
        self.permission(time(16, 30), time(17, 30))
        r = self.row()
        self.assertEqual((r["scheduled_duration"], r["permission_duration"], r["working_duration"]), ("08h 30m", "01h 00m", "07h 30m"))

    def test_permission_outside_office_hours_is_not_deducted(self):
        self.record.check_in_at, self.record.check_out_at = at(2026, 10, 8, 8, 0), at(2026, 10, 8, 18, 30)
        self.record.save()
        self.permission(time(8), time(9))  # before office hours
        self.permission(time(17), time(18))  # only 5:00 – 5:30 PM is inside office hours
        r = self.row()
        self.assertEqual((r["total_duration"], r["permission_duration"], r["working_duration"]), ("10h 30m", "00h 30m", "10h 00m"))

    def test_office_hours_come_from_settings(self):
        AttendanceSettings.objects.update_or_create(pk=1, defaults={"work_start": time(10), "work_end": time(17)})
        self.permission(time(9), time(11))  # 10:00 – 11:00 is inside the new office hours
        r = self.row()
        self.assertEqual((r["scheduled_duration"], r["permission_duration"]), ("07h 00m", "01h 00m"))

    def test_only_the_part_inside_attendance_counts_and_overlaps_count_once(self):
        self.permission(time(8), time(10))  # 1 h inside (09:00-10:00)
        self.permission(time(9, 30), time(10, 30))  # overlaps: adds 30 min
        self.permission(time(18), time(19))  # after check-out: nothing
        r = self.row()
        self.assertEqual((r["permission_duration"], r["working_duration"]), ("01h 30m", "07h 00m"))

    def test_approval_later_updates_the_figures_and_reports(self):
        lr = self.permission(time(11), time(12), status="pending")
        self.assertEqual(self.row()["working_duration"], "08h 30m")
        approver = client_for(make_user("admin", username="boss2"))
        approver.post(f"{API}/attendance/leave/{lr.id}/approve/")
        self.assertEqual(self.row()["working_duration"], "07h 30m")
        q = "date_from=2026-10-08&date_to=2026-10-08"
        daily = approver.get(f"{API}/attendance/reports/?type=daily&{q}").data["table"]["rows"][0]
        self.assertEqual((daily["total"], daily["permission"], daily["working"]), ("08h 30m", "01h 00m", "07h 30m"))
        monthly = approver.get(f"{API}/attendance/reports/?type=monthly&{q}").data["table"]["rows"][0]
        self.assertEqual((monthly["permission_hours"], monthly["hours"]), ("01h 00m", "07h 30m"))
        days = self.api.get(f"{API}/attendance/calendar/?month=2026-10").data["days"]
        self.assertEqual([d["working_duration"] for d in days if d["date"] == date(2026, 10, 8)], ["07h 30m"])

    def test_figures_wait_for_check_out(self):
        self.record.check_out_at = None
        self.record.status = "checked_in"
        self.record.save()
        r = self.row()
        self.assertEqual((r["total_duration"], r["working_duration"]), (None, None))


class EmployeeTests(AttendanceBase):
    def test_add_view_edit_delete_keeps_history(self):
        login = make_user("sales", username="ravi")
        res = self.admin_api.post(f"{API}/attendance/employees/", {
            "employee_code": "TEST-100", "name": "TEST Ravi", "department": "Packing", "designation": "Operator",
            "email": "RAVI@test.invalid", "phone": "98765 43210", "joining_date": "2026-09-15", "user_id": login.id}, format="json")
        self.assertEqual(res.status_code, 201, res.data)
        emp_id = res.data["id"]
        self.assertEqual((res.data["email"], res.data["status"], res.data["user"]["id"]), ("ravi@test.invalid", "Active", login.id))
        self.assertEqual(self.admin_api.get(f"{API}/attendance/employees/{emp_id}/").data["designation"], "Operator")
        res = self.admin_api.patch(f"{API}/attendance/employees/{emp_id}/", {"designation": "Supervisor"}, format="json")
        self.assertEqual(res.data["designation"], "Supervisor")
        dup = self.admin_api.post(f"{API}/attendance/employees/", {"employee_code": "test-100", "name": "x", "user_id": login.id}, format="json")
        self.assertEqual(set(dup.data), {"employee_code", "user_id"})

        AttendanceRecord.objects.create(employee_id=emp_id, attendance_date=date(2026, 10, 1), check_in_at=at(2026, 10, 1, 18, 0))
        self.assertEqual(self.admin_api.delete(f"{API}/attendance/employees/{emp_id}/").status_code, 204)
        self.assertEqual(self.admin_api.get(f"{API}/attendance/employees/").data["count"], 0)
        self.assertEqual(AttendanceRecord.objects.count(), 1)  # history kept
        e = Employee.objects.get(pk=emp_id)
        self.assertIsNotNone(e.deleted_at)
        self.assertIsNone(e.user_id)  # the login can no longer check in as this employee
        again = self.admin_api.post(f"{API}/attendance/employees/", {"employee_code": "TEST-100", "name": "TEST New"}, format="json")
        self.assertEqual(again.status_code, 201)  # the ID can be reused after deletion

    def test_no_employees_and_permission(self):
        self.assertEqual(self.admin_api.get(f"{API}/attendance/employees/").data["count"], 0)
        _user, api = self.worker("check_in")
        self.assertEqual(api.get(f"{API}/attendance/employees/").status_code, 403)
        self.assertEqual(api.post(f"{API}/attendance/employees/", {}, format="json").status_code, 403)
        _viewer, viewer = self.worker("employee_view", username="viewer")
        self.assertEqual(viewer.get(f"{API}/attendance/employees/").data["count"], 2)
        self.assertEqual(viewer.post(f"{API}/attendance/employees/", {"employee_code": "TEST-9", "name": "TEST"},
                                     format="json").status_code, 403)


class LeaveTests(AttendanceBase):
    def test_apply_view_own_approve_reject_cancel(self):
        _user, api = self.worker("leave_apply")
        leave = api.post(f"{API}/attendance/leave/", {"type": "leave", "date": "2026-10-12", "reason": "TEST family function"}, format="json")
        self.assertEqual(leave.status_code, 201, leave.data)
        self.assertEqual((leave.data["status"], leave.data["from_time"]), ("Pending", None))
        err = api.post(f"{API}/attendance/leave/", {"type": "permission", "date": "2026-10-13", "reason": "TEST"}, format="json")
        self.assertEqual(set(err.data), {"from_time", "to_time"})  # a permission needs its times
        bad = api.post(f"{API}/attendance/leave/", {"type": "permission", "date": "2026-10-13", "from_time": "12:00",
                                                    "to_time": "10:00", "reason": "TEST"}, format="json")
        self.assertIn("to_time", bad.data)
        perm = api.post(f"{API}/attendance/leave/", {"type": "permission", "date": "2026-10-13", "from_time": "10:00",
                                                     "to_time": "12:00", "reason": "TEST personal work", "remarks": "TEST"}, format="json")
        self.assertEqual(perm.status_code, 201)
        self.assertEqual(api.get(f"{API}/attendance/leave/").data["count"], 2)  # own requests
        self.assertEqual(api.get(f"{API}/attendance/leave/?scope=all").status_code, 403)
        self.assertEqual(api.post(f"{API}/attendance/leave/{leave.data['id']}/approve/").status_code, 403)

        edited = api.patch(f"{API}/attendance/leave/{perm.data['id']}/", {"to_time": "12:30"}, format="json")
        self.assertEqual(edited.data["to_time"], "12:30")
        approver, approver_api = self.worker("leave_view", "leave_approve", username="boss")
        self.assertEqual(approver_api.get(f"{API}/attendance/leave/?scope=all").data["count"], 2)
        self.assertEqual(approver_api.post(f"{API}/attendance/leave/{leave.data['id']}/approve/").data["status"], "Approved")
        self.assertEqual(approver_api.post(f"{API}/attendance/leave/{perm.data['id']}/reject/").status_code, 403)
        self.assertEqual(api.post(f"{API}/attendance/leave/{leave.data['id']}/cancel/").status_code, 400)  # already approved
        self.assertEqual(api.post(f"{API}/attendance/leave/{perm.data['id']}/cancel/").data["status"], "Cancelled")
        self.assertEqual(LeaveRequest.objects.get(pk=leave.data["id"]).reviewed_by, approver)

    def test_reject_and_permission_needed_to_apply(self):
        _user, api = self.worker("leave_apply")
        lr = api.post(f"{API}/attendance/leave/", {"type": "leave", "date": "2026-10-20", "reason": "TEST"}, format="json").data
        self.assertEqual(self.admin_api.post(f"{API}/attendance/leave/{lr['id']}/reject/").data["status"], "Rejected")
        _u, no_apply = self.worker(username="noapply")
        self.assertEqual(no_apply.post(f"{API}/attendance/leave/", {}, format="json").status_code, 403)


class CalendarReportSettingsTests(AttendanceBase):
    def test_calendar_shows_present_absent_leave(self):
        user, api = self.worker("check_in", "check_out")
        emp = user.employee
        AttendanceRecord.objects.create(employee=emp, attendance_date=date(2026, 10, 1), check_in_at=at(2026, 10, 1, 9, 0),
                                        check_out_at=at(2026, 10, 1, 17, 30), status="completed")
        LeaveRequest.objects.create(employee=emp, type="leave", date=date(2026, 10, 2), reason="TEST", status="approved")
        LeaveRequest.objects.create(employee=emp, type="leave", date=date(2026, 10, 3), reason="TEST", status="pending")
        self.clock(at(2026, 10, 4, 12, 0))
        days = {d["date"]: d["statuses"] for d in api.get(f"{API}/attendance/calendar/?month=2026-10").data["days"]}
        self.assertEqual(days[date(2026, 10, 1)], ["present"])
        self.assertEqual(days[date(2026, 10, 2)], ["leave"])
        self.assertEqual(days[date(2026, 10, 3)], ["absent"])  # a pending request doesn't count
        self.assertEqual(days[date(2026, 10, 4)], ["weekly_holiday"])  # Sunday: never absent
        self.assertNotIn(date(2026, 10, 5), days)  # future working days are left out
        self.assertEqual(days[date(2026, 10, 11)], ["weekly_holiday"])  # future holidays are shown
        other = self.employee(code="TEST-OTHER")
        self.assertEqual(api.get(f"{API}/attendance/calendar/?employee={other.id}").status_code, 403)
        self.assertEqual(self.admin_api.get(f"{API}/attendance/calendar/?employee={other.id}&month=2026-10").status_code, 200)

    def test_reports_and_exports(self):
        emp = self.employee(code="TEST-R1")
        AttendanceRecord.objects.create(employee=emp, attendance_date=date(2026, 10, 1), check_in_at=at(2026, 10, 1, 9, 0),
                                        check_out_at=at(2026, 10, 1, 11, 14), status="completed")
        LeaveRequest.objects.create(employee=emp, type="permission", date=date(2026, 10, 2), from_time=time(10), to_time=time(12),
                                    reason="TEST", status="approved")
        self.clock(at(2026, 10, 4, 12, 0))
        q = "date_from=2026-10-01&date_to=2026-10-03"
        daily = self.admin_api.get(f"{API}/attendance/reports/?type=daily&{q}").data
        statuses = {r["date"]: r["status"] for r in daily["table"]["rows"]}
        self.assertEqual(statuses, {date(2026, 10, 1): "Present", date(2026, 10, 2): "On Permission", date(2026, 10, 3): "Absent"})
        self.assertEqual(daily["table"]["rows"][0]["working"], "02h 14m")
        monthly = self.admin_api.get(f"{API}/attendance/reports/?type=monthly&{q}").data["table"]["rows"][0]
        self.assertEqual((monthly["present"], monthly["absent"], monthly["permission"]), (1, 1, 1))
        self.assertEqual(self.admin_api.get(f"{API}/attendance/reports/?type=employee&{q}").status_code, 400)  # needs an employee
        self.assertEqual(len(self.admin_api.get(f"{API}/attendance/reports/?type=daily&{q}&status=absent").data["table"]["rows"]), 1)
        self.assertEqual(len(self.admin_api.get(f"{API}/attendance/reports/?type=leave&{q}").data["table"]["rows"]), 1)
        for fmt in ("csv", "xlsx", "pdf"):
            res = self.admin_api.get(f"{API}/attendance/reports/?type=daily&{q}&format={fmt}")
            self.assertEqual(res.status_code, 200, fmt)
            self.assertIn("attachment", res["Content-Disposition"])
        _user, api = self.worker("check_in")
        self.assertEqual(api.get(f"{API}/attendance/reports/?type=daily").status_code, 403)
        _v, viewer = self.worker("report_view", username="viewer")
        self.assertEqual(viewer.get(f"{API}/attendance/reports/?type=daily&{q}").status_code, 200)
        self.assertEqual(viewer.get(f"{API}/attendance/reports/?type=daily&{q}&format=csv").status_code, 403)  # needs export

    def test_empty_report(self):
        self.clock(at(2026, 10, 4, 12, 0))
        self.assertEqual(self.admin_api.get(f"{API}/attendance/reports/?type=daily").data["table"]["rows"], [])

    def test_settings(self):
        _user, api = self.worker("settings_view")
        shown = api.get(f"{API}/attendance/settings/").data
        self.assertEqual((shown["open_time"], shown["close_time"], shown["timezone"], shown["weekly_holiday_label"],
                          shown["scheduled_duration"]), ("17:00", "09:20", "Asia/Kolkata (IST)", "Sunday", "08h 30m"))
        _u2, nobody = self.worker("check_in", username="nobody")
        self.assertEqual(nobody.get(f"{API}/attendance/settings/").status_code, 403)
        self.assertEqual(api.patch(f"{API}/attendance/settings/", {"open_time": "18:00"}, format="json").status_code, 403)
        self.assertIn("close_time", self.admin_api.patch(f"{API}/attendance/settings/", {"open_time": "09:20"}, format="json").data)
        res = self.admin_api.patch(f"{API}/attendance/settings/", {"open_time": "18:00", "close_time": "08:00"}, format="json")
        self.assertEqual((res.data["open_time"], res.data["close_time"], res.data["work_start"], res.data["work_end"]),
                         ("18:00", "08:00", "09:00", "17:30"))
        self.assertIn("work_end", self.admin_api.patch(f"{API}/attendance/settings/", {"work_end": "08:00"}, format="json").data)
        self.assertIn("weekly_holiday", self.admin_api.patch(f"{API}/attendance/settings/", {"weekly_holiday": 7}, format="json").data)
        res = self.admin_api.patch(f"{API}/attendance/settings/", {"weekly_holiday": 5}, format="json")
        self.assertEqual(res.data["weekly_holiday_label"], "Saturday")
        self.assertFalse(window.state(at(2026, 10, 8, 17, 30)).is_open)
        self.assertTrue(window.state(at(2026, 10, 8, 18, 0)).is_open)


class SettingsUsersPermissionTests(AttendanceBase):
    def test_permissions_are_set_per_user(self):
        user = make_user("sales", username="priya")
        res = self.admin_api.patch(f"{API}/settings/users/{user.id}/", {"attendance_permissions": ["calendar_view", "leave_apply"]}, format="json")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["attendance_permissions"], ["calendar_view", "leave_apply"])
        user.refresh_from_db()
        self.assertTrue(perms.has(user, "leave_apply"))
        self.assertFalse(perms.has(user, "leave_approve"))
        self.assertNotIn("check_in", perms.CODES)  # check-in / check-out need no permission, so they aren't offered
        self.assertEqual(self.admin_api.patch(f"{API}/settings/users/{user.id}/", {"attendance_permissions": ["check_in"]},
                                              format="json").status_code, 400)
        self.assertEqual(self.admin_api.patch(f"{API}/settings/users/{user.id}/", {"attendance_permissions": ["nope"]},
                                              format="json").status_code, 400)
        rows = {r["id"]: r for r in self.admin_api.get(f"{API}/settings/users/").data["results"]}
        self.assertEqual(rows[self.admin.id]["attendance_permissions"], perms.CODES)  # Super Admin: all
        labels = self.admin_api.get(f"{API}/settings/options/").data["attendance_permissions"]
        self.assertEqual(len(labels), len(perms.CODES))
        self.assertEqual(client_for(make_user("sales", username="s2")).patch(
            f"{API}/settings/users/{user.id}/", {"attendance_permissions": []}, format="json").status_code, 403)


class HolidayTests(AttendanceBase):
    def test_add_edit_delete_needs_the_holiday_permission(self):
        res = self.admin_api.post(f"{API}/attendance/holidays/", {"name": "TEST Diwali", "date": "2026-11-09",
                                                                  "description": "TEST"}, format="json")
        self.assertEqual(res.status_code, 201, res.data)
        hid = res.data["id"]
        dup = self.admin_api.post(f"{API}/attendance/holidays/", {"name": "TEST again", "date": "2026-11-09"}, format="json")
        self.assertIn("date", dup.data)
        self.assertIn("name", self.admin_api.post(f"{API}/attendance/holidays/", {"date": "2026-11-10"}, format="json").data)
        _u, api = self.worker("check_in")
        self.assertEqual(api.get(f"{API}/attendance/holidays/?year=2026").data["count"], 1)  # everyone sees holidays
        self.assertEqual(api.post(f"{API}/attendance/holidays/", {"name": "TEST", "date": "2026-11-11"}, format="json").status_code, 403)
        self.assertEqual(api.patch(f"{API}/attendance/holidays/{hid}/", {"name": "x"}, format="json").status_code, 403)
        self.assertEqual(api.delete(f"{API}/attendance/holidays/{hid}/").status_code, 403)
        _m, manager = self.worker("holiday_manage", username="manager")
        res = manager.patch(f"{API}/attendance/holidays/{hid}/", {"name": "TEST Deepavali"}, format="json")
        self.assertEqual((res.data["name"], res.data["date"]), ("TEST Deepavali", date(2026, 11, 9)))
        self.assertEqual(manager.delete(f"{API}/attendance/holidays/{hid}/").status_code, 204)
        self.assertFalse(OfficeHoliday.objects.exists())

    def test_holidays_are_never_absent_and_count_once(self):
        user, api = self.worker("check_in")
        OfficeHoliday.objects.create(name="TEST Gandhi Jayanti", date=date(2026, 10, 2))
        OfficeHoliday.objects.create(name="TEST Sunday festival", date=date(2026, 10, 11))  # also the weekly holiday
        self.clock(at(2026, 10, 12, 12, 0))
        days = {d["date"]: d for d in api.get(f"{API}/attendance/calendar/?month=2026-10").data["days"]}
        self.assertEqual(days[date(2026, 10, 2)]["statuses"], ["office_holiday"])
        self.assertEqual(days[date(2026, 10, 2)]["holiday"]["name"], "TEST Gandhi Jayanti")
        self.assertEqual(days[date(2026, 10, 3)]["statuses"], ["absent"])
        self.assertEqual(days[date(2026, 10, 4)]["statuses"], ["weekly_holiday"])
        self.assertEqual(days[date(2026, 10, 11)]["statuses"], ["office_holiday"])  # counted once
        self.assertEqual(days[date(2026, 10, 2)]["scheduled_duration"], "00h 00m")
        q = f"date_from=2026-10-01&date_to=2026-10-11&employee={user.employee.id}"
        monthly = self.admin_api.get(f"{API}/attendance/reports/?type=monthly&{q}").data["table"]["rows"][0]
        self.assertEqual((monthly["working_days"], monthly["absent"], monthly["office_holidays"], monthly["weekly_holidays"],
                          monthly["scheduled_hours"]), (8, 8, 2, 1, "68h 00m"))
        daily = {r["date"]: r["status"] for r in self.admin_api.get(f"{API}/attendance/reports/?type=daily&{q}").data["table"]["rows"]}
        self.assertEqual(daily[date(2026, 10, 2)], "Office Holiday (TEST Gandhi Jayanti)")

    def test_work_on_a_holiday_is_recorded_without_deductions(self):
        user, api = self.worker("check_in")
        emp = user.employee
        AttendanceRecord.objects.create(employee=emp, attendance_date=date(2026, 10, 4), check_in_at=at(2026, 10, 4, 9, 0),
                                        check_out_at=at(2026, 10, 4, 13, 0), status="completed")
        LeaveRequest.objects.create(employee=emp, type="permission", date=date(2026, 10, 4), from_time=time(10), to_time=time(11),
                                    reason="TEST", status="approved")
        self.clock(at(2026, 10, 5, 12, 0))
        day = next(d for d in api.get(f"{API}/attendance/calendar/?month=2026-10").data["days"] if d["date"] == date(2026, 10, 4))
        self.assertEqual(day["statuses"], ["present", "permission", "weekly_holiday"])
        self.assertEqual((day["scheduled_duration"], day["permission_duration"], day["working_duration"]), ("00h 00m", "00h 00m", "04h 00m"))

    def test_weekly_holiday_can_be_changed(self):
        _u, api = self.worker("check_in")
        AttendanceSettings.objects.update_or_create(pk=1, defaults={"weekly_holiday": 5})  # Saturday
        self.clock(at(2026, 10, 5, 12, 0))
        days = {d["date"]: d["statuses"] for d in api.get(f"{API}/attendance/calendar/?month=2026-10").data["days"]}
        self.assertEqual((days[date(2026, 10, 3)], days[date(2026, 10, 4)]), (["weekly_holiday"], ["absent"]))


class DashboardTests(AttendanceBase):
    def setUp(self):
        super().setUp()
        a, b, _c, d, e = (self.employee(code=f"TEST-{x}") for x in "ABCDE")
        a.department = "Packing"
        a.save()
        AttendanceRecord.objects.create(employee=a, attendance_date=date(2026, 10, 8), check_in_at=at(2026, 10, 8, 9, 0),
                                        check_out_at=at(2026, 10, 8, 16, 40), status="completed")
        AttendanceRecord.objects.create(employee=b, attendance_date=date(2026, 10, 8), check_in_at=at(2026, 10, 8, 9, 5))
        LeaveRequest.objects.create(employee=d, type="leave", date=date(2026, 10, 8), reason="TEST", status="approved")
        AttendanceRecord.objects.create(employee=e, attendance_date=date(2026, 10, 8), check_in_at=at(2026, 10, 8, 9, 0))
        LeaveRequest.objects.create(employee=e, type="permission", date=date(2026, 10, 8), from_time=time(16, 30),
                                    to_time=time(17, 30), reason="TEST", status="approved")
        self.clock(at(2026, 10, 8, 16, 45))

    def board(self, query="", api=None):
        return (api or self.admin_api).get(f"{API}/attendance/dashboard/?{query}")

    def test_summary_and_table(self):
        res = self.board()
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["summary"], {"total_active": 5, "present": 3, "absent": 1, "on_leave": 1, "on_permission": 1,
                                               "not_checked_out": 2})
        self.assertEqual(res.data["permission_label"], "Currently On Approved Permission")
        rows = {r["employee"]["employee_code"]: r for r in res.data["results"]}
        self.assertEqual((rows["TEST-A"]["scheduled_duration"], rows["TEST-A"]["working_duration"], rows["TEST-A"]["labels"]),
                         ("08h 30m", "07h 40m", ["Present"]))
        self.assertEqual(rows["TEST-C"]["labels"], ["Absent"])
        self.assertEqual(rows["TEST-D"]["labels"], ["On Leave"])
        self.assertEqual((rows["TEST-E"]["labels"], rows["TEST-E"]["permission_times"]), (["Present", "On Permission"], ["4:30 PM – 5:30 PM"]))

    def test_filters_search_and_pagination(self):
        self.assertEqual([r["employee"]["employee_code"] for r in self.board("status=absent").data["results"]], ["TEST-C"])
        self.assertEqual(self.board("search=TEST-D").data["count"], 1)
        self.assertEqual(self.board("department=Packing").data["summary"]["total_active"], 1)
        e = Employee.objects.get(employee_code="TEST-E")
        self.assertEqual(self.board(f"employee={e.id}").data["count"], 1)
        page = self.board("page_size=2")
        self.assertEqual((page.data["count"], len(page.data["results"])), (5, 2))
        self.assertEqual(self.board("status=nope").status_code, 400)
        self.assertEqual(self.board("date=2026-10-07").data["summary"]["absent"], 5)  # nobody came that day

    def test_sunday_is_a_holiday_for_everyone(self):
        res = self.board("date=2026-10-04")
        self.assertEqual((res.data["summary"]["absent"], res.data["holiday"]["label"]), (0, "Weekly Holiday"))
        self.assertEqual({tuple(r["labels"]) for r in res.data["results"]}, {("Weekly Holiday",)})

    def test_needs_the_view_all_permission(self):
        _u, api = self.worker("check_in", "report_view")
        self.assertEqual(self.board(api=api).status_code, 403)
        _v, viewer = self.worker("view_all", username="viewer")
        self.assertEqual(self.board(api=viewer).status_code, 200)

    def test_no_employees(self):
        Employee.objects.update(status=Employee.Status.INACTIVE)
        res = self.board()
        self.assertEqual((res.data["count"], res.data["summary"]["total_active"]), (0, 0))
