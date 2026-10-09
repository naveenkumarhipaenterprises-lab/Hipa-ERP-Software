"""Role-based access is enforced on the server, matching the frontend's navigation rules."""
from django.test import TestCase

from apps.core.roles import MODULE_READ

from .helpers import API, client_for, make_user

READ_PATH = {
    "dashboard": "/dashboard/summary/",
    "sales": "/sales/overview/",
    "inventory": "/inventory/overview/",
    "purchase": "/purchase/purchases/",
    "marketing": "/marketing/overview/",
    "customers": "/customers/",
    "supply_chain": "/supply-chain/overview/",
    "quality": "/quality/overview/",
    "attendance": "/attendance/status/",
    "ai_assistant": "/ai/status/",
    "reports": "/reports/",
    "settings": "/settings/options/",
}
ROLES = ["admin", "management", "sales", "purchase", "inventory", "marketing", "finance", "quality", "supply_chain"]


class RolePermissionTests(TestCase):
    def test_read_matrix(self):
        for role in ROLES:
            api = client_for(make_user(role))
            for module, path in READ_PATH.items():
                expected = 200 if role in MODULE_READ[module] else 403
                res = api.get(API + path)
                self.assertEqual(res.status_code, expected, f"{role} GET {path}")

    def test_read_only_roles_cannot_write(self):
        # The Accounts team (role finance) can view sales but not create orders
        res = client_for(make_user("finance")).post(f"{API}/sales/orders/", {}, format="json")
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.data["detail"], "Your role can view this module but not change it.")
        # Purchase can view inventory but not record product movements
        self.assertEqual(client_for(make_user("purchase")).post(f"{API}/inventory/movements/", {}, format="json").status_code, 403)
        # Inventory can view purchases but not record them
        self.assertEqual(client_for(make_user("inventory")).post(f"{API}/purchase/purchases/", {}, format="json").status_code, 403)

    def test_retired_production_endpoints_are_gone(self):
        api = client_for(make_user("admin"))
        for path in ("/production/plan/", "/production/batches/", "/supply-chain/purchase-orders/", "/supply-chain/suppliers/"):
            self.assertEqual(api.get(API + path).status_code, 404, path)

    def test_offers_need_marketing_write(self):
        self.assertEqual(client_for(make_user("sales")).post(f"{API}/customers/offers/", {}, format="json").status_code, 403)
        # Marketing may send offers (here it fails validation instead of permission)
        self.assertEqual(client_for(make_user("marketing")).post(f"{API}/customers/offers/", {}, format="json").status_code, 400)

    def test_reports_are_for_managers(self):
        api = client_for(make_user("management"))
        self.assertEqual(api.get(f"{API}/reports/preview/?type=sales").status_code, 200)
        self.assertEqual(api.get(f"{API}/reports/preview/?type=finance").status_code, 400)  # Accounts report retired
        sales = client_for(make_user("sales"))
        self.assertEqual(sales.get(f"{API}/reports/preview/?type=sales").status_code, 403)
        self.assertEqual(sales.get(f"{API}/reports/export/?type=sales&format=csv").status_code, 403)

    def test_team_roles_see_only_their_own_work_and_attendance(self):
        """e.g. Marketing: Marketing, Customers (to send offers) and Attendance; no Dashboard, Sales, Reports or AI."""
        api = client_for(make_user("marketing"))
        for path in ("/dashboard/summary/", "/dashboard/sales-trend/", "/sales/overview/", "/reports/", "/ai/status/",
                     "/inventory/overview/", "/purchase/purchases/"):
            self.assertEqual(api.get(API + path).status_code, 403, path)
        for path in ("/marketing/overview/", "/customers/", "/attendance/status/"):
            self.assertEqual(api.get(API + path).status_code, 200, path)

    def test_only_admin_manages_admins(self):
        admin = make_user("admin")
        mgmt = client_for(make_user("management"))
        res = mgmt.patch(f"{API}/settings/users/{admin.id}/", {"role": "sales"}, format="json")
        self.assertEqual(res.status_code, 403)
        res = mgmt.post(f"{API}/settings/users/", {"name": "X", "email": "x@test.invalid", "role": "admin"}, format="json")
        self.assertEqual(res.status_code, 403)

    def test_cannot_change_own_role_or_deactivate_self(self):
        me = make_user("admin")
        api = client_for(me)
        self.assertEqual(api.patch(f"{API}/settings/users/{me.id}/", {"role": "sales"}, format="json").status_code, 400)
        self.assertEqual(api.patch(f"{API}/settings/users/{me.id}/", {"status": "Inactive"}, format="json").status_code, 400)

    def test_notifications_are_private(self):
        from apps.system.models import Notification

        a, b = make_user("sales", username="a"), make_user("sales", username="b")
        n = Notification.objects.create(user=a, title="TEST")
        self.assertEqual(client_for(b).post(f"{API}/notifications/{n.id}/read/").status_code, 404)
        self.assertEqual(client_for(a).post(f"{API}/notifications/{n.id}/read/").status_code, 200)
