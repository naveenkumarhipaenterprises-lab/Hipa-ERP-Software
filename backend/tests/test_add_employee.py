"""Settings -> Users -> Add Employee: login, role, password, employee record and Attendance access in one step."""
from django.test import TestCase

from apps.accounts.models import User
from apps.attendance import permissions as attendance_perms
from apps.attendance.models import Employee

from .helpers import API, client_for, make_user

URL = f"{API}/settings/users/add-employee/"


def body(**extra):
    return {"name": "TEST New Person", "email": "test.new@test.invalid", "role": "sales", "password": "Hipa-Spice-2026!",
            "employee_code": "T11", "department": "Sales", "designation": "Executive", "phone": "+91 98400 00000",
            "joining_date": "2026-10-12", **extra}


class AddEmployeeTests(TestCase):
    def test_management_adds_an_employee_who_can_sign_in_and_check_in(self):
        res = client_for(make_user("management")).post(URL, body(), format="json")
        self.assertEqual(res.status_code, 201, res.data)
        user = User.objects.get(email="test.new@test.invalid")
        self.assertEqual((user.role, user.status), ("sales", "active"))
        emp = Employee.objects.get(employee_code="T11")
        self.assertEqual((emp.user, emp.department, str(emp.joining_date)), (user, "Sales", "2026-10-12"))
        self.assertEqual(attendance_perms.granted(user), ["leave_apply"])
        login = self.client.post(f"{API}/auth/login/", {"username": "test.new@test.invalid", "password": "Hipa-Spice-2026!"},
                                 content_type="application/json")
        self.assertEqual(login.status_code, 200)

    def test_validation(self):
        api = client_for(make_user("admin"))
        Employee.objects.create(employee_code="T11", name="TEST Taken")
        res = api.post(URL, body(password="12345678", phone="abc"), format="json")
        self.assertEqual(res.status_code, 400)
        self.assertIn("employee_code", res.data)
        self.assertIn("phone", res.data)
        res = api.post(URL, body(employee_code="T12", password="12345678"), format="json")
        self.assertIn("password", res.data)
        self.assertFalse(User.objects.filter(email="test.new@test.invalid").exists())

    def test_only_managers_and_only_owner_adds_super_admins(self):
        self.assertEqual(client_for(make_user("sales")).post(URL, body(), format="json").status_code, 403)
        self.assertEqual(client_for(make_user("admin")).post(URL, body(role="admin"), format="json").status_code, 403)
        owner = User.objects.create_superuser(username="owner", email="owner@test.invalid", password="Test-Passw0rd!9", name="TEST Owner")
        self.assertEqual(client_for(owner).post(URL, body(role="admin"), format="json").status_code, 201)
