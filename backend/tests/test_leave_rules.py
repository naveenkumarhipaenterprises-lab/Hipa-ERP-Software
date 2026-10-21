"""
Leave / permission requests can't clash: no request on a holiday, no second request for a day that already has a
whole-day one, no overlapping times. Employee phone numbers and e-mails are only for people who manage employees.
(October 2026: the 18th is a Sunday, the weekly holiday.)
"""
from datetime import date

from apps.attendance.models import LeaveRequest, OfficeHoliday

from .helpers import API
from .test_attendance import AttendanceBase


class LeaveClashTests(AttendanceBase):
    def setUp(self):
        super().setUp()
        self.user, self.api = self.worker("leave_apply")

    def apply(self, **body):
        return self.api.post(f"{API}/attendance/leave/", {"reason": "TEST", **body}, format="json")

    def test_no_request_on_a_holiday(self):
        OfficeHoliday.objects.create(name="TEST Deepavali", date=date(2026, 10, 20))
        office = self.apply(type="leave", date="2026-10-20")
        self.assertEqual(office.status_code, 400)
        self.assertIn("TEST Deepavali", office.data["date"][0])
        weekly = self.apply(type="permission", date="2026-10-18", from_time="10:00", to_time="11:00")
        self.assertEqual(weekly.status_code, 400)
        self.assertIn("is a holiday", weekly.data["date"][0])

    def test_whole_day_leave_clashes_with_anything_that_day(self):
        self.assertEqual(self.apply(type="leave", date="2026-10-12").status_code, 201)
        again = self.apply(type="leave", date="2026-10-12")
        self.assertEqual(again.status_code, 400)
        self.assertIn("pending leave request for this day (whole day)", again.data["date"][0])
        self.assertEqual(self.apply(type="permission", date="2026-10-12", from_time="10:00", to_time="11:00").status_code, 400)

    def test_permissions_clash_only_when_their_times_overlap(self):
        self.assertEqual(self.apply(type="permission", date="2026-10-13", from_time="10:00", to_time="11:00").status_code, 201)
        overlap = self.apply(type="permission", date="2026-10-13", from_time="10:30", to_time="12:00")
        self.assertEqual(overlap.status_code, 400)
        self.assertIn("10:00–11:00", overlap.data["date"][0])
        self.assertEqual(self.apply(type="permission", date="2026-10-13", from_time="11:00", to_time="12:00").status_code, 201)
        self.assertEqual(self.apply(type="leave", date="2026-10-13").status_code, 400)  # a whole day covers both

    def test_cancelled_or_rejected_requests_dont_block_a_new_one(self):
        first = self.apply(type="leave", date="2026-10-14").data
        self.assertEqual(self.api.post(f"{API}/attendance/leave/{first['id']}/cancel/").status_code, 200)
        self.assertEqual(self.apply(type="leave", date="2026-10-14").status_code, 201)

    def test_editing_checks_the_other_requests_but_not_itself(self):
        a = self.apply(type="permission", date="2026-10-15", from_time="10:00", to_time="11:00").data
        b = self.apply(type="permission", date="2026-10-15", from_time="14:00", to_time="15:00").data
        moved = self.api.patch(f"{API}/attendance/leave/{a['id']}/", {"to_time": "11:30"}, format="json")
        self.assertEqual(moved.status_code, 200, moved.data)  # its own old times don't count as a clash
        clash = self.api.patch(f"{API}/attendance/leave/{a['id']}/", {"to_time": "14:30"}, format="json")
        self.assertEqual(clash.status_code, 400)
        self.assertEqual(LeaveRequest.objects.get(pk=a["id"]).to_time.strftime("%H:%M"), "11:30")
        self.assertEqual(self.api.patch(f"{API}/attendance/leave/{b['id']}/", {"date": "2026-10-18"}, format="json").status_code, 400)

    def test_editing_needs_the_apply_permission(self):
        lr = self.apply(type="leave", date="2026-10-16").data
        from apps.attendance import permissions as perms

        perms.set_granted(self.user, [])
        self.assertEqual(self.api.patch(f"{API}/attendance/leave/{lr['id']}/", {"reason": "TEST changed"}, format="json").status_code, 403)


class EmployeeContactPrivacyTests(AttendanceBase):
    def test_contacts_only_for_people_who_manage_employees(self):
        self.employee(code="TEST-777", email="meena@test.invalid", phone="9876543210")
        _v, viewer = self.worker("employee_view", username="viewer")
        _m, manager = self.worker("employee_manage", username="manager")

        def row(api, **params):
            return next(r for r in api.get(f"{API}/attendance/employees/", params).data["results"] if r["employee_code"] == "TEST-777")

        seen = row(viewer)
        self.assertEqual((seen["email"], seen["phone"]), (None, None))
        self.assertNotIn("meena@test.invalid", str(viewer.get(f"{API}/attendance/employees/{seen['id']}/").data))
        # A viewer can't find people by e-mail either
        self.assertEqual(viewer.get(f"{API}/attendance/employees/", {"search": "meena@"}).data["count"], 0)
        self.assertEqual((row(manager)["email"], row(manager)["phone"]), ("meena@test.invalid", "9876543210"))
        self.assertEqual(manager.get(f"{API}/attendance/employees/", {"search": "meena@"}).data["count"], 1)
