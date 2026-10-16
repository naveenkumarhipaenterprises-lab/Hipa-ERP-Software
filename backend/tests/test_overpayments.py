"""
Overpayments (e.g. goods returned after an invoice was paid): refund it or keep it as the customer's credit, decided
each time; credit pays later invoices. TEST records only.
"""
from datetime import timedelta

from django.core.cache import cache
from django.test import TestCase

from apps.core.periods import today
from apps.sales.models import SalesSettlement
from apps.system.models import AuditLog

from .helpers import API, client_for, make_user


class OverpaymentTests(TestCase):
    def setUp(self):
        cache.clear()
        self.api = client_for(make_user("admin"))
        self.product = self.call("post", "/inventory/items/", {"product_name": "TEST Turmeric", "opening_stock_kg": 100,
                                                              "price_per_kg": 250, "min_stock_kg": 0, "reorder_level_kg": 0}, 201)
        self.customer = self.call("post", "/customers/", {"name": "TEST Traders", "type": "retailer", "city": "Erode"}, 201)

    def call(self, method, path, body=None, expected=200):
        res = getattr(self.api, method)(API + path, body or {}, format="json")
        self.assertEqual(res.status_code, expected, f"{method.upper()} {path}: {getattr(res, 'data', '')}")
        return res.data

    def invoice(self, kg=10):
        return self.call("post", "/sales/invoices/", {"customer_id": self.customer["id"], "due_date": (today() + timedelta(days=10)).isoformat(),
                                                      "items": [{"product_id": self.product["id"], "quantity_kg": kg, "gst_pct": 0}]}, 201)

    def pay(self, inv, amount, method="upi", expected=201):
        return self.call("post", "/sales/payments/", {"invoice_id": inv["id"], "amount": amount, "payment_method": method}, expected)

    def overpaid_invoice(self):
        """₹2,500 paid in full, then 2 kg (₹500) returned: ₹500 overpaid."""
        inv = self.invoice()
        self.pay(inv, 2500)
        ret = self.call("post", "/sales/returns/", {"invoice_id": inv["id"], "product_id": self.product["id"], "quantity_kg": 2,
                                                    "reason": "damaged"}, 201)
        self.call("patch", f"/sales/returns/{ret['id']}/", {"status": "completed"})
        return self.call("get", f"/sales/invoices/{inv['id']}/")

    def settle(self, inv, kind, amount, expected=201, **extra):
        return self.call("post", "/sales/settlements/", {"invoice_id": inv["id"], "kind": kind, "amount": amount, **extra}, expected)

    def test_refund_part_and_keep_the_rest_as_credit(self):
        inv = self.overpaid_invoice()
        self.assertEqual((inv["overpaid"], inv["payment_status"], inv["can_settle"]), (500, "Paid", True))
        refund = self.settle(inv, "refund", 300, payment_method="upi", reference="TEST-UTR")
        self.assertTrue(refund["number"].startswith("RFD"))
        credit = self.settle(inv, "credit", 200)
        self.assertTrue(credit["number"].startswith("CRN"))
        inv = self.call("get", f"/sales/invoices/{inv['id']}/")
        self.assertEqual((inv["overpaid"], inv["settled_amount"], inv["balance"], inv["payment_status"], inv["can_settle"]),
                         (0, 500, 0, "Paid", False))
        self.assertEqual(inv["customer_credit"], 200)
        self.assertEqual(sorted(s["kind"] for s in inv["settlements"]), ["Customer credit", "Refund"])
        self.assertEqual(self.call("get", "/sales/settlements/?kind=refund")["count"], 1)
        self.assertTrue(AuditLog.objects.filter(action__startswith="Recorded refund").exists())

    def test_credit_pays_a_later_invoice(self):
        inv = self.overpaid_invoice()
        self.settle(inv, "credit", 200)
        second = self.invoice(kg=4)  # ₹1,000
        self.assertEqual(self.call("get", f"/sales/invoices/?customer={self.customer['id']}")["results"][0]["customer_credit"], 200)
        self.pay(second, 150, method="credit")
        err = self.pay(second, 100, method="credit", expected=400)
        self.assertIn("₹50.00 credit available", err["amount"][0])
        p = self.pay(second, 50, method="credit")
        self.assertEqual(self.call("get", f"/sales/invoices/{second['id']}/")["customer_credit"], 0)
        # Credit already used can't be cancelled until the payments made with it are cancelled
        credit = SalesSettlement.objects.get(kind="credit")
        self.assertIn("already used", self.call("post", f"/sales/settlements/{credit.pk}/cancel/", expected=400)["detail"])
        self.call("post", f"/sales/payments/{p['id']}/cancel/")
        self.assertEqual(self.call("get", f"/sales/invoices/{second['id']}/")["customer_credit"], 50)  # credit given back

    def test_wrong_settlements_are_refused(self):
        inv = self.overpaid_invoice()
        self.assertIn("amount", self.settle(inv, "credit", 600, expected=400))  # only 500 overpaid
        self.assertIn("payment_method", self.settle(inv, "refund", 100, expected=400))  # how was it paid?
        self.assertIn("payment_method", self.settle(inv, "refund", 100, expected=400, payment_method="credit"))
        self.assertIn("kind", self.settle(inv, "gift", 100, expected=400))
        self.assertIn("date", self.settle(inv, "credit", 100, expected=400, date=(today() + timedelta(days=1)).isoformat()))
        clean = self.invoice(kg=1)
        self.assertIn("no overpayment", self.settle(clean, "credit", 10, expected=400)["invoice_id"][0])

    def test_cancelling_a_refund_shows_the_overpayment_again(self):
        inv = self.overpaid_invoice()
        refund = self.settle(inv, "refund", 300, payment_method="cash")
        cancelled = self.call("post", f"/sales/settlements/{refund['id']}/cancel/")
        self.assertEqual(cancelled["status"], "Cancelled")
        self.assertEqual(self.call("get", f"/sales/invoices/{inv['id']}/")["overpaid"], 500)
        self.call("post", f"/sales/settlements/{refund['id']}/cancel/", expected=400)  # already cancelled

    def test_the_same_form_cannot_settle_twice_and_only_payment_roles_may(self):
        inv = self.overpaid_invoice()
        body = {"invoice_id": inv["id"], "kind": "credit", "amount": 100, "request_key": "TEST-settle-1"}
        self.call("post", "/sales/settlements/", body, 201)
        self.call("post", "/sales/settlements/", body, 409)
        self.assertEqual(SalesSettlement.objects.count(), 1)
        stock = client_for(make_user("inventory", username="store"))
        self.assertEqual(stock.post(f"{API}/sales/settlements/", {**body, "request_key": "x"}, format="json").status_code, 403)

    def test_paid_filter_counts_refunds(self):
        inv = self.overpaid_invoice()
        self.settle(inv, "refund", 500, payment_method="upi")
        self.assertEqual(self.call("get", "/sales/invoices/?payment_status=paid")["count"], 1)
        self.call("post", f"/sales/payments/{self.call('get', f'/sales/invoices/{inv['id']}/')['payments'][0]['id']}/cancel/")
        inv = self.call("get", f"/sales/invoices/{inv['id']}/")
        self.assertEqual((inv["balance"], inv["payment_status"]), (2500, "Unpaid"))  # 2,000 owed + the 500 already refunded
