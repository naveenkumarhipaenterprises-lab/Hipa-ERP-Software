"""Every read endpoint on an empty database answers 200 with empty / zero / null values, never invented figures."""
from django.test import TestCase, override_settings

from .helpers import API, client_for, make_user

LIST_ENDPOINTS = [
    "/settings/users/", "/settings/security/login-activity/", "/settings/audit-logs/",
    "/sales/orders/", "/inventory/items/", "/inventory/movements/", "/customers/", "/purchase/purchases/",
    "/purchase/suppliers/", "/purchase/raw-materials/", "/purchase/goods-receipts/", "/purchase/returns/", "/purchase/payments/",
    "/marketing/campaigns/", "/marketing/posts/?status=scheduled", "/supply-chain/shipments/",
    "/quality/tests/", "/finance/transactions/", "/reports/",
]

ARRAY_ENDPOINTS = [
    "/dashboard/sales-trend/", "/sales/trend/", "/customers/growth/", "/marketing/performance/", "/marketing/audience/",
    "/supply-chain/supplier-performance/", "/purchase/trend/", "/quality/trend/", "/quality/standards/", "/finance/revenue-expenses/",
    "/finance/cash-flow/",
]

RANGES = ["this_month", "last_month", "last_3_months", "this_year"]


def all_numbers(value):
    """Every number inside a payload (for checking nothing non-zero is invented)."""
    if isinstance(value, bool):
        return []
    if isinstance(value, (int, float)):
        return [value]
    if isinstance(value, dict):
        return [n for v in value.values() for n in all_numbers(v)]
    if isinstance(value, list):
        return [n for v in value for n in all_numbers(v)]
    return []


# Independent of the local .env: no AI key and no SMTP server in these tests
@override_settings(GEMINI_API_KEY="", EMAIL_HOST="", EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class EmptyDatabaseTests(TestCase):
    def setUp(self):
        self.api = client_for(make_user("admin"))

    def get(self, path):
        res = self.api.get(API + path)
        self.assertEqual(res.status_code, 200, f"{path}: {res.status_code} {getattr(res, 'data', '')}")
        return res.data

    def test_paginated_lists_are_empty(self):
        for path in LIST_ENDPOINTS:
            data = self.get(path)
            expected = 1 if path == "/settings/users/" else 0  # the signed-in admin exists
            self.assertEqual(data["count"], expected, path)
            self.assertIn("next", data)
            self.assertIn("previous", data)
            self.assertEqual(len(data["results"]), expected, path)

    def test_series_are_empty_arrays(self):
        for path in ARRAY_ENDPOINTS:
            self.assertEqual(self.get(path), [], path)

    def test_overviews_have_no_invented_numbers(self):
        for rng in RANGES:
            for path in ["/dashboard/summary/", "/sales/overview/", "/inventory/overview/", "/customers/overview/",
                         "/marketing/overview/", "/purchase/overview/", "/supply-chain/overview/", "/quality/overview/",
                         "/finance/overview/",
                         "/reports/overview/"]:
                data = self.get(f"{path}?range={rng}")
                self.assertTrue(all(n == 0 for n in all_numbers(data)), f"{path}?range={rng} -> {data}")

    def test_dashboard_sections_empty(self):
        d = self.get("/dashboard/summary/")
        for key in ("product_contribution", "order_status", "recent_orders", "low_stock", "top_customers", "upcoming"):
            self.assertEqual(d[key], [], key)
        self.assertEqual(d["kpis"]["total_sales"], {"value": 0})

    def test_options_endpoints(self):
        self.assertEqual(self.get("/sales/options/")["customers"], [])
        self.assertEqual(self.get("/inventory/options/")["items"], [])
        self.assertEqual(self.get("/purchase/options/")["suppliers"], [])
        self.assertEqual(self.get("/supply-chain/options/")["suppliers"], [])
        self.assertEqual(self.get("/quality/options/")["pending_receipts"], [])
        self.assertEqual(self.get("/customers/options/")["offer_channels"], [])  # no e-mail configured
        self.assertTrue(self.get("/finance/options/")["expense_categories"])
        self.assertTrue(self.get("/marketing/options/")["platforms"])
        self.assertTrue(self.get("/settings/options/")["roles"])

    def test_settings_start_blank(self):
        self.assertEqual(self.get("/settings/general/")["company_name"], "")
        self.assertEqual(self.get("/settings/company/")["legal_name"], "")
        b = self.get("/settings/backup/")
        self.assertIsNone(b["last_backup_at"])
        self.assertFalse(b["automatic"])
        self.assertEqual(self.get("/settings/security/"), {"two_factor_enabled": False})
        self.assertTrue(all(p["enabled"] for p in self.get("/settings/notifications/")))
        self.assertEqual([i["connected"] for i in self.get("/settings/integrations/")], [False, False])

    def test_finance_budget_null(self):
        self.assertIsNone(self.get("/finance/overview/")["budget"])

    def test_notifications_empty(self):
        d = self.get("/notifications/")
        self.assertEqual(d["results"], [])
        self.assertEqual(d["unread_count"], 0)

    def test_ai_not_connected(self):
        status = self.get("/ai/status/")
        self.assertFalse(status["available"])
        self.assertEqual(self.get("/ai/home/"), {"suggestions": [], "insights": [], "conversations": []})
        res = self.api.post(f"{API}/ai/chat/", {"message": "hello"}, format="json")
        self.assertEqual(res.status_code, 503)

    def test_report_previews_are_empty(self):
        for t in ("sales", "quotations", "inventory", "purchase", "marketing", "customers", "supply_chain", "quality", "finance",
                  "ai_business"):
            d = self.get(f"/reports/preview/?type={t}&range=this_month")
            self.assertIsNone(d["chart"], t)
            self.assertIsNone(d["breakdown"], t)
            self.assertEqual(d["table"]["rows"], [], t)

    def test_csv_exports_have_only_headers(self):
        for path in ("/inventory/items/export/", "/customers/export/", "/customers/import/template/",
                     "/quality/report/"):
            res = self.api.get(API + path)
            self.assertEqual(res.status_code, 200, path)
            self.assertIn("attachment; filename=", res["Content-Disposition"])
            lines = res.content.decode("utf-8-sig").strip().splitlines()
            self.assertEqual(len(lines), 1, path)

    def test_report_exports_all_formats(self):
        for fmt, magic in (("csv", b"\xef\xbb\xbf"), ("xlsx", b"PK"), ("pdf", b"%PDF")):
            res = self.api.get(f"{API}/reports/export/?type=sales&range=this_month&format={fmt}")
            self.assertEqual(res.status_code, 200, fmt)
            self.assertTrue(res.content.startswith(magic), fmt)

    def test_analytics_stores_nothing_without_data(self):
        from io import StringIO

        from django.core.management import call_command

        from apps.ai_assistant.models import AnalyticsRun, Insight

        out = StringIO()
        call_command("run_analytics", stdout=out)
        self.assertEqual(Insight.objects.count(), 0)
        summary = AnalyticsRun.objects.get().summary
        self.assertTrue(all(part["status"] == "insufficient_data" for part in summary.values()), summary)

    def test_invalid_range_is_400(self):
        res = self.api.get(f"{API}/sales/overview/?range=forever")
        self.assertEqual(res.status_code, 400)
        self.assertIn("range", res.data)

    def test_unknown_endpoint_is_404(self):
        self.assertEqual(self.api.get(f"{API}/nope/").status_code, 404)
