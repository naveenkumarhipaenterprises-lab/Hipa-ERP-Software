"""Attendance Only role: Attendance (check in / out, leave and permission requests) and nothing else."""
from django.test import TestCase

from apps.accounts.models import User

from .helpers import API, client_for, make_user


class AttendanceOnlyRoleTests(TestCase):
    def test_attendance_only_user_opens_attendance_and_no_module(self):
        api = client_for(make_user("attendance"))
        self.assertEqual(api.get(f"{API}/attendance/status/").status_code, 200)
        for path in ("/sales/orders/", "/inventory/items/", "/purchase/purchases/", "/supply-chain/overview/",
                     "/dashboard/summary/", "/settings/users/", "/supply-chain/customer-deliveries/"):
            self.assertEqual(api.get(API + path).status_code, 403, path)
        self.assertEqual(api.get(f"{API}/auth/me/").data["roles"], ["attendance"])

    def test_admin_can_switch_a_sales_user_to_attendance_only(self):
        admin = client_for(make_user("admin"))
        seller = make_user("sales", extra_roles=["marketing"])
        res = admin.patch(f"{API}/settings/users/{seller.id}/", {"role": "attendance"}, format="json")
        self.assertEqual(res.status_code, 200, res.data)
        seller.refresh_from_db()
        self.assertEqual((seller.role, seller.extra_roles, seller.all_roles), ("attendance", [], ["attendance"]))
        self.assertEqual(client_for(seller).get(f"{API}/sales/orders/").status_code, 403)

    def test_attendance_only_is_never_an_extra_role(self):
        admin = client_for(make_user("admin"))
        seller = make_user("sales")
        res = admin.patch(f"{API}/settings/users/{seller.id}/", {"extra_roles": ["attendance"]}, format="json")
        self.assertEqual(res.status_code, 400)
        self.assertIn("attendance", [r["value"] for r in admin.get(f"{API}/settings/options/").data["roles"]])
        self.assertEqual(User.objects.get(pk=seller.pk).all_roles, ["sales"])

    def test_roles_window_switches_to_attendance_only_and_back(self):
        admin = client_for(make_user("admin"))
        aruna = make_user("purchase", extra_roles=["inventory"])
        res = admin.patch(f"{API}/settings/users/{aruna.id}/", {"role": "attendance", "extra_roles": []}, format="json")
        self.assertEqual(res.status_code, 200, res.data)
        aruna.refresh_from_db()
        self.assertEqual(aruna.all_roles, ["attendance"])
        self.assertEqual(client_for(aruna).get(f"{API}/inventory/items/").status_code, 403)
        res = admin.patch(f"{API}/settings/users/{aruna.id}/", {"role": "purchase", "extra_roles": ["inventory"]}, format="json")
        self.assertEqual(res.status_code, 200, res.data)
        aruna.refresh_from_db()
        self.assertEqual(aruna.all_roles, ["purchase", "inventory"])
