"""Sales quotations, invoices, customer payments, returns and PDFs (TEST records only)."""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase

from apps.core.periods import today
from apps.inventory.models import Product
from apps.sales.models import QuotationStatusChange, SalesQuotation
from apps.system.models import Notification

from .helpers import API, client_for, make_user


class SalesDocumentTests(TestCase):
    def setUp(self):
        self.api = client_for(make_user("admin"))
        self.turmeric = self.product("TEST Turmeric Powder", 250)
        self.chilli = self.product("TEST Chilli Powder", 300)
        self.customer = self.call("post", "/customers/", {"name": "TEST Traders", "type": "retailer", "city": "Erode",
                                                          "address": "12 Market Road\nErode", "gstin": "33abcde1234f1z5",
                                                          "email": "buyer@test.invalid"}, 201)

    def call(self, method, path, body=None, expected=200):
        res = getattr(self.api, method)(API + path, body or {}, format="json")
        self.assertEqual(res.status_code, expected, f"{method.upper()} {path}: {getattr(res, 'data', '')}")
        return getattr(res, "data", res)

    def sales(self, method, path, body=None, expected=200):
        return self.call(method, "/sales" + path, body, expected)

    def product(self, name, price, stock=100):
        p = self.call("post", "/inventory/items/", {"product_name": name, "opening_stock_kg": stock, "price_per_kg": price,
                                                    "min_stock_kg": 0, "reorder_level_kg": 0}, 201)
        return Product.objects.get(pk=p["id"])

    def stock(self, product):
        return Product.objects.get(pk=product.pk).stock_kg

    def quotation(self, **extra):
        body = {"customer_id": self.customer["id"], "valid_until": (today() + timedelta(days=15)).isoformat(),
                "payment_terms": "50% advance", "delivery_terms": "Ex-works Erode", "terms_conditions": "TEST terms",
                "items": [{"product_id": self.turmeric.id, "quantity_kg": 10, "discount_pct": 10, "gst_pct": 5},
                          {"product_id": self.chilli.id, "quantity_kg": 5, "unit_price": 320, "gst_pct": 5}], **extra}
        return self.sales("post", "/quotations/", body, 201)

    # --- Empty database --------------------------------------------------------------------
    def test_empty_lists_and_options(self):
        for path in ("/quotations/", "/invoices/", "/payments/", "/returns/"):
            data = self.sales("get", path)
            self.assertEqual((data["count"], data["results"]), (0, []), path)
        opts = self.sales("get", "/options/")
        self.assertIsNone(opts["defaults"]["gst_pct"])
        self.assertEqual(opts["defaults"]["quotation_terms"], "")
        self.assertTrue(opts["quotation_statuses"] and opts["payment_methods"])
        self.assertEqual(self.call("get", "/settings/billing/")["bank_name"], "")

    # --- Quotations ------------------------------------------------------------------------
    def test_quotation_totals_customer_details_and_validation(self):
        q = self.quotation()
        self.assertTrue(q["quotation_number"].startswith("QT-"))
        # Turmeric 10 x 250 = 2500 - 10% = 2250 + 5% = 2362.50; Chilli 5 x 320 = 1600 + 5% = 1680
        self.assertEqual((q["subtotal"], q["discount_amount"], q["gst_amount"], q["grand_total"]), (4100, 250, 192.5, 4042.5))
        self.assertEqual([i["amount"] for i in q["items"]], [2362.5, 1680])
        self.assertEqual((q["customer_name"], q["gstin"], q["billing_address"]), ("TEST Traders", "33ABCDE1234F1Z5", "12 Market Road\nErode"))
        self.assertEqual(q["shipping_address"], "12 Market Road\nErode")
        self.assertEqual((q["status"], q["status_history"][0]["to"]), ("Draft", "Draft"))
        self.assertTrue(q["can_convert_to_order"] and q["can_convert_to_invoice"])

        err = self.sales("post", "/quotations/", {"customer_id": self.customer["id"], "items": [
            {"product_id": self.turmeric.id, "quantity_kg": 1}, {"product_id": self.turmeric.id, "quantity_kg": 0}]}, 400)
        self.assertEqual(set(err), {"items", "valid_until"})
        self.assertIn("Row 2", err["items"][0])
        err = self.sales("post", "/quotations/", {"customer_name": "", "valid_until": "2000-01-01", "items": []}, 400)
        self.assertEqual(set(err), {"customer_name", "items", "valid_until"})

        edited = self.sales("patch", f"/quotations/{q['id']}/", {"items": [{"product_id": self.chilli.id, "quantity_kg": 2}],
                                                                 "shipping_address": "Godown 4"})
        self.assertEqual((edited["grand_total"], edited["shipping_address"]), (600, "Godown 4"))
        self.assertEqual(self.sales("get", "/quotations/?search=chilli")["count"], 1)

    def test_quotation_settings_defaults(self):
        self.call("put", "/settings/billing/", {"default_sales_gst_pct": 5, "quotation_validity_days": 30, "quotation_terms": "TEST T&C",
                                                "invoice_due_days": 15, "bank_ifsc": "sbin0001234"})
        q = self.sales("post", "/quotations/", {"customer_id": self.customer["id"],
                                                "items": [{"product_id": self.turmeric.id, "quantity_kg": 4}]}, 201)
        self.assertEqual((q["valid_until"], q["terms_conditions"], q["grand_total"]), (today() + timedelta(days=30), "TEST T&C", 1050))
        inv = self.sales("post", f"/quotations/{q['id']}/convert-to-invoice/", {}, 201)["invoice"]
        self.assertEqual(inv["due_date"], today() + timedelta(days=15))
        self.assertIn("bank_ifsc", self.call("put", "/settings/billing/", {"bank_ifsc": "BAD"}, 400))

    def test_status_workflow_and_history(self):
        q = self.quotation()
        self.sales("post", f"/quotations/{q['id']}/status/", {"status": "sent"})
        with self.captureOnCommitCallbacks(execute=True):
            acc = self.sales("post", f"/quotations/{q['id']}/status/", {"status": "Accepted", "note": "Customer confirmed by phone"})
        self.assertEqual(acc["status"], "Accepted")
        self.assertEqual([h["to"] for h in acc["status_history"]], ["Draft", "Sent", "Accepted"])
        self.assertEqual(acc["status_history"][-1]["note"], "Customer confirmed by phone")
        self.assertIn("status", self.sales("post", f"/quotations/{q['id']}/status/", {"status": "sent"}, 400))
        self.assertIn("status", self.sales("post", f"/quotations/{q['id']}/status/", {"status": "converted"}, 400))
        self.assertTrue(Notification.objects.filter(key="quotation_updates").exists())
        self.sales("patch", f"/quotations/{q['id']}/", {"notes": "x"}, 400)  # accepted quotations are locked
        self.sales("delete", f"/quotations/{q['id']}/", expected=409)
        draft = self.quotation()
        self.sales("delete", f"/quotations/{draft['id']}/", expected=204)

    def test_expiry_is_stored(self):
        q = self.quotation()
        SalesQuotation.objects.filter(pk=q["id"]).update(quotation_date=today() - timedelta(days=20), valid_until=today() - timedelta(days=1))
        row = self.sales("get", "/quotations/")["results"][0]
        self.assertEqual((row["status"], row["can_convert_to_order"]), ("Expired", False))
        self.assertTrue(QuotationStatusChange.objects.filter(quotation_id=q["id"], to_status="expired").exists())
        self.assertTrue(Notification.objects.filter(key="quotation_expiry").exists())
        self.sales("post", f"/quotations/{q['id']}/convert-to-order/", {}, 400)
        reopened = self.sales("patch", f"/quotations/{q['id']}/", {"valid_until": (today() + timedelta(days=5)).isoformat()})
        self.assertEqual(reopened["status"], "Draft")

    def test_pdfs(self):
        q = self.quotation(notes="TEST note")
        res = self.api.get(f"{API}/sales/quotations/{q['id']}/pdf/")
        self.assertEqual((res.status_code, res["Content-Type"]), (200, "application/pdf"))
        self.assertTrue(res.content.startswith(b"%PDF"))
        self.assertTrue(res["Content-Disposition"].startswith("inline"))
        res = self.api.get(f"{API}/sales/quotations/{q['id']}/pdf/?download=1")
        self.assertEqual(res["Content-Disposition"], f'attachment; filename="{q["quotation_number"]}.pdf"')
        inv = self.sales("post", f"/quotations/{q['id']}/convert-to-invoice/", {}, 201)["invoice"]
        self.call("put", "/settings/billing/", {"bank_name": "TEST Bank", "authorised_signatory": "TEST Signatory"})
        res = self.api.get(f"{API}/sales/invoices/{inv['id']}/pdf/?download=1")
        self.assertTrue(res.content.startswith(b"%PDF"))
        self.assertIn(inv["invoice_number"], res["Content-Disposition"])

    # --- Conversions -------------------------------------------------------------------------
    def test_quotation_to_order_to_invoice(self):
        q = self.quotation()
        res = self.sales("post", f"/quotations/{q['id']}/convert-to-order/", {}, 201)
        order, q2 = res["sales_order"], res["quotation"]
        self.assertTrue(order["order_number"].startswith("SO-"))
        self.assertEqual((order["amount"], order["quotation_number"], order["can_invoice"]), (4042.5, q["quotation_number"], True))
        self.assertEqual((q2["status"], q2["sales_order_number"]), ("Converted", order["order_number"]))
        self.assertEqual([h["to"] for h in q2["status_history"]], ["Draft", "Accepted", "Converted"])
        self.assertEqual((self.stock(self.turmeric), self.stock(self.chilli)), (90, 95))
        detail = self.sales("get", f"/orders/{order['id']}/")
        self.assertEqual([(i["unit_price"], i["discount_pct"], i["gst_pct"]) for i in detail["items"]], [(250, 10, 5), (320, 0, 5)])
        self.sales("post", f"/quotations/{q['id']}/convert-to-order/", {}, 400)  # no duplicates

        # Invoicing the converted quotation invoices its order, with no second stock movement
        inv = self.sales("post", f"/quotations/{q['id']}/convert-to-invoice/", {}, 201)["invoice"]
        self.assertTrue(inv["invoice_number"].startswith("INV-"))
        self.assertNotEqual(inv["invoice_number"], q["quotation_number"])
        self.assertEqual((inv["grand_total"], inv["sales_order_number"], inv["quotation_number"]),
                         (4042.5, order["order_number"], q["quotation_number"]))
        self.assertFalse(inv["can_edit_items"])
        self.assertEqual((self.stock(self.turmeric), self.stock(self.chilli)), (90, 95))
        self.sales("post", f"/orders/{order['id']}/convert-to-invoice/", {}, 400)
        self.sales("post", f"/orders/{order['id']}/cancel/", {}, 400)  # invoiced orders can't be cancelled

    def test_direct_quotation_to_invoice_moves_stock_once(self):
        q = self.quotation()
        res = self.sales("post", f"/quotations/{q['id']}/convert-to-invoice/", {"due_date": (today() + timedelta(days=7)).isoformat()}, 201)
        inv = res["invoice"]
        self.assertEqual((res["quotation"]["status"], inv["sales_order_number"], inv["payment_status"]), ("Converted", None, "Unpaid"))
        self.assertEqual((self.stock(self.turmeric), self.stock(self.chilli)), (90, 95))
        self.sales("post", f"/quotations/{q['id']}/convert-to-invoice/", {}, 400)
        self.sales("post", f"/quotations/{q['id']}/convert-to-order/", {}, 400)
        cancelled = self.sales("post", f"/invoices/{inv['id']}/cancel/")
        self.assertEqual((cancelled["status"], cancelled["payment_status"]), ("Cancelled", None))
        self.assertEqual((self.stock(self.turmeric), self.stock(self.chilli)), (100, 100))

    def test_quotation_without_customer_must_be_linked(self):
        q = self.sales("post", "/quotations/", {"customer_name": "TEST Walk-in Buyer", "valid_until": (today() + timedelta(days=3)).isoformat(),
                                                "items": [{"product_id": self.turmeric.id, "quantity_kg": 1}]}, 201)
        self.assertFalse(q["can_convert_to_order"])
        err = self.sales("post", f"/quotations/{q['id']}/convert-to-order/", {}, 400)
        self.assertIn("customer", err["detail"])

    # --- Invoices, payments, returns ------------------------------------------------------------
    def test_direct_invoice_payments_and_returns(self):
        inv = self.sales("post", "/invoices/", {"customer_id": self.customer["id"], "due_date": (today() + timedelta(days=10)).isoformat(),
                                                "items": [{"product_id": self.turmeric.id, "quantity_kg": 20, "gst_pct": 5}]}, 201)
        self.assertEqual((inv["grand_total"], inv["balance"], inv["payment_status"]), (5250, 5250, "Unpaid"))
        self.assertEqual(self.stock(self.turmeric), 80)
        err = self.sales("post", "/invoices/", {"customer_id": self.customer["id"],
                                                "items": [{"product_id": self.chilli.id, "quantity_kg": 500}]}, 400)
        self.assertIn("quantity_kg", err)  # not enough stock

        # Editing products re-books stock
        edited = self.sales("patch", f"/invoices/{inv['id']}/", {"items": [{"product_id": self.turmeric.id, "quantity_kg": 10, "gst_pct": 5}]})
        self.assertEqual((edited["grand_total"], self.stock(self.turmeric)), (2625, 90))

        with self.captureOnCommitCallbacks(execute=True):
            p1 = self.sales("post", "/payments/", {"invoice_id": inv["id"], "amount": 1000, "payment_method": "upi", "reference": "UTR1"}, 201)
        self.assertTrue(p1["receipt_number"].startswith("RCP-"))
        self.assertEqual(self.sales("get", f"/invoices/{inv['id']}/")["payment_status"], "Partially Paid")
        self.assertTrue(Notification.objects.filter(key="customer_payments").exists())
        self.assertIn("amount", self.sales("post", "/payments/", {"invoice_id": inv["id"], "amount": 5000, "payment_method": "cash"}, 400))
        self.assertIn("items", self.sales("patch", f"/invoices/{inv['id']}/", {"items": [{"product_id": self.turmeric.id, "quantity_kg": 1}]}, 400))
        self.sales("post", f"/invoices/{inv['id']}/cancel/", expected=400)

        # Return 2 kg (restocked); completing it credits 525
        ret = self.sales("post", "/returns/", {"invoice_id": inv["id"], "product_id": self.turmeric.id, "quantity_kg": 2, "reason": "damaged"}, 201)
        self.assertEqual((ret["amount"], ret["status"], self.stock(self.turmeric)), (525, "Pending", 92))
        self.assertIn("quantity_kg", self.sales("post", "/returns/", {"invoice_id": inv["id"], "product_id": self.turmeric.id,
                                                                     "quantity_kg": 9, "reason": "excess"}, 400))
        self.assertIn("product_id", self.sales("post", "/returns/", {"invoice_id": inv["id"], "product_id": self.chilli.id,
                                                                    "quantity_kg": 1, "reason": "excess"}, 400))
        self.sales("patch", f"/returns/{ret['id']}/", {"status": "completed"})
        inv = self.sales("get", f"/invoices/{inv['id']}/")
        self.assertEqual((inv["credited_amount"], inv["balance"]), (525, 1100))
        self.sales("post", "/payments/", {"invoice_id": inv["id"], "amount": 1100, "payment_method": "Bank Transfer"}, 201)
        inv = self.sales("get", f"/invoices/{inv['id']}/")
        self.assertEqual((inv["payment_status"], inv["balance"], len(inv["payments"]), len(inv["returns"])), ("Paid", 0, 2, 1))
        self.assertEqual(self.sales("get", "/invoices/?payment_status=paid")["count"], 1)

        cancelled = self.sales("post", f"/payments/{p1['id']}/cancel/")
        self.assertEqual(cancelled["status"], "Cancelled")
        self.assertEqual(self.sales("get", f"/invoices/{inv['id']}/")["payment_status"], "Partially Paid")

    def test_overdue_and_cancelled_return(self):
        inv = self.sales("post", "/invoices/", {"customer_id": self.customer["id"], "invoice_date": (today() - timedelta(days=30)).isoformat(),
                                                "due_date": (today() - timedelta(days=1)).isoformat(),
                                                "items": [{"product_id": self.chilli.id, "quantity_kg": 3}]}, 201)
        self.assertEqual(inv["payment_status"], "Overdue")
        self.assertEqual(self.sales("get", "/invoices/?payment_status=overdue")["count"], 1)
        ret = self.sales("post", "/returns/", {"invoice_id": inv["id"], "product_id": self.chilli.id, "quantity_kg": 1, "reason": "quality",
                                               "amount": 250, "restock": False}, 201)
        self.assertEqual(self.stock(self.chilli), 97)  # not restocked
        self.sales("patch", f"/returns/{ret['id']}/", {"status": "cancelled"})
        self.sales("patch", f"/returns/{ret['id']}/", {"status": "completed"}, 400)

    def test_return_credit_cannot_exceed_the_invoice_line(self):
        inv = self.sales("post", "/invoices/", {"customer_id": self.customer["id"],
                                                "items": [{"product_id": self.chilli.id, "quantity_kg": 3}]}, 201)  # 3 x 300 = 900
        err = self.sales("post", "/returns/", {"invoice_id": inv["id"], "product_id": self.chilli.id, "quantity_kg": 1,
                                               "reason": "quality", "amount": 1000}, 400)
        self.assertIn("₹900.00", err["amount"][0])
        self.sales("post", "/returns/", {"invoice_id": inv["id"], "product_id": self.chilli.id, "quantity_kg": 1,
                                         "reason": "quality", "amount": 800}, 201)
        err = self.sales("post", "/returns/", {"invoice_id": inv["id"], "product_id": self.chilli.id, "quantity_kg": 1,
                                               "reason": "quality", "amount": 101}, 400)
        self.assertIn("₹100.00", err["amount"][0])
        auto = self.sales("post", "/returns/", {"invoice_id": inv["id"], "product_id": self.chilli.id, "quantity_kg": 1,
                                                "reason": "quality"}, 201)
        self.assertEqual(auto["amount"], 100)  # 300 at the invoiced price, but only 100 is left to credit

    def test_customer_totals_exclude_gst_like_the_sales_figures(self):
        self.sales("post", "/orders/", {"customer_id": self.customer["id"], "order_date": today().isoformat(),
                                        "items": [{"product_id": self.turmeric.id, "quantity_kg": 4, "discount_pct": 5, "gst_pct": 5},
                                                  {"product_id": self.chilli.id, "quantity_kg": 1}]}, 201)
        net = 1250  # 1000 - 5% + 300; with GST it would be 1297.50
        self.assertEqual(self.sales("get", "/overview/")["kpis"]["total_sales"]["value"], net)
        self.assertEqual(self.call("get", "/customers/")["results"][0]["total_purchase"], net)
        self.assertEqual(self.call("get", "/customers/overview/")["top_customers"][0]["amount"], net)
        self.assertEqual(self.call("get", "/dashboard/summary/")["top_customers"][0]["amount"], net)
        self.assertEqual(self.sales("get", "/overview/")["top_customers"][0]["amount"], net)
        # Filtered to one product, a customer's amount is that product's sales only
        self.assertEqual(self.sales("get", f"/overview/?product={self.chilli.id}")["top_customers"][0]["amount"], 300)

    def test_dashboard_recent_orders_show_the_order_number(self):
        order = self.sales("post", "/orders/", {"customer_id": self.customer["id"], "order_date": today().isoformat(),
                                                "items": [{"product_id": self.chilli.id, "quantity_kg": 1}]}, 201)
        row = self.call("get", "/dashboard/summary/")["recent_orders"][0]
        self.assertEqual(row["order_number"], order["order_number"])

    def test_multi_product_order_with_discount_and_gst(self):
        order = self.sales("post", "/orders/", {"customer_id": self.customer["id"], "order_date": today().isoformat(),
                                                "items": [{"product_id": self.turmeric.id, "quantity_kg": 4, "discount_pct": 5, "gst_pct": 5},
                                                          {"product_id": self.chilli.id, "quantity_kg": 1}]}, 201)
        # 1000 - 5% = 950 + 5% = 997.50; + 300
        self.assertEqual((order["amount"], order["gst_amount"], order["discount_amount"]), (1297.5, 47.5, 50))
        # Net sales (excluding GST) feed the sales analytics
        self.assertEqual(self.sales("get", "/overview/")["kpis"]["total_sales"]["value"], 1250)
        inv = self.sales("post", "/invoices/", {"sales_order_id": order["id"]}, 201)
        self.assertEqual((inv["grand_total"], self.stock(self.turmeric)), (1297.5, 96))


class SalesDocumentPermissionTests(TestCase):
    def test_roles(self):
        self.assertEqual(client_for(make_user("inventory")).get(f"{API}/sales/quotations/").status_code, 403)
        finance = client_for(make_user("finance"))
        self.assertEqual(finance.get(f"{API}/sales/invoices/").status_code, 200)
        self.assertEqual(finance.post(f"{API}/sales/quotations/", {}, format="json").status_code, 403)
        self.assertEqual(finance.post(f"{API}/sales/payments/", {}, format="json").status_code, 400)  # may record receipts
        self.assertEqual(client_for(make_user("marketing")).post(f"{API}/sales/payments/", {}, format="json").status_code, 403)
        self.assertEqual(client_for(make_user("sales")).put(f"{API}/settings/billing/", {}, format="json").status_code, 403)
