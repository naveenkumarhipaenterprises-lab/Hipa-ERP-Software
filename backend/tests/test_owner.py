"""Only the owner (Django superuser) may add or change Super Admin accounts; other Super Admins may not."""
from django.test import TestCase

from apps.accounts.models import User

from .helpers import API, client_for, make_user


class OwnerTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_superuser(username="test_owner", email="test.owner@test.invalid",
                                                   password="Test-Passw0rd!9", name="TEST Owner")
        self.admin = make_user("admin", username="test_admin2")  # Super Admin, not the owner
        self.staff = make_user("sales", username="test_staff")

    def test_super_admin_cannot_change_super_admins(self):
        api = client_for(self.admin)
        self.assertEqual(api.patch(f"{API}/settings/users/{self.owner.pk}/", {"status": "Inactive"}, format="json").status_code, 403)
        self.assertEqual(api.post(f"{API}/settings/users/{self.owner.pk}/password/", {"password": "Hipa-Spice-2026!"},
                                  format="json").status_code, 403)
        self.assertEqual(api.patch(f"{API}/settings/users/{self.staff.pk}/", {"role": "admin"}, format="json").status_code, 403)
        self.assertEqual(api.post(f"{API}/settings/users/", {"name": "TEST X", "email": "test.x@test.invalid", "role": "admin"},
                                  format="json").status_code, 403)
        # ...but still manages everyone else
        self.assertEqual(api.patch(f"{API}/settings/users/{self.staff.pk}/", {"role": "marketing"}, format="json").status_code, 200)
        self.assertEqual(api.post(f"{API}/settings/users/{self.staff.pk}/password/", {"password": "Hipa-Spice-2026!"},
                                  format="json").status_code, 200)

    def test_owner_manages_super_admins(self):
        api = client_for(self.owner)
        self.assertEqual(api.post(f"{API}/settings/users/{self.admin.pk}/password/", {"password": "Hipa-Spice-2026!"},
                                  format="json").status_code, 200)
        self.assertEqual(api.patch(f"{API}/settings/users/{self.admin.pk}/", {"role": "management"}, format="json").status_code, 200)
        self.assertEqual(api.patch(f"{API}/settings/users/{self.staff.pk}/", {"role": "admin"}, format="json").status_code, 200)

    def test_me_says_who_is_owner(self):
        self.assertTrue(client_for(self.owner).get(f"{API}/auth/me/").data["is_owner"])
        self.assertFalse(client_for(self.admin).get(f"{API}/auth/me/").data["is_owner"])
