"""Purchase AI recommendations, daily alerts, dashboard purchase sections and new reports (TEST records only)."""
import importlib
from datetime import timedelta
from decimal import Decimal
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.test import TestCase, override_settings

from apps.ai_assistant.models import Insight
from apps.core.periods import today
from apps.customers.models import Customer
from apps.inventory.models import Product
from apps.purchase.models import GoodsReceipt, MaterialMovement, Purchase, RawMaterial, Supplier, SupplierPayment
from apps.purchase.services import move_material
from apps.sales.models import SalesInvoice, SalesOrder
from apps.system.models import Notification

from .helpers import API, client_for, make_user

real_import = importlib.import_module


def blocked(name, *args, **kwargs):
    if name.startswith("ml."):
        raise ImportError("blocked by Application Control policy")
    return real_import(name, *args, **kwargs)


@override_settings(GEMINI_API_KEY="")
class PurchaseRecommendationTests(TestCase):
    def setUp(self):
        self.admin = make_user("admin")
        self.api = client_for(self.admin)
        self.supplier = Supplier.objects.create(name="TEST Farms", city="Erode")
        self.cheap = Supplier.objects.create(name="TEST Cheap Farms", city="Salem")

    def material_with_usage(self, name="TEST Raw Turmeric", days=20, per_day=10, stock_after=40, reorder=50):
        m = RawMaterial.objects.create(name=name, category="whole_spice", unit="kg", reorder_level=reorder, supplier=self.supplier)
        move_material(m, "in", per_day * days + stock_after, source=MaterialMovement.Source.OPENING, date=today() - timedelta(days=days + 1))
        for d in range(days, 0, -1):
            move_material(m, "out", per_day, source=MaterialMovement.Source.USAGE, date=today() - timedelta(days=d))
        return m

    def bought(self, material, supplier, price, days_ago, received_after):
        p = Purchase.objects.create(supplier=supplier, material=material, unit="kg", quantity=Decimal("10"), unit_price=Decimal(price),
                                    purchase_date=today() - timedelta(days=days_ago), status=Purchase.Status.RECEIVED,
                                    received_quantity=Decimal("10"))
        GoodsReceipt.objects.create(purchase=p, received_date=p.purchase_date + timedelta(days=received_after), received_quantity=10,
                                    accepted_quantity=10)
        return p

    def test_empty_database_says_insufficient(self):
        data = self.api.get(f"{API}/purchase/recommendations/").data
        self.assertEqual((data["status"], data["message"], data["rows"]), ("insufficient_data", "Insufficient data for AI recommendation.", []))
        self.assertEqual(data["summary"], {"items": 0, "high": 0, "medium": 0, "low": 0, "estimated_cost": None})
        csv = self.api.get(f"{API}/purchase/recommendations/export/")
        self.assertEqual(len(csv.content.decode("utf-8-sig").strip().splitlines()), 1)
        self.assertEqual(self.api.get(f"{API}/purchase/recommendations/?horizon=99").status_code, 400)

    def test_material_recommendation_from_usage_lead_time_and_prices(self):
        m = self.material_with_usage()
        self.bought(m, self.supplier, "120", 60, 6)
        self.bought(m, self.cheap, "110", 40, 4)
        self.bought(m, self.supplier, "132", 30, 5)
        RawMaterial.objects.filter(pk=m.pk).update(current_stock=40)  # receipts above were history only
        Purchase.objects.create(supplier=self.supplier, material=m, unit="kg", quantity=Decimal("25"), unit_price=Decimal("130"),
                                purchase_date=today())  # still to be received
        data = self.api.get(f"{API}/purchase/recommendations/?horizon=30").data
        self.assertEqual(data["status"], "ok")
        row = data["rows"][0]
        self.assertEqual((row["item"], row["avg_daily_demand"], row["lead_time_days"], row["on_order"]), ("TEST Raw Turmeric", 10.0, 5.0, 25.0))
        self.assertEqual(row["safety_stock"], 0.0)  # steady usage: no variation
        self.assertEqual(row["reorder_point"], 50.0)  # 10/day x 5 days
        self.assertEqual(row["recommended_quantity"], 235.0)  # 300 - 40 - 25
        self.assertEqual((row["priority"], row["days_of_cover"]), ("HIGH", 4.0))
        self.assertEqual((row["last_price"], row["best_supplier"]), (130.0, "TEST Cheap Farms"))
        self.assertEqual(row["estimated_cost"], 30550.0)
        self.assertEqual(data["summary"]["high"], 1)

    def test_material_without_lead_time_uses_reorder_level(self):
        self.material_with_usage(stock_after=400, reorder=50)
        row = self.api.get(f"{API}/purchase/recommendations/").data["rows"][0]
        self.assertIsNone(row["lead_time_days"])
        self.assertEqual((row["reorder_point"], row["priority"], row["recommended_quantity"]), (50.0, "LOW", 0.0))
        self.assertTrue(row["notes"])

    def test_short_history_is_listed_not_estimated(self):
        self.material_with_usage(days=5)
        data = self.api.get(f"{API}/purchase/recommendations/").data
        self.assertEqual(data["status"], "insufficient_data")
        self.assertIn("days of recorded usage", data["insufficient"][0]["reason"])

    def test_product_recommendation_from_sales_forecast(self):
        p = Product.objects.create(name="TEST Garam Masala", price_per_kg=Decimal("400"))
        c = Customer.objects.create(name="TEST Shop", type="retailer", city="Erode")
        for week in range(8):
            o = SalesOrder.objects.create(customer=c, order_date=today() - timedelta(days=7 * week + 1))
            o.items.create(product=p, quantity_kg=Decimal("40"), unit_price=Decimal("400"))
            o.recalculate_total()
        row = self.api.get(f"{API}/purchase/recommendations/").data["rows"][0]
        self.assertEqual((row["item"], row["item_type"], row["demand_basis"]), ("TEST Garam Masala", "product", "sales forecast"))
        self.assertGreater(row["recommended_quantity"], 0)

    def test_blocked_analytics_is_503_and_dashboard_still_works(self):
        with mock.patch("importlib.import_module", side_effect=blocked):
            self.assertEqual(self.api.get(f"{API}/purchase/recommendations/").status_code, 503)
            self.assertEqual(self.api.get(f"{API}/dashboard/summary/").status_code, 200)

    def test_daily_analysis_stores_insights_for_dashboard_and_ai_report(self):
        m = self.material_with_usage()
        self.bought(m, self.supplier, "120", 30, 5)
        RawMaterial.objects.filter(pk=m.pk).update(current_stock=40)
        make_user("purchase")
        call_command("run_analytics", stdout=StringIO())
        insight = Insight.objects.get(kind="purchase")
        self.assertEqual(insight.module, "purchase")
        self.assertIn("TEST Raw Turmeric", insight.title)
        self.assertTrue(Notification.objects.filter(key="purchase_recommendations").exists())
        dash = self.api.get(f"{API}/dashboard/summary/").data
        self.assertEqual(dash["purchase_recommendations"][0]["title"], insight.title)
        report = self.api.get(f"{API}/reports/preview/?type=ai_business&range=this_month").data
        self.assertEqual(report["table"]["rows"][0]["title"], insight.title)
        # Team roles don't open Reports at all (Super Admin and Management only)
        res = client_for(make_user("sales")).get(f"{API}/reports/preview/?type=ai_business&range=this_month")
        self.assertEqual(res.status_code, 403)


class DueAlertTests(TestCase):
    def test_alerts_are_sent_once(self):
        make_user("admin")
        s = Supplier.objects.create(name="TEST Farms", city="Erode")
        m = RawMaterial.objects.create(name="TEST Pepper", category="whole_spice", unit="kg")
        Purchase.objects.create(supplier=s, material=m, unit="kg", quantity=5, unit_price=100, purchase_date=today() - timedelta(days=9),
                                expected_receipt_date=today() - timedelta(days=2))
        SupplierPayment.objects.create(supplier=s, amount=500, payment_date=today() + timedelta(days=1), payment_method="upi")
        c = Customer.objects.create(name="TEST Shop", type="retailer", city="Erode")
        inv = SalesInvoice.objects.create(customer=c, customer_name="TEST Shop", invoice_date=today() - timedelta(days=40),
                                          due_date=today() - timedelta(days=10))
        inv.items.create(product=Product.objects.create(name="TEST Product", price_per_kg=10), quantity_kg=1, unit_price=10)
        inv.recalculate_total()
        out = StringIO()
        call_command("send_due_alerts", stdout=out)
        self.assertIn("3 alert(s)", out.getvalue())
        for key in ("supplier_delays", "supplier_payment_due", "invoice_overdue"):
            self.assertTrue(Notification.objects.filter(key=key).exists(), key)
        out = StringIO()
        call_command("send_due_alerts", stdout=out)
        self.assertIn("0 alert(s)", out.getvalue())


class DashboardAndReportTests(TestCase):
    def setUp(self):
        self.api = client_for(make_user("admin"))

    def test_dashboard_purchase_sections(self):
        d = self.api.get(f"{API}/dashboard/summary/").data
        for key in ("purchase_trend", "purchase_recommendations", "supplier_performance", "low_stock_materials"):
            self.assertEqual(d[key], [], key)
        self.assertEqual(d["kpis"]["purchase_value"], {"value": 0})
        s = Supplier.objects.create(name="TEST Farms", city="Erode")
        m = RawMaterial.objects.create(name="TEST Pepper", category="whole_spice", unit="kg", reorder_level=10)
        Purchase.objects.create(supplier=s, material=m, unit="kg", quantity=5, unit_price=100, purchase_date=today())
        d = self.api.get(f"{API}/dashboard/summary/").data
        self.assertEqual((d["kpis"]["purchase_value"]["value"], d["kpis"]["outstanding_supplier_payments"]["value"]), (500, 500))
        self.assertEqual(d["purchase_overview"]["pending"], 1)
        self.assertEqual(d["low_stock_materials"][0]["material"], "TEST Pepper")
        self.assertTrue(d["purchase_trend"])
        self.assertEqual(client_for(make_user("sales")).get(f"{API}/dashboard/summary/").status_code, 403)

    def test_quotation_report_and_sales_summary(self):
        p = Product.objects.create(name="TEST Product", price_per_kg=Decimal("100"))
        c = Customer.objects.create(name="TEST Shop", type="retailer", city="Erode")
        for status in ("draft", "accepted", "rejected"):
            q = self.api.post(f"{API}/sales/quotations/", {"customer_id": c.id, "valid_until": (today() + timedelta(days=5)).isoformat(),
                                                           "items": [{"product_id": p.id, "quantity_kg": 1}]}, format="json").data
            if status != "draft":
                self.api.post(f"{API}/sales/quotations/{q['id']}/status/", {"status": status}, format="json")
        self.api.post(f"{API}/sales/quotations/{q['id']}/status/", {"status": "draft"}, format="json")  # rejected -> draft
        self.api.post(f"{API}/inventory/movements/", {"item_id": p.id, "type": "in", "quantity_kg": 5}, format="json")
        accepted = self.api.get(f"{API}/sales/quotations/?status=accepted").data["results"][0]
        self.api.post(f"{API}/sales/quotations/{accepted['id']}/convert-to-order/", {}, format="json")
        summary = self.api.get(f"{API}/sales/overview/").data["quotations"]
        self.assertEqual((summary["count"], summary["draft"], summary["converted"], summary["value"]), (3, 2, 1, 300))
        self.assertEqual(summary["conversion_rate_pct"], 100.0)
        report = self.api.get(f"{API}/reports/preview/?type=quotations&range=this_month").data
        self.assertEqual(len(report["table"]["rows"]), 3)
        self.assertIn("conversion rate 100%", report["title"])
        res = self.api.get(f"{API}/reports/export/?type=quotations&range=this_month&format=pdf")
        self.assertTrue(res.content.startswith(b"%PDF"))
        self.assertEqual(client_for(make_user("inventory")).get(f"{API}/reports/preview/?type=quotations").status_code, 403)
