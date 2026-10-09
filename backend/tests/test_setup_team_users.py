"""`manage.py setup_team_users`: loads the team (logins, roles, Attendance employees) from a CSV file."""
import tempfile
from io import StringIO
from pathlib import Path

from django.core import mail
from django.core.management import CommandError, call_command
from django.test import TestCase

from apps.accounts.models import User
from apps.attendance import permissions as attendance_perms
from apps.attendance.models import Employee
from apps.system.models import AuditLog

HEADER = "employee_code,name,email,joining_date,role,attendance_permissions\n"


class SetupTeamUsersTests(TestCase):
    def run_cmd(self, rows, *args):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "team.csv"
            path.write_text(HEADER + rows, encoding="utf-8")
            out = StringIO()
            call_command("setup_team_users", str(path), *args, stdout=out)
            return out.getvalue()

    def test_creates_super_admins_and_team_members_with_invites(self):
        out = self.run_cmd(
            "T01,TEST Admin,test.admin@test.invalid,15-07-2026,admin,\n"
            "T02,TEST Seller,test.seller@test.invalid,31-07-2026,Sales Team,check_in;check_out;leave_apply\n"
        )
        admin = User.objects.get(email="test.admin@test.invalid")
        self.assertEqual(admin.role, "admin")
        self.assertTrue(admin.is_superuser and admin.is_staff)
        self.assertFalse(admin.has_usable_password())  # sets it from the invitation e-mail
        seller = User.objects.get(email="test.seller@test.invalid")
        self.assertEqual(seller.role, "sales")
        self.assertFalse(seller.is_superuser)
        self.assertEqual(attendance_perms.granted(seller), ["check_in", "check_out", "leave_apply"])
        self.assertEqual(sorted(m.to[0] for m in mail.outbox), ["test.admin@test.invalid", "test.seller@test.invalid"])
        emp = Employee.objects.get(employee_code="T02")
        self.assertEqual((emp.user, emp.email, str(emp.joining_date)), (seller, "test.seller@test.invalid", "2026-07-31"))
        self.assertIn("2 created", out)
        self.assertTrue(AuditLog.objects.filter(action__startswith="Team setup").exists())

    def test_rerun_changes_nothing_and_sends_nothing(self):
        rows = "T01,TEST Admin,test.admin@test.invalid,15-07-2026,admin,\n"
        self.run_cmd(rows)
        mail.outbox.clear()
        out = self.run_cmd(rows)
        self.assertIn("1 unchanged", out)
        self.assertEqual(mail.outbox, [])
        self.assertEqual(User.objects.filter(email="test.admin@test.invalid").count(), 1)

    def test_existing_user_keeps_password_and_gets_new_role(self):
        user = User.objects.create_user(username="test_existing", email="Test.Existing@test.invalid",
                                        password="Test-Passw0rd!9", name="TEST Existing", role="sales")
        self.run_cmd("T05,TEST Existing,test.existing@test.invalid,,management,\n")
        user.refresh_from_db()
        self.assertEqual(user.role, "management")
        self.assertTrue(user.check_password("Test-Passw0rd!9"))
        self.assertEqual(mail.outbox, [])  # already has a password: no invitation
        self.assertEqual(Employee.objects.get(employee_code="T05").user, user)

    def test_blank_role_creates_no_login_but_keeps_employee(self):
        out = self.run_cmd("T03,TEST Pending,test.pending@test.invalid,27-07-2026,,\n")
        self.assertFalse(User.objects.filter(email="test.pending@test.invalid").exists())
        self.assertTrue(Employee.objects.filter(employee_code="T03", user__isnull=True).exists())
        self.assertIn("1 skipped", out)

    def test_dry_run_writes_nothing(self):
        out = self.run_cmd("T01,TEST Admin,test.admin@test.invalid,15-07-2026,admin,\n", "--dry-run")
        self.assertIn("DRY RUN", out)
        self.assertFalse(User.objects.filter(email="test.admin@test.invalid").exists())
        self.assertFalse(Employee.objects.filter(employee_code="T01").exists())
        self.assertEqual(mail.outbox, [])

    def test_bad_rows_stop_everything(self):
        with self.assertRaisesMessage(CommandError, "Nothing was changed"):
            self.run_cmd("T01,TEST Good,test.good@test.invalid,15-07-2026,admin,\n"
                         "T02,TEST Bad,not-an-email,2026/31/31,wizard,\n")
        self.assertFalse(User.objects.filter(email="test.good@test.invalid").exists())

    def test_superuser_is_never_demoted_from_the_file(self):
        boss = User.objects.create_superuser(username="test_boss", email="test.boss@test.invalid",
                                             password="Test-Passw0rd!9", name="TEST Boss")
        out = self.run_cmd(",TEST Boss,test.boss@test.invalid,,sales,\n")
        boss.refresh_from_db()
        self.assertEqual(boss.role, "admin")
        self.assertIn("Django superuser", out)

    def test_employee_with_other_email_is_not_linked(self):
        Employee.objects.create(employee_code="T07", name="TEST Someone", email="someone.else@test.invalid")
        out = self.run_cmd("T07,TEST Seven,test.seven@test.invalid,,sales,\n")
        self.assertIsNone(Employee.objects.get(employee_code="T07").user)
        self.assertIn("different e-mail", out)

    def test_invited_users_can_sign_in_only_after_setting_a_password(self):
        self.run_cmd("T01,TEST Admin,test.admin@test.invalid,15-07-2026,admin,\n")
        res = self.client.post("/api/v1/auth/login/", {"username": "test.admin", "password": "anything"},
                               content_type="application/json")
        self.assertNotEqual(res.status_code, 200)

    def test_two_roles_in_one_cell(self):
        self.run_cmd("T03,TEST Both,test.both@test.invalid,27-07-2026,purchase+inventory,\n")
        user = User.objects.get(email="test.both@test.invalid")
        self.assertEqual((user.role, user.all_roles), ("purchase", ["purchase", "inventory"]))
        out = self.run_cmd("T03,TEST Both,test.both@test.invalid,27-07-2026,purchase+inventory,\n")
        self.assertIn("1 unchanged", out)
        with self.assertRaisesMessage(CommandError, "Super Admin can only be the first"):
            self.run_cmd("T04,TEST Bad,test.bad@test.invalid,,sales+admin,\n")
