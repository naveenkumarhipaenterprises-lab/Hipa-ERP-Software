"""Extra roles: a person with Purchase + Inventory gets the access of both, on every endpoint."""
from django.test import TestCase

from apps.core.roles import can_read, can_write

from .helpers import API, client_for, make_user


class ExtraRoleTests(TestCase):
    def test_access_is_the_union_of_all_roles(self):
        user = make_user("purchase", extra_roles=["inventory"])
        self.assertEqual(user.all_roles, ["purchase", "inventory"])
        self.assertTrue(can_write(user, "purchase"))
        self.assertTrue(can_write(user, "inventory"))  # Purchase alone can't change product stock
        self.assertFalse(can_read(user, "marketing"))
        plain = make_user("purchase", username="test_plain_purchase")
        self.assertFalse(can_write(plain, "inventory"))

    def test_server_enforces_extra_role(self):
        both = client_for(make_user("purchase", extra_roles=["inventory"]))
        plain = client_for(make_user("purchase", username="test_plain_purchase"))
        # Validation error (400) means the role check passed; 403 means it was refused
        self.assertEqual(plain.post(f"{API}/inventory/movements/", {}, format="json").status_code, 403)
        self.assertEqual(both.post(f"{API}/inventory/movements/", {}, format="json").status_code, 400)

    def test_super_admin_is_never_an_extra_role_and_duplicates_are_dropped(self):
        user = make_user("sales", extra_roles=["admin", "sales", "marketing", "marketing"])
        user.refresh_from_db()
        self.assertEqual(user.extra_roles, ["marketing"])
        self.assertFalse(can_read(user, "settings"))

    def test_login_and_me_return_all_roles(self):
        user = make_user("purchase", extra_roles=["inventory"])
        res = client_for(user).get(f"{API}/auth/me/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["role"], "purchase")
        self.assertEqual(res.data["roles"], ["purchase", "inventory"])

    def test_settings_users_can_set_extra_roles(self):
        admin = client_for(make_user("admin"))
        target = make_user("purchase", username="test_target")
        res = admin.patch(f"{API}/settings/users/{target.pk}/", {"extra_roles": ["inventory"]}, format="json")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["extra_roles"], ["inventory"])
        res = admin.patch(f"{API}/settings/users/{target.pk}/", {"extra_roles": ["admin"]}, format="json")
        self.assertEqual(res.status_code, 400)
        res = admin.post(f"{API}/settings/users/", {"name": "TEST New", "email": "test.new@test.invalid",
                                                     "role": "sales", "extra_roles": ["marketing"]}, format="json")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data["extra_roles"], ["marketing"])
