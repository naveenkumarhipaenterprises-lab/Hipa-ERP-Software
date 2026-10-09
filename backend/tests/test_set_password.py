"""Settings -> Users -> Password: a Super Admin sets another person's password."""
from django.test import TestCase

from apps.system.models import AuditLog

from .helpers import API, client_for, make_user

NEW = "Hipa-Spice-2026!"


class SetPasswordTests(TestCase):
    def setUp(self):
        self.admin = make_user("admin")
        self.staff = make_user("sales", username="test_staff")
        self.staff.set_unusable_password()
        self.staff.save()
        self.url = f"{API}/settings/users/{self.staff.pk}/password/"

    def test_super_admin_sets_password_and_user_can_sign_in(self):
        res = client_for(self.admin).post(self.url, {"password": NEW}, format="json")
        self.assertEqual(res.status_code, 200, res.data)
        self.staff.refresh_from_db()
        self.assertTrue(self.staff.check_password(NEW))
        self.assertEqual(self.staff.status, "active")
        login = self.client.post(f"{API}/auth/login/", {"username": self.staff.email, "password": NEW},
                                 content_type="application/json")
        self.assertEqual(login.status_code, 200)
        self.assertTrue(AuditLog.objects.filter(action="Set user password", target=self.staff.email).exists())

    def test_weak_password_is_refused(self):
        res = client_for(self.admin).post(self.url, {"password": "12345678"}, format="json")
        self.assertEqual(res.status_code, 400)
        self.assertIn("password", res.data)

    def test_only_super_admin(self):
        for role in ("management", "sales"):
            res = client_for(make_user(role, username=f"test_{role}_x")).post(self.url, {"password": NEW}, format="json")
            self.assertEqual(res.status_code, 403, role)
        self.staff.refresh_from_db()
        self.assertFalse(self.staff.has_usable_password())

    def test_not_for_own_account(self):
        res = client_for(self.admin).post(f"{API}/settings/users/{self.admin.pk}/password/", {"password": NEW}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_old_sessions_stop_working(self):
        self.staff.set_password("Old-Passw0rd!9")
        self.staff.save()
        token = self.client.post(f"{API}/auth/login/", {"username": self.staff.email, "password": "Old-Passw0rd!9"},
                                 content_type="application/json").data["access"]
        client_for(self.admin).post(self.url, {"password": NEW}, format="json")
        res = self.client.get(f"{API}/auth/me/", HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertEqual(res.status_code, 401)
