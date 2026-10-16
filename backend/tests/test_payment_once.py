"""The same payment form can't record a payment twice (a double click or a retry), for customers and suppliers."""
from datetime import timedelta

from django.core.cache import cache
from django.test import TestCase

from apps.core.periods import today
from apps.purchase.models import SupplierPayment
from apps.sales.models import SalesPayment

from .helpers import API, client_for, make_user


class PaymentOnceTests(TestCase):
    def setUp(self):
        cache.clear()
        self.api = client_for(make_user("admin"))

    def call(self, path, body, expected):
        res = self.api.post(API + path, body, format="json")
        self.assertEqual(res.status_code, expected, f"{path}: {res.data}")
        return res.data

    def invoice(self):
        p = self.call("/inventory/items/", {"product_name": "TEST Turmeric", "opening_stock_kg": 100, "price_per_kg": 250,
                                            "min_stock_kg": 0, "reorder_level_kg": 0}, 201)
        c = self.call("/customers/", {"name": "TEST Traders", "type": "retailer", "city": "Erode"}, 201)
        return self.call("/sales/invoices/", {"customer_id": c["id"], "due_date": (today() + timedelta(days=10)).isoformat(),
                                              "items": [{"product_id": p["id"], "quantity_kg": 10, "gst_pct": 0}]}, 201)

    def test_a_customer_payment_form_sent_twice_records_once(self):
        inv = self.invoice()
        body = {"invoice_id": inv["id"], "amount": 500, "payment_method": "upi", "request_key": "TEST-form-1"}
        self.call("/sales/payments/", body, 201)
        err = self.call("/sales/payments/", body, 409)
        self.assertIn("already recorded", err["detail"])
        self.assertEqual(SalesPayment.objects.count(), 1)
        self.call("/sales/payments/", {**body, "request_key": "TEST-form-2"}, 201)  # a new form: a new payment
        self.assertEqual(SalesPayment.objects.count(), 2)

    def test_a_refused_form_can_be_corrected_and_sent_again(self):
        inv = self.invoice()
        body = {"invoice_id": inv["id"], "amount": 0, "payment_method": "upi", "request_key": "TEST-form-3"}
        self.call("/sales/payments/", body, 400)  # wrong amount: nothing saved, the code is released
        self.call("/sales/payments/", {**body, "amount": 500}, 201)

    def test_without_a_code_it_works_as_before(self):
        inv = self.invoice()
        body = {"invoice_id": inv["id"], "amount": 100, "payment_method": "cash"}
        self.call("/sales/payments/", body, 201)
        self.call("/sales/payments/", body, 201)
        self.assertEqual(SalesPayment.objects.count(), 2)

    def test_a_supplier_payment_form_sent_twice_records_once(self):
        s = self.call("/purchase/suppliers/", {"name": "TEST Farms", "city": "Erode"}, 201)
        body = {"supplier_id": s["id"], "amount": 1000, "payment_date": today().isoformat(), "payment_method": "upi",
                "request_key": "TEST-form-4"}
        self.call("/purchase/payments/", body, 201)
        self.call("/purchase/payments/", body, 409)
        self.assertEqual(SupplierPayment.objects.count(), 1)
