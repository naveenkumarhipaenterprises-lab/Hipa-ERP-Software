"""
Attendance: the 05:00 PM → 09:20 AM window (server time, IST), separate check-in / check-out permissions,
employees, leave / permission requests, calendar, reports and settings. TEST records only; the clock is fixed.
"""
from datetime import date, datetime, time
from unittest import mock

from django.test import TestCase

from apps.attendance import permissions as perms
from apps.attendance import window
from apps.attendance.models import AttendanceRecord, AttendanceSettings, Employee, LeaveRequest

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

    def test_after_midnight_belongs_to_the_previous_evening(self):
        s = AttendanceSettings.load()
        self.assertEqual(window.state(at(2026, 10, 8, 17, 0), s).attendance_date, date(2026, 10, 8))
        night = window.state(at(2026, 10, 9, 2, 0), s)
        self.assertEqual(night.attendance_date, date(2026, 10, 8))
        self.assertEqual(night.closes_at, at(2026, 10, 9, 9, 20))
        closed = window.state(at(2026, 10, 9, 12, 0), s)
        self.assertIsNone(closed.attendance_date)
        self.assertEqual((closed.opens_at, closed.last_date), (at(2026, 10, 9, 17, 0), date(2026, 10, 8)))

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
    def test_check_in_and_out_during_the_open_window(self):
        user, api = self.worker("check_in", "check_out")
        self.clock(at(2026, 10, 8, 18, 18))
        res = api.post(f"{API}/attendance/check-in/", {"check_in_at": "2020-01-01T00:00:00"}, format="json")  # ignored
        self.assertEqual(res.status_code, 201, res.data)
        self.assertTrue(res.data["record"]["check_in_at"].startswith("2026-10-08T18:18"))
        self.assertEqual((res.data["can_check_in"], res.data["can_check_out"]), (False, True))
        self.assertEqual(api.post(f"{API}/attendance/check-in/").status_code, 400)  # once per window
        self.clock(at(2026, 10, 8, 20, 32))
        res = api.post(f"{API}/attendance/check-out/")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual((res.data["record"]["duration"], res.data["record"]["status"]), ("02h 14m", "Attendance completed"))
        self.assertEqual(api.post(f"{API}/attendance/check-out/").status_code, 400)
        r = AttendanceRecord.objects.get()
        self.assertEqual((r.attendance_date, r.status), (date(2026, 10, 8), "completed"))

    def test_after_midnight_check_out_closes_the_same_window(self):
        _user, api = self.worker("check_in", "check_out")
        self.clock(at(2026, 10, 8, 22, 0))
        api.post(f"{API}/attendance/check-in/")
        self.clock(at(2026, 10, 9, 6, 0))
        self.assertEqual(api.post(f"{API}/attendance/check-out/").status_code, 200)
        self.assertEqual(AttendanceRecord.objects.get().attendance_date, date(2026, 10, 8))

    def test_closed_window_rejects_both(self):
        _user, api = self.worker("check_in", "check_out")
        self.clock(at(2026, 10, 8, 10, 0))
        res = api.post(f"{API}/attendance/check-in/")
        self.assertEqual(res.status_code, 400)
        self.assertIn("closed", res.data["detail"])
        self.assertEqual(api.post(f"{API}/attendance/check-out/").status_code, 400)
        status = api.get(f"{API}/attendance/status/").data
        self.assertEqual((status["window"]["is_open"], status["can_check_in"]), (False, False))
        self.assertIn("05:00 PM", status["window"]["message"])
        self.assertFalse(AttendanceRecord.objects.exists())

    def test_separate_permissions(self):
        self.clock(at(2026, 10, 8, 18, 0))
        _a, both = self.worker("check_in", "check_out", username="a")
        _b, in_only = self.worker("check_in", username="b")
        _c, out_only = self.worker("check_out", username="c")
        _d, neither = self.worker(username="d")
        self.assertEqual(both.post(f"{API}/attendance/check-in/").status_code, 201)
        self.assertEqual(in_only.post(f"{API}/attendance/check-in/").status_code, 201)
        self.assertEqual(in_only.post(f"{API}/attendance/check-out/").status_code, 403)
        self.assertEqual(out_only.post(f"{API}/attendance/check-in/").status_code, 403)
        self.assertEqual(out_only.post(f"{API}/attendance/check-out/").status_code, 400)  # no active record yet
        AttendanceRecord.objects.create(employee=Employee.objects.get(employee_code="TEST-c"), attendance_date=date(2026, 10, 8),
                                        check_in_at=at(2026, 10, 8, 17, 30))
        self.assertEqual(out_only.post(f"{API}/attendance/check-out/").status_code, 200)  # valid active record exists
        self.assertEqual(neither.post(f"{API}/attendance/check-in/").status_code, 403)
        self.assertEqual(neither.post(f"{API}/attendance/check-out/").status_code, 403)
        flags = neither.get(f"{API}/attendance/status/").data["permissions"]
        self.assertFalse(flags["check_in"] or flags["check_out"])

    def test_login_without_an_employee_is_told_so(self):
        user = make_user("sales", username="nolink")
        perms.set_granted(user, ["check_in"])
        self.clock(at(2026, 10, 8, 18, 0))
        res = client_for(user).post(f"{API}/attendance/check-in/")
        self.assertEqual(res.status_code, 400)
        self.assertIn("isn't linked to an active employee", res.data["detail"])

    def test_not_checked_out_after_the_window_closes(self):
        _user, api = self.worker("check_in", "check_out")
        self.clock(at(2026, 10, 8, 18, 0))
        api.post(f"{API}/attendance/check-in/")
        self.clock(at(2026, 10, 9, 10, 0))
        self.assertEqual(api.post(f"{API}/attendance/check-out/").status_code, 400)
        status = api.get(f"{API}/attendance/status/").data
        self.assertEqual(status["record"]["status"], "Not checked out")
        self.assertEqual(api.get(f"{API}/attendance/history/").data["results"][0]["status"], "Not checked out")

    def test_super_admin_has_every_permission(self):
        self.employee(user=self.admin, code="TEST-ADM")
        self.clock(at(2026, 10, 8, 18, 0))
        self.assertEqual(self.admin_api.post(f"{API}/attendance/check-in/").status_code, 201)


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
        AttendanceRecord.objects.create(employee=emp, attendance_date=date(2026, 10, 1), check_in_at=at(2026, 10, 1, 18, 0),
                                        check_out_at=at(2026, 10, 1, 21, 0), status="completed")
        LeaveRequest.objects.create(employee=emp, type="leave", date=date(2026, 10, 2), reason="TEST", status="approved")
        LeaveRequest.objects.create(employee=emp, type="leave", date=date(2026, 10, 3), reason="TEST", status="pending")
        self.clock(at(2026, 10, 4, 12, 0))
        days = {d["date"]: d["statuses"] for d in api.get(f"{API}/attendance/calendar/?month=2026-10").data["days"]}
        self.assertEqual(days[date(2026, 10, 1)], ["present"])
        self.assertEqual(days[date(2026, 10, 2)], ["leave"])
        self.assertEqual(days[date(2026, 10, 3)], ["absent"])  # a pending request doesn't count
        self.assertNotIn(date(2026, 10, 5), days)  # future days are left out
        other = self.employee(code="TEST-OTHER")
        self.assertEqual(api.get(f"{API}/attendance/calendar/?employee={other.id}").status_code, 403)
        self.assertEqual(self.admin_api.get(f"{API}/attendance/calendar/?employee={other.id}&month=2026-10").status_code, 200)

    def test_reports_and_exports(self):
        emp = self.employee(code="TEST-R1")
        AttendanceRecord.objects.create(employee=emp, attendance_date=date(2026, 10, 1), check_in_at=at(2026, 10, 1, 17, 58),
                                        check_out_at=at(2026, 10, 1, 20, 12), status="completed")
        LeaveRequest.objects.create(employee=emp, type="permission", date=date(2026, 10, 2), from_time=time(10), to_time=time(12),
                                    reason="TEST", status="approved")
        self.clock(at(2026, 10, 4, 12, 0))
        q = "date_from=2026-10-01&date_to=2026-10-03"
        daily = self.admin_api.get(f"{API}/attendance/reports/?type=daily&{q}").data
        statuses = {r["date"]: r["status"] for r in daily["table"]["rows"]}
        self.assertEqual(statuses, {date(2026, 10, 1): "Present", date(2026, 10, 2): "Permission", date(2026, 10, 3): "Absent"})
        self.assertEqual(daily["table"]["rows"][0]["duration"], "02h 14m")
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

    def test_empty_report(self):
        self.clock(at(2026, 10, 4, 12, 0))
        self.assertEqual(self.admin_api.get(f"{API}/attendance/reports/?type=daily").data["table"]["rows"], [])

    def test_settings(self):
        _user, api = self.worker("check_in")
        shown = api.get(f"{API}/attendance/settings/").data  # anyone can see the rule
        self.assertEqual((shown["open_time"], shown["close_time"], shown["timezone"]), ("17:00", "09:20", "Asia/Kolkata (IST)"))
        self.assertEqual(api.patch(f"{API}/attendance/settings/", {"open_time": "18:00"}, format="json").status_code, 403)
        self.assertIn("close_time", self.admin_api.patch(f"{API}/attendance/settings/", {"open_time": "09:20"}, format="json").data)
        res = self.admin_api.patch(f"{API}/attendance/settings/", {"open_time": "18:00", "close_time": "08:00"}, format="json")
        self.assertEqual((res.data["open_time"], res.data["close_time"]), ("18:00", "08:00"))
        self.assertFalse(window.state(at(2026, 10, 8, 17, 30)).is_open)
        self.assertTrue(window.state(at(2026, 10, 8, 18, 0)).is_open)


class SettingsUsersPermissionTests(AttendanceBase):
    def test_permissions_are_set_per_user(self):
        user = make_user("sales", username="priya")
        res = self.admin_api.patch(f"{API}/settings/users/{user.id}/", {"attendance_permissions": ["check_in", "leave_apply"]}, format="json")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["attendance_permissions"], ["check_in", "leave_apply"])
        user.refresh_from_db()
        self.assertTrue(perms.has(user, "check_in"))
        self.assertFalse(perms.has(user, "check_out"))
        self.assertEqual(self.admin_api.patch(f"{API}/settings/users/{user.id}/", {"attendance_permissions": ["nope"]},
                                              format="json").status_code, 400)
        rows = {r["id"]: r for r in self.admin_api.get(f"{API}/settings/users/").data["results"]}
        self.assertEqual(rows[self.admin.id]["attendance_permissions"], perms.CODES)  # Super Admin: all
        labels = self.admin_api.get(f"{API}/settings/options/").data["attendance_permissions"]
        self.assertEqual(len(labels), 10)
        self.assertEqual(client_for(make_user("sales", username="s2")).patch(
            f"{API}/settings/users/{user.id}/", {"attendance_permissions": []}, format="json").status_code, 403)
