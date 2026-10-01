"""Purchase module: suppliers, raw materials, purchases, goods receipts, returns and supplier payments (TEST records only)."""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase

from apps.core.periods import today
from apps.inventory.models import Product
from apps.purchase.models import RawMaterial
from apps.system.models import Notification

from .helpers import API, client_for, make_user
from .test_empty_db import all_numbers


class PurchaseWorkflowTests(TestCase):
    def setUp(self):
        self.api = client_for(make_user("admin"))

    def call(self, method, path, body=None, expected=200):
        res = getattr(self.api, method)(API + "/purchase" + path, body or {}, format="json")
        self.assertEqual(res.status_code, expected, f"{method.upper()} {path}: {getattr(res, 'data', '')}")
        return res.data

    def post(self, path, body, expected=201):
        return self.call("post", path, body, expected)

    def supplier(self, name="TEST Spice Farms", **extra):
        return self.post("/suppliers/", {"name": name, "city": "Erode", "state": "Tamil Nadu", "gstin": "33abcde1234f1z5",
                                         "payment_terms": "Net 30", "credit_days": 30, **extra})

    def material(self, name="TEST Raw Turmeric", **extra):
        body = {"name": name, "category": "whole_spice", "unit": "kg", "minimum_stock": 20, "reorder_level": 50, **extra}
        return self.post("/raw-materials/", body)

    def purchase(self, supplier, material, qty=100, price=120, **extra):
        return self.post("/purchases/", {"supplier_id": supplier["id"], "item_type": "material", "material_id": material["id"],
                                         "quantity": qty, "unit_price": price, "discount_pct": 5, "gst_pct": 5,
                                         "purchase_date": today().isoformat(), **extra})

    # --- Empty database ----------------------------------------------------------------
    def test_empty_endpoints(self):
        for path in ("/suppliers/", "/raw-materials/", "/material-movements/", "/purchases/", "/goods-receipts/", "/returns/", "/payments/"):
            data = self.call("get", path)
            self.assertEqual((data["count"], data["results"]), (0, []), path)
        for rng in ("this_month", "last_month", "last_3_months", "this_year"):
            ov = self.call("get", f"/overview/?range={rng}")
            self.assertTrue(all(n == 0 for n in all_numbers(ov)), ov)
            self.assertEqual(ov["top_materials"], [])
            self.assertEqual(ov["supplier_performance"], [])
            self.assertEqual(ov["insights"], {})
        self.assertEqual(self.call("get", "/trend/"), [])
        opts = self.call("get", "/options/")
        self.assertEqual((opts["suppliers"], opts["materials"], opts["purchases"]), ([], [], []))
        self.assertTrue(opts["units"] and opts["payment_methods"])

    # --- Suppliers ---------------------------------------------------------------------
    def test_supplier_crud_search_and_delete_rules(self):
        s = self.supplier()
        self.assertTrue(s["supplier_code"].startswith("SUP-"))
        self.assertEqual((s["gstin"], s["status"]), ("33ABCDE1234F1Z5", "Active"))
        err = self.post("/suppliers/", {"name": "test spice farms", "city": "Salem", "gstin": "BAD"}, expected=400)
        self.assertEqual(set(err), {"name", "gstin"})
        self.supplier("TEST Cardamom Estate", city="Idukki", state="Kerala")
        self.assertEqual(self.call("get", "/suppliers/?search=cardamom")["count"], 1)
        self.assertEqual(self.call("get", "/suppliers/?state=kerala")["count"], 1)
        self.assertEqual(self.call("get", "/suppliers/?ordering=-name")["results"][0]["name"], "TEST Spice Farms")
        self.call("get", "/suppliers/?ordering=password", expected=400)
        updated = self.call("patch", f"/suppliers/{s['id']}/", {"status": "Inactive", "phone": "98765 43210"})
        self.assertEqual((updated["status"], updated["phone"]), ("Inactive", "9876543210"))
        self.assertEqual(self.call("get", "/suppliers/?status=active")["count"], 1)
        # A supplier with purchases can only be deactivated
        self.call("patch", f"/suppliers/{s['id']}/", {"status": "active"})
        self.purchase(s, self.material())
        self.call("delete", f"/suppliers/{s['id']}/", expected=409)
        other = self.supplier("TEST Unused")
        self.call("delete", f"/suppliers/{other['id']}/", expected=204)

    # --- Raw materials -----------------------------------------------------------------
    def test_material_with_opening_stock_and_usage(self):
        m = self.material(opening_stock=60, purchase_price=110)
        self.assertTrue(m["material_code"].startswith("RM-"))
        self.assertEqual((m["current_stock"], m["stock_status"], m["category_label"]), (60, "In Stock", "Whole Spices"))
        err = self.post("/raw-materials/", {"name": "X", "category": "rocks", "unit": "kg"}, expected=400)
        self.assertEqual(set(err), {"category"})
        err = self.post("/raw-materials/", {"name": "X", "category": "Seeds", "minimum_stock": 10, "reorder_level": 5}, expected=400)
        self.assertEqual(set(err), {"reorder_level"})
        self.post("/material-movements/", {"material_id": m["id"], "type": "out", "quantity": 15, "note": "TEST grinding"})
        row = self.call("get", f"/raw-materials/{m['id']}/")
        self.assertEqual((row["current_stock"], row["stock_status"]), (45, "Reorder"))
        self.assertEqual(row["movements"][0]["source"], "Used")
        err = self.post("/material-movements/", {"material_id": m["id"], "type": "out", "quantity": 46}, expected=400)
        self.assertIn("quantity", err)
        self.assertEqual(self.call("get", "/raw-materials/?stock_status=low")["count"], 1)
        # Unit is locked once stock exists
        self.assertIn("unit", self.call("patch", f"/raw-materials/{m['id']}/", {"unit": "g"}, expected=400))

    # --- Purchases, GRN, returns, payments ---------------------------------------------------
    def test_purchase_totals_receipt_return_and_payments(self):
        s, m = self.supplier(), self.material()
        p = self.purchase(s, m)  # 100 kg x 120 = 12000, -5% = 11400, +5% GST = 11970
        self.assertTrue(p["purchase_number"].startswith("PUR-"))
        self.assertEqual((p["subtotal"], p["discount_amount"], p["gst_amount"], p["total_amount"]), (12000, 600, 570, 11970))
        self.assertEqual((p["status"], p["payment_status"], p["unit"]), ("Pending", "Pending", "kg"))
        self.assertEqual(p["payment_due_date"], today() + timedelta(days=30))  # from the supplier's credit days
        self.assertTrue(p["can_edit_all"])

        edited = self.call("patch", f"/purchases/{p['id']}/", {"quantity": 110})
        self.assertEqual(edited["total_amount"], 13167)
        self.call("patch", f"/purchases/{p['id']}/", {"quantity": 100})

        # Goods receipt: 60 received, 5 damaged -> 55 accepted into stock
        with self.captureOnCommitCallbacks(execute=True):
            grn = self.post("/goods-receipts/", {"purchase_id": p["id"], "received_date": today().isoformat(),
                                                 "received_quantity": 60, "damaged_quantity": 5})
        self.assertTrue(grn["grn_number"].startswith("GRN-"))
        self.assertEqual((grn["accepted_quantity"], grn["quality_status"]), (55, "Pending Inspection"))
        self.assertEqual(RawMaterial.objects.get(pk=m["id"]).current_stock, 55)
        self.assertTrue(Notification.objects.filter(key="goods_receipt_issues").exists())
        p = self.call("get", f"/purchases/{p['id']}/")
        self.assertEqual((p["status"], p["received_quantity"], p["pending_quantity"]), ("Partially Received", 55, 45))
        self.assertFalse(p["can_cancel"])
        self.assertIn("quantity", self.call("patch", f"/purchases/{p['id']}/", {"quantity": 1}, expected=400))
        err = self.post("/goods-receipts/", {"purchase_id": p["id"], "received_date": today().isoformat(),
                                             "received_quantity": 50}, expected=400)
        self.assertIn("accepted_quantity", err)  # only 45 left to receive
        self.post("/goods-receipts/", {"purchase_id": p["id"], "received_date": today().isoformat(), "received_quantity": 45,
                                       "quality_status": "passed"})
        self.assertEqual(self.call("get", f"/purchases/{p['id']}/")["status"], "Received")

        # Return 10 kg: stock goes out, and once completed the payable drops by its value
        ret = self.post("/returns/", {"purchase_id": p["id"], "quantity": 10, "return_date": today().isoformat(), "reason": "quality"})
        self.assertEqual((ret["amount"], ret["status"], ret["supplier"]), (1197, "Pending", "TEST Spice Farms"))
        self.assertEqual(RawMaterial.objects.get(pk=m["id"]).current_stock, 90)
        self.call("patch", f"/returns/{ret['id']}/", {"status": "Completed"})
        self.call("patch", f"/returns/{ret['id']}/", {"status": "Cancelled"}, expected=400)
        self.assertEqual(self.call("get", f"/purchases/{p['id']}/")["balance"], 10773)

        # Payments: a scheduled one, then partial and full payments
        sched = self.post("/payments/", {"purchase_id": p["id"], "amount": 5000, "payment_date": (today() + timedelta(days=3)).isoformat(),
                                         "payment_method": "upi", "status": "pending"})
        self.assertEqual((sched["status"], sched["can_mark_paid"]), ("Pending", True))
        self.assertEqual(self.call("get", f"/purchases/{p['id']}/")["payment_status"], "Pending")
        paid = self.call("post", f"/payments/{sched['id']}/mark-paid/", {"transaction_reference": "UTR123"})
        self.assertEqual((paid["status"], paid["transaction_reference"]), ("Partially Paid", "UTR123"))
        self.assertEqual(self.call("get", f"/purchases/{p['id']}/")["payment_status"], "Partially Paid")
        err = self.post("/payments/", {"purchase_id": p["id"], "amount": 6000, "payment_date": today().isoformat(),
                                       "payment_method": "Bank Transfer"}, expected=400)
        self.assertIn("amount", err)
        last = self.post("/payments/", {"purchase_id": p["id"], "amount": 5773, "payment_date": today().isoformat(),
                                        "payment_method": "Bank Transfer"})
        self.assertEqual(last["status"], "Paid")
        p = self.call("get", f"/purchases/{p['id']}/")
        self.assertEqual((p["payment_status"], p["balance"], len(p["payments"]), len(p["goods_receipts"])), ("Paid", 0, 2, 2))
        self.call("delete", f"/payments/{last['id']}/", expected=409)

        ov = self.call("get", "/overview/")
        self.assertEqual(ov["kpis"]["total_purchases"]["value"], 1)
        self.assertEqual(ov["kpis"]["purchase_value"]["value"], 11970)
        self.assertEqual(ov["kpis"]["received_purchases"]["value"], 1)
        self.assertEqual(ov["kpis"]["purchase_returns"]["value"], 1)
        self.assertEqual(ov["kpis"]["outstanding_payments"]["value"], 0)
        self.assertEqual(ov["top_materials"][0]["item"], "TEST Raw Turmeric")
        perf = ov["supplier_performance"][0]
        self.assertEqual((perf["supplier"], perf["accepted_pct"]), ("TEST Spice Farms", 95.2))  # 100 of 105 kg accepted
        self.assertTrue(self.call("get", "/trend/"))
        self.assertEqual(self.call("get", "/purchases/?payment_status=paid")["count"], 1)

    def test_overdue_payments_and_filters(self):
        s, m = self.supplier(credit_days=0), self.material()
        old = today() - timedelta(days=10)
        p = self.purchase(s, m, purchase_date=old.isoformat())
        self.assertEqual(p["payment_status"], "Overdue")
        self.assertEqual(self.call("get", "/purchases/?payment_status=Overdue")["count"], 1)
        self.assertEqual(self.call("get", "/purchases/?payment_status=pending")["count"], 0)
        self.assertEqual(self.call("get", f"/purchases/?date_from={today().isoformat()}")["count"], 0)
        self.assertEqual(self.call("get", "/purchases/?range=this_year&search=turmeric")["count"], 1)
        late = self.post("/payments/", {"supplier_id": s["id"], "amount": 100, "payment_date": old.isoformat(),
                                        "payment_method": "cash", "status": "pending"})
        self.assertEqual(late["status"], "Overdue")
        self.assertEqual(self.call("get", "/payments/?status=overdue")["count"], 1)
        self.call("delete", f"/payments/{late['id']}/", expected=204)
        self.assertEqual(self.call("get", "/overview/")["kpis"]["outstanding_payments"]["value"], 11970)

    def test_product_purchase_adds_finished_stock(self):
        s = self.supplier()
        product = Product.objects.create(name="TEST Garam Masala", price_per_kg=Decimal("400"))
        p = self.post("/purchases/", {"supplier_id": s["id"], "item_type": "product", "product_id": product.id, "quantity": 20,
                                      "unit_price": 300, "purchase_date": today().isoformat()})
        self.assertEqual((p["item"], p["unit"], p["total_amount"]), ("TEST Garam Masala", "kg", 6000))
        self.post("/goods-receipts/", {"purchase_id": p["id"], "received_date": today().isoformat(), "received_quantity": 20})
        product.refresh_from_db()
        self.assertEqual(product.stock_kg, 20)
        self.assertEqual(product.movements.get().source, "purchase")

    def test_cancel_delete_and_validation(self):
        s, m = self.supplier(), self.material()
        err = self.post("/purchases/", {"supplier_id": 999, "material_id": m["id"], "quantity": 0, "unit_price": -1,
                                        "gst_pct": 101, "purchase_date": (today() + timedelta(days=1)).isoformat(),
                                        "expected_receipt_date": today().isoformat()}, expected=400)
        self.assertTrue({"supplier_id", "quantity", "unit_price", "gst_pct", "purchase_date"} <= set(err))
        p = self.purchase(s, m)
        cancelled = self.post(f"/purchases/{p['id']}/cancel/", {}, expected=200)
        self.assertEqual((cancelled["status"], cancelled["payment_status"]), ("Cancelled", None))
        self.post(f"/purchases/{p['id']}/cancel/", {}, expected=400)
        self.post("/goods-receipts/", {"purchase_id": p["id"], "received_date": today().isoformat(), "received_quantity": 1}, expected=400)
        self.call("patch", f"/purchases/{p['id']}/", {"notes": "x"}, expected=400)
        self.call("delete", f"/purchases/{p['id']}/", expected=204)

    def test_price_increase_alert_uses_real_previous_price(self):
        s, m = self.supplier(), self.material()
        make_user("purchase")
        self.purchase(s, m, price=100)
        self.assertFalse(Notification.objects.filter(key="purchase_price_increase").exists())
        self.purchase(s, m, price=110)
        self.assertTrue(Notification.objects.filter(key="purchase_price_increase", title__contains="10.0%").exists())


class PurchasePermissionTests(TestCase):
    def test_roles(self):
        self.assertEqual(client_for(make_user("sales")).get(f"{API}/purchase/overview/").status_code, 403)
        for role in ("admin", "management", "purchase", "inventory", "finance", "supply_chain"):
            self.assertEqual(client_for(make_user(role)).get(f"{API}/purchase/purchases/").status_code, 200, role)
        finance = client_for(make_user("finance", username="fin2"))
        self.assertEqual(finance.post(f"{API}/purchase/purchases/", {}, format="json").status_code, 403)
        self.assertEqual(finance.post(f"{API}/purchase/payments/", {}, format="json").status_code, 400)  # may pay suppliers
        inventory = client_for(make_user("inventory", username="inv2"))
        self.assertEqual(inventory.post(f"{API}/purchase/suppliers/", {}, format="json").status_code, 403)
        self.assertEqual(inventory.post(f"{API}/purchase/material-movements/", {}, format="json").status_code, 400)
        self.assertEqual(self.client.get(f"{API}/purchase/overview/").status_code, 401)
