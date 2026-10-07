"""CRUD and business rules with real records (created inside the test database only)."""
import tempfile
from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.core.periods import today
from apps.inventory.models import Product
from apps.purchase.models import GoodsReceipt, Supplier
from apps.sales.models import SalesOrder
from apps.supply_chain.models import Shipment
from apps.system.models import AuditLog, Notification

from .helpers import API, client_for, make_user


class WorkflowTests(TestCase):
    def setUp(self):
        self.admin = make_user("admin")
        self.api = client_for(self.admin)

    def post(self, path, body, expected=201):
        res = self.api.post(API + path, body, format="json")
        self.assertEqual(res.status_code, expected, f"{path}: {res.data}")
        return res.data

    def product(self, name="TEST Turmeric", stock=100, price=250, min_kg=10, reorder=30):
        return self.post("/inventory/items/", {"product_name": name, "opening_stock_kg": stock, "price_per_kg": price,
                                               "min_stock_kg": min_kg, "reorder_level_kg": reorder})

    def customer(self, name="TEST Traders"):
        return self.post("/customers/", {"name": name, "type": "retailer", "city": "Erode", "phone": "98765 43210"})

    # --- Inventory ----------------------------------------------------------------
    def test_edit_product_details_and_switch_it_off(self):
        item, other = self.product(), self.product(name="TEST Chilli")
        path = f"{API}/inventory/items/{item['id']}/"
        res = self.api.patch(path, {"product_name": " TEST Turmeric Premium ", "price_per_kg": 280, "min_stock_kg": 15,
                                    "reorder_level_kg": 40}, format="json")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual((res.data["product"], res.data["price_per_kg"], res.data["min_stock_kg"], res.data["reorder_level_kg"]),
                         ("TEST Turmeric Premium", 280, 15, 40))
        self.assertEqual(res.data["stock_kg"], 100)  # stock is not editable here
        self.assertTrue(AuditLog.objects.filter(action="Edited inventory item").exists())
        # Validation: duplicate name, reorder below minimum, stock can't be set
        self.assertIn("product_name", self.api.patch(path, {"product_name": "test chilli"}, format="json").data)
        self.assertIn("reorder_level_kg", self.api.patch(path, {"min_stock_kg": 50}, format="json").data)
        self.api.patch(path, {"stock_kg": 5}, format="json")
        self.assertEqual(Product.objects.get(pk=item["id"]).stock_kg, 100)
        # Switched off: gone from the active list and from new orders, listed under inactive, can be switched back on
        self.assertFalse(self.api.patch(path, {"is_active": False}, format="json").data["is_active"])
        self.assertEqual([r["id"] for r in self.api.get(f"{API}/inventory/items/").data["results"]], [other["id"]])
        self.assertEqual([r["id"] for r in self.api.get(f"{API}/inventory/items/?active=false").data["results"]], [item["id"]])
        self.assertNotIn(item["id"], [p["id"] for p in self.api.get(f"{API}/sales/options/").data["products"]])
        self.assertTrue(self.api.patch(path, {"is_active": True}, format="json").data["is_active"])
        # Read-only roles can't edit
        self.assertEqual(client_for(make_user("purchase")).patch(path, {"price_per_kg": 1}, format="json").status_code, 403)

    def test_inventory_item_and_movements(self):
        item = self.product()
        self.assertEqual(item["stock_kg"], 100)
        self.assertEqual(item["status"], "In Stock")
        self.assertEqual(item["stock_value"], 25000)
        with self.captureOnCommitCallbacks(execute=True):
            self.post("/inventory/movements/", {"item_id": item["id"], "type": "out", "quantity_kg": 75, "note": "TEST"})
        row =self.api.get(f"{API}/inventory/items/").data["results"][0]
        self.assertEqual(row["stock_kg"], 25)
        self.assertEqual(row["status"], "Low Stock")
        # Low-stock notification went to inventory users
        self.assertTrue(Notification.objects.filter(key="low_stock").exists())
        # Can't take out more than is in stock
        err = self.post("/inventory/movements/", {"item_id": item["id"], "type": "out", "quantity_kg": 26}, expected=400)
        self.assertIn("quantity_kg", err)
        # Filter by status label or value
        self.assertEqual(self.api.get(f"{API}/inventory/items/?status=Low Stock").data["count"], 1)
        self.assertEqual(self.api.get(f"{API}/inventory/items/?status=in_stock").data["count"], 0)
        ov = self.api.get(f"{API}/inventory/overview/").data
        self.assertEqual(ov["kpis"]["total_stock_kg"]["value"], 25)
        self.assertEqual(ov["low_stock"][0]["severity"], "low")
        self.assertEqual(len(ov["movements"]), 2)

    def test_inventory_validation(self):
        self.product()
        err = self.post("/inventory/items/", {"product_name": "test turmeric", "price_per_kg": 1}, expected=400)
        self.assertIn("product_name", err)
        err = self.post("/inventory/items/", {"product_name": "X", "price_per_kg": -1, "min_stock_kg": 50, "reorder_level_kg": 10}, expected=400)
        self.assertIn("price_per_kg", err)
        err = self.post("/inventory/movements/", {"item_id": 999, "type": "sideways", "quantity_kg": 0}, expected=400)
        self.assertEqual(set(err), {"item_id", "type", "quantity_kg"})

    # --- Customers & sales ----------------------------------------------------------
    def test_customer_crud_and_duplicates(self):
        c = self.customer()
        self.assertEqual(c["type_label"], "Retailer")
        self.post("/customers/", {"name": "test traders", "type": "retailer", "city": "erode"}, expected=400)
        res = self.api.patch(f"{API}/customers/{c['id']}/", {"status": "Inactive", "type": "Wholesaler"}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["status"], "Inactive")
        self.assertEqual(res.data["type"], "wholesaler")
        self.assertEqual(self.api.get(f"{API}/customers/?status=active").data["count"], 0)
        self.assertEqual(self.api.get(f"{API}/customers/?search=trad").data["count"], 1)

    def test_customer_import(self):
        csv_bytes = ("name,type,contact_person,phone,email,city,address\n"
                     "TEST A,retailer,,,,Salem,\n"
                     "TEST B,Distributor,,,a@test.invalid,Erode,\n"
                     "TEST C,alien,,,,Erode,\n").encode()
        res = self.api.post(f"{API}/customers/import/", {"file": SimpleUploadedFile("c.csv", csv_bytes, "text/csv")}, format="multipart")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["created"], 2)
        self.assertEqual(res.data["errors"][0]["row"], 4)
        # Importing again updates instead of duplicating
        res = self.api.post(f"{API}/customers/import/", {"file": SimpleUploadedFile("c.csv", csv_bytes, "text/csv")}, format="multipart")
        self.assertEqual((res.data["created"], res.data["updated"]), (0, 2))

    def test_sales_order_deducts_stock_and_cancel_returns_it(self):
        p, c = self.product(), self.customer()
        order = self.post("/sales/orders/", {"customer_id": c["id"], "product_id": p["id"], "quantity_kg": 10,
                                             "order_date": today().isoformat()})
        self.assertTrue(order["order_number"].startswith("SO-"))
        self.assertEqual(order["amount"], 2500)
        self.assertEqual(order["status"], "Pending")
        self.assertTrue(order["can_cancel"])
        self.assertEqual(Product.objects.get(pk=p["id"]).stock_kg, 90)

        ov = self.api.get(f"{API}/sales/overview/").data
        self.assertEqual(ov["kpis"]["total_sales"]["value"], 2500)
        self.assertEqual(ov["kpis"]["quantity_sold_kg"]["value"], 10)
        self.assertEqual(ov["products"][0]["avg_price"], 250)
        self.assertEqual(ov["top_customers"][0]["amount"], 2500)
        dash = self.api.get(f"{API}/dashboard/summary/").data
        self.assertEqual(dash["kpis"]["total_orders"]["value"], 1)
        self.assertEqual(dash["recent_orders"][0]["customer"], "TEST Traders")
        self.assertTrue(self.api.get(f"{API}/dashboard/sales-trend/").data)
        cust = self.api.get(f"{API}/customers/").data["results"][0]
        self.assertEqual((cust["total_orders"], cust["total_purchase"]), (1, 2500))

        cancelled = self.post(f"/sales/orders/{order['id']}/cancel/", {}, expected=200)
        self.assertEqual(cancelled["status"], "Cancelled")
        self.assertEqual(Product.objects.get(pk=p["id"]).stock_kg, 100)
        self.post(f"/sales/orders/{order['id']}/cancel/", {}, expected=400)
        self.assertEqual(self.api.get(f"{API}/sales/overview/").data["kpis"]["total_sales"]["value"], 0)
        self.assertTrue(AuditLog.objects.filter(action="Cancelled sales order").exists())

    def test_sales_order_status_moves_forward_one_step_at_a_time(self):
        p, c = self.product(), self.customer()
        order = self.post("/sales/orders/", {"customer_id": c["id"], "product_id": p["id"], "quantity_kg": 5,
                                             "order_date": today().isoformat()})
        self.assertEqual(order["next_status"], {"value": "processing", "label": "Processing"})
        path = f"/sales/orders/{order['id']}/status/"
        self.assertIn("status", self.post(path, {"status": "delivered"}, expected=400))  # can't skip a step
        for step, label in (("processing", "Processing"), ("in_transit", "In Transit"), ("delivered", "Delivered")):
            order = self.post(path, {"status": step}, expected=200)
            self.assertEqual(order["status"], label)
        self.assertIsNone(order["next_status"])
        self.assertFalse(order["can_cancel"])
        self.assertIn("status", self.post(path, {"status": "processing"}, expected=400))  # delivered is final
        self.assertEqual(Product.objects.get(pk=p["id"]).stock_kg, 95)  # stock went out with the order only
        self.assertTrue(AuditLog.objects.filter(action="Marked sales order delivered").exists())
        # Cancelled orders don't move; read-only roles can't move orders
        other = self.post("/sales/orders/", {"customer_id": c["id"], "product_id": p["id"], "quantity_kg": 1,
                                             "order_date": today().isoformat()})
        self.post(f"/sales/orders/{other['id']}/cancel/", {}, expected=200)
        self.post(f"/sales/orders/{other['id']}/status/", {"status": "processing"}, expected=400)
        res = client_for(make_user("finance")).post(f"{API}/sales/orders/{order['id']}/status/", {"status": "x"}, format="json")
        self.assertEqual(res.status_code, 403)

    def test_sales_order_validation(self):
        p, c = self.product(stock=5), self.customer()
        err = self.post("/sales/orders/", {"customer_id": c["id"], "product_id": p["id"], "quantity_kg": 6,
                                           "order_date": today().isoformat()}, expected=400)
        self.assertIn("quantity_kg", err)
        self.assertEqual(SalesOrder.objects.count(), 0)  # nothing half-saved
        err = self.post("/sales/orders/", {"customer_id": c["id"], "product_id": p["id"], "quantity_kg": 1,
                                           "order_date": (today() + timedelta(days=2)).isoformat()}, expected=400)
        self.assertIn("order_date", err)

    # --- Purchase receipt & quality ---------------------------------------------------
    def purchase_received(self, qty=50):
        s = self.post("/purchase/suppliers/", {"name": "TEST Farms", "city": "Erode"})
        m = self.post("/purchase/raw-materials/", {"name": "TEST Raw Turmeric", "category": "whole_spice", "unit": "kg",
                                                   "reorder_level": 100})
        p = self.post("/purchase/purchases/", {"supplier_id": s["id"], "material_id": m["id"], "quantity": qty, "unit_price": 120,
                                               "purchase_date": today().isoformat(), "expected_receipt_date": today().isoformat()})
        grn = self.post("/purchase/goods-receipts/", {"purchase_id": p["id"], "received_date": today().isoformat(),
                                                      "received_quantity": qty})
        return s, m, p, grn

    def test_goods_receipt_quality_test(self):
        _s, m, _p, grn = self.purchase_received()
        pending = self.api.get(f"{API}/quality/options/").data["pending_receipts"]
        self.assertEqual([g["id"] for g in pending], [grn["id"]])
        test = self.post("/quality/tests/", {"goods_receipt_id": grn["id"], "batch_number": "LOT-7", "test_date": today().isoformat(),
                                             "result": "pass", "parameters": "TEST moisture 8%"})
        self.assertEqual((test["result"], test["status"], test["product"], test["grn_number"]),
                         ("Pass", "Approved", "TEST Raw Turmeric", grn["grn_number"]))
        self.assertEqual(GoodsReceipt.objects.get(pk=grn["id"]).quality_status, "passed")
        self.assertEqual(self.api.get(f"{API}/quality/options/").data["pending_receipts"], [])
        ov = self.api.get(f"{API}/quality/overview/").data
        self.assertEqual(ov["kpis"]["pass_rate_pct"]["value"], 100.0)
        self.assertEqual(ov["kpis"]["batches_tested"]["value"], 1)
        self.assertIsNotNone(ov["kpis"]["avg_testing_hours"]["value"])
        self.assertEqual(ov["product_quality"][0]["name"], "TEST Raw Turmeric")
        self.assertEqual(self.api.get(f"{API}/quality/tests/?search=LOT-7").data["count"], 1)
        self.assertEqual(self.api.get(f"{API}/purchase/goods-receipts/{grn['id']}/").data["quality_tests"][0]["result"], "Pass")

    def test_failed_product_test_notifies(self):
        p = self.product()
        self.post("/quality/tests/", {"product_id": p["id"], "test_date": today().isoformat(), "result": "fail", "parameters": "TEST"})
        self.assertTrue(Notification.objects.filter(key="quality_failures").exists())
        err = self.post("/quality/tests/", {"test_date": today().isoformat(), "result": "pass", "parameters": "TEST"}, expected=400)
        self.assertIn("material_id", err)

    # --- Supply chain ------------------------------------------------------------------
    def test_supply_chain_uses_purchases_and_shipments(self):
        s, m, p, _grn = self.purchase_received()
        ov = self.api.get(f"{API}/supply-chain/overview/").data
        self.assertEqual(ov["kpis"]["pending_purchases"]["value"], 0)
        self.assertEqual(ov["kpis"]["procurement_cost"]["value"], 6000)
        self.assertEqual(ov["raw_materials"][0]["status"], "Reorder")  # 50 kg against a 100 kg reorder level
        from apps.supply_chain.services import record_delivery

        sh = Shipment.objects.create(supplier=Supplier.objects.get(pk=s["id"]), purchase_id=p["id"], material_id=m["id"],
                                     quantity=50, destination="Main warehouse", dispatched_on=today(), eta=today(),
                                     status="delivered", quality_passed=True)
        record_delivery(sh)
        sh.refresh_from_db()
        self.assertEqual(sh.delivered_on, today())
        perf = self.api.get(f"{API}/supply-chain/supplier-performance/").data
        self.assertEqual(perf[0]["on_time_pct"], 100.0)
        self.assertEqual(perf[0]["quality_pct"], 100.0)
        self.assertEqual(perf[0]["cost_efficiency_pct"], 100.0)
        rows = self.api.get(f"{API}/supply-chain/shipments/?search={p['purchase_number']}").data["results"]
        self.assertEqual(rows[0]["item"], "TEST Raw Turmeric")
        dash = self.api.get(f"{API}/dashboard/summary/").data
        self.assertEqual(dash["kpis"]["active_suppliers"]["value"], 1)

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix="hipa-test-media-"))
    def test_purchase_report(self):
        self.purchase_received()
        preview = self.api.get(f"{API}/reports/preview/?type=purchase&range=this_month").data
        self.assertEqual(preview["table"]["rows"][0]["total_amount"], 6000)
        self.assertEqual(preview["breakdown"]["data"][0]["name"], "TEST Farms")
        report = self.post("/reports/", {"type": "purchase", "range": "this_month", "format": "pdf"})
        self.assertEqual(report["status"], "Ready")

    # --- Finance -----------------------------------------------------------------------
    def test_finance_transactions_and_budget(self):
        self.post("/finance/transactions/", {"type": "income", "description": "TEST sale", "category": "product_sales",
                                             "amount": 1000, "date": today().isoformat()})
        self.post("/finance/transactions/", {"type": "expense", "description": "TEST power", "category": "Utilities",
                                             "amount": 400, "date": today().isoformat()})
        err = self.post("/finance/transactions/", {"type": "income", "description": "x", "category": "utilities",
                                                   "amount": 0, "date": "bad"}, expected=400)
        self.assertEqual(set(err), {"category", "amount", "date"})
        ov = self.api.get(f"{API}/finance/overview/").data
        self.assertEqual(ov["kpis"]["net_profit"]["value"], 600)
        self.assertEqual(ov["kpis"]["profit_margin_pct"]["value"], 60.0)
        budget = self.api.put(f"{API}/finance/budget/", {"revenue_target": 5000, "expense_limit": 2000}, format="json")
        self.assertEqual(budget.status_code, 200)
        self.assertEqual(budget.data["revenue"], {"actual": 1000, "target": 5000})
        self.assertTrue(self.api.get(f"{API}/finance/revenue-expenses/?granularity=quarterly").data)
        self.assertEqual(self.api.get(f"{API}/finance/transactions/?type=expense").data["count"], 1)

    # --- Marketing ---------------------------------------------------------------------
    def test_campaigns_and_posts(self):
        c = self.post("/marketing/campaigns/", {"name": "TEST Diwali", "platform": "instagram", "objective": "sales",
                                                "start_date": today().isoformat(), "end_date": (today() + timedelta(days=5)).isoformat(),
                                                "budget": 1000})
        self.assertEqual(c["status"], "Active")
        ended = self.post(f"/marketing/campaigns/{c['id']}/end/", {}, expected=200)
        self.assertEqual(ended["status"], "Completed")
        self.assertFalse(ended["can_end"])
        when = (timezone.now() + timedelta(days=1)).isoformat()
        self.post("/marketing/posts/", {"platform": "facebook", "scheduled_for": when, "caption": "TEST", "campaign_id": c["id"]})
        self.assertEqual(self.api.get(f"{API}/marketing/posts/?status=scheduled").data["count"], 1)
        self.post("/marketing/posts/", {"platform": "facebook", "scheduled_for": "2000-01-01T10:00:00", "caption": "TEST"}, expected=400)

    # --- Reports & settings -------------------------------------------------------------
    @override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix="hipa-test-media-"))
    def test_generate_and_download_report(self):
        p, c = self.product(), self.customer()
        self.post("/sales/orders/", {"customer_id": c["id"], "product_id": p["id"], "quantity_kg": 2, "order_date": today().isoformat()})
        preview = self.api.get(f"{API}/reports/preview/?type=sales&range=this_month").data
        self.assertEqual(len(preview["table"]["rows"]), 1)
        self.assertIsNotNone(preview["chart"])
        for fmt in ("pdf", "xlsx", "csv"):
            report = self.post("/reports/", {"type": "sales", "range": "this_month", "format": fmt})
            self.assertEqual(report["status"], "Ready")
            self.assertTrue(report["download_available"])
            res = self.api.get(f"{API}/reports/{report['id']}/download/")
            self.assertEqual(res.status_code, 200)
            self.assertIn(f".{fmt}", res["Content-Disposition"])
            b"".join(res.streaming_content)
        self.assertEqual(self.api.get(f"{API}/reports/").data["count"], 3)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_invite_and_update_user(self):
        from django.core import mail

        res = self.post("/settings/users/", {"name": "TEST Priya", "email": "priya@test.invalid", "role": "finance"})
        self.assertEqual(res["status"], "Invited")
        self.assertEqual(len(mail.outbox), 1)
        self.post("/settings/users/", {"name": "Dup", "email": "PRIYA@test.invalid", "role": "sales"}, expected=400)
        res = self.api.patch(f"{API}/settings/users/{res['id']}/", {"role": "sales", "status": "Inactive"}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual((res.data["role"], res.data["status"]), ("sales", "Inactive"))

    def test_settings_forms_validate_and_save(self):
        bad = self.api.put(f"{API}/settings/general/", {"company_name": "", "timezone": "Mars/Base"}, format="json")
        self.assertEqual(bad.status_code, 400)
        good = self.api.put(f"{API}/settings/general/", {"company_name": "HIPA MASALA", "timezone": "Asia/Kolkata",
                                                         "date_format": "DD/MM/YYYY", "time_format": "12h", "currency": "INR",
                                                         "language": "en"}, format="json")
        self.assertEqual(good.status_code, 200)
        self.assertEqual(self.api.get(f"{API}/settings/general/").data["company_name"], "HIPA MASALA")
        res = self.api.patch(f"{API}/settings/notifications/", {"key": "low_stock", "enabled": False}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(self.api.patch(f"{API}/settings/security/", {"two_factor_enabled": True}, format="json").status_code, 400)
        self.assertEqual(self.api.post(f"{API}/settings/integrations/email/connect/").status_code, 503)
        logs = self.api.get(f"{API}/settings/audit-logs/?search=general").data
        self.assertEqual(logs["count"], 1)

    def test_disabled_notification_kind_is_not_sent(self):
        make_user("inventory")
        self.api.patch(f"{API}/settings/notifications/", {"key": "low_stock", "enabled": False}, format="json")
        item = self.product(stock=50)
        with self.captureOnCommitCallbacks(execute=True):
            self.post("/inventory/movements/", {"item_id": item["id"], "type": "out", "quantity_kg": 45})
        self.assertFalse(Notification.objects.filter(key="low_stock").exists())


class CorsTests(TestCase):
    def test_frontend_origin_allowed_and_download_header_exposed(self):
        res = self.client.options(f"{API}/auth/login/", HTTP_ORIGIN="http://localhost:5173",
                                  HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST")
        self.assertEqual(res["Access-Control-Allow-Origin"], "http://localhost:5173")
        res = self.client.get(f"{API}/auth/me/", HTTP_ORIGIN="http://localhost:5173")
        self.assertIn("Content-Disposition", res["Access-Control-Expose-Headers"])

    def test_other_origins_not_allowed(self):
        res = self.client.options(f"{API}/auth/login/", HTTP_ORIGIN="http://evil.example",
                                  HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST")
        self.assertNotIn("Access-Control-Allow-Origin", res)
