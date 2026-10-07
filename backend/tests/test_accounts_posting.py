"""
Sales payments and supplier payments flow into Accounts by themselves: one transaction per payment, updated in
place, marked Cancelled (and left out of every total) when the payment is cancelled. TEST records only.
"""
import importlib
from datetime import timedelta
from decimal import Decimal

from django.apps import apps
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.core.periods import today
from apps.finance.models import Transaction
from apps.purchase.models import SupplierPayment
from apps.sales.models import SalesPayment

from .helpers import API, client_for, make_user

post_existing = importlib.import_module("apps.finance.migrations.0003_post_existing_payments").post_existing


class AccountsPostingTests(TestCase):
    def setUp(self):
        self.api = client_for(make_user("admin"))
        product = self.call("post", "/inventory/items/", {"product_name": "TEST Chilli Powder", "opening_stock_kg": 100,
                                                         "price_per_kg": 300, "min_stock_kg": 0, "reorder_level_kg": 0}, 201)
        self.customer = self.call("post", "/customers/", {"name": "TEST Traders", "type": "retailer", "city": "Erode"}, 201)
        self.invoice = self.call("post", "/sales/invoices/", {"customer_id": self.customer["id"],
                                                              "items": [{"product_id": product["id"], "quantity_kg": 10, "gst_pct": 5}]}, 201)
        self.supplier = self.call("post", "/purchase/suppliers/", {"name": "TEST Spice Farms", "city": "Erode"}, 201)
        material = self.call("post", "/purchase/raw-materials/", {"name": "TEST Raw Chilli", "category": "whole_spice", "unit": "kg"}, 201)
        self.purchase = self.call("post", "/purchase/purchases/", {"supplier_id": self.supplier["id"], "material_id": material["id"],
                                                                  "quantity": 100, "unit_price": 100, "purchase_date": today().isoformat()}, 201)

    def call(self, method, path, body=None, expected=200):
        res = getattr(self.api, method)(API + path, body or {}, format="json")
        self.assertEqual(res.status_code, expected, f"{method.upper()} {path}: {getattr(res, 'data', '')}")
        return getattr(res, "data", res)

    def receive(self, amount, **extra):
        return self.call("post", "/sales/payments/", {"invoice_id": self.invoice["id"], "amount": amount, "payment_method": "upi", **extra}, 201)

    def pay_supplier(self, amount, **extra):
        return self.call("post", "/purchase/payments/", {"purchase_id": self.purchase["id"], "amount": amount, "payment_method": "bank_transfer",
                                                         "payment_date": today().isoformat(), **extra}, 201)

    def accounts(self):
        return self.call("get", "/finance/overview/")["kpis"]

    # --- Sales payments ----------------------------------------------------------------------
    def test_received_sales_payment_becomes_income(self):
        p = self.receive(1000, reference="UTR-1")
        t = Transaction.objects.get(sales_payment_id=p["id"])
        self.assertEqual((t.type, t.category, t.amount, t.date, t.status, t.party),
                         ("income", "product_sales", Decimal("1000.00"), today(), "completed", "TEST Traders"))
        self.assertEqual(t.reference, f"{p['receipt_number']} / UTR-1")
        self.assertIn(self.invoice["invoice_number"], t.description)
        self.assertEqual(self.accounts()["revenue"]["value"], 1000)
        row = self.call("get", "/finance/transactions/")["results"][0]
        self.assertEqual(row["source"]["number"], p["receipt_number"])
        self.assertEqual((row["can_edit"], row["can_mark_paid"]), (False, False))

    def test_export_customer_payment_is_export_sales(self):
        self.call("patch", f"/customers/{self.customer['id']}/", {"type": "export"})
        p = self.receive(500)
        self.assertEqual(Transaction.objects.get(sales_payment_id=p["id"]).category, "export_sales")

    def test_cancelled_sales_payment_is_kept_but_counts_nowhere(self):
        p = self.receive(1000)
        self.call("post", f"/sales/payments/{p['id']}/cancel/")
        t = Transaction.objects.get(sales_payment_id=p["id"])
        self.assertEqual(t.status, "cancelled")
        self.assertEqual(Transaction.objects.count(), 1)  # no reversing row, no second row
        kpis = self.accounts()
        self.assertEqual((kpis["revenue"]["value"], kpis["net_profit"]["value"]), (0, 0))
        self.assertEqual(self.call("get", "/dashboard/summary/")["kpis"]["net_profit"]["value"], 0)
        self.assertEqual(self.call("get", "/finance/cash-flow/"), [])  # nothing completed: the chart shows its empty state
        self.assertEqual(self.call("get", "/finance/transactions/?status=cancelled")["count"], 1)

    def test_saving_a_payment_again_updates_the_same_transaction(self):
        p = SalesPayment.objects.get(pk=self.receive(1000)["id"])
        p.amount, p.payment_date = Decimal("900"), today() - timedelta(days=1)
        p.save()
        p.save()
        t = Transaction.objects.get(sales_payment=p)
        self.assertEqual((t.amount, t.date), (Decimal("900.00"), today() - timedelta(days=1)))
        self.assertEqual(Transaction.objects.count(), 1)

    def test_a_payment_can_never_have_two_transactions(self):
        p = SalesPayment.objects.get(pk=self.receive(1000)["id"])
        with self.assertRaises(IntegrityError), transaction.atomic():
            Transaction.objects.create(sales_payment=p, type="income", category="product_sales", description="TEST",
                                       amount=1000, date=today())

    # --- Supplier payments --------------------------------------------------------------------
    def test_supplier_payment_posts_when_paid_and_reverses_when_cancelled(self):
        scheduled = self.pay_supplier(2000, status="pending", payment_date=(today() + timedelta(days=5)).isoformat())
        self.assertFalse(Transaction.objects.exists())  # nothing until it is paid
        paid = self.call("post", f"/purchase/payments/{scheduled['id']}/mark-paid/", {"transaction_reference": "NEFT-7"})
        t = Transaction.objects.get(supplier_payment_id=paid["id"])
        self.assertEqual((t.type, t.category, t.amount, t.status, t.party, t.date),
                         ("expense", "raw_materials", Decimal("2000.00"), "completed", "TEST Spice Farms", today()))
        self.assertEqual(t.reference, f"{paid['payment_number']} / NEFT-7")
        self.assertTrue(paid["can_cancel"])
        self.assertEqual(self.accounts()["expenses"]["value"], 2000)

        cancelled = self.call("post", f"/purchase/payments/{paid['id']}/cancel/")
        self.assertEqual((cancelled["status"], cancelled["can_cancel"]), ("Cancelled", False))
        self.assertEqual(Transaction.objects.get(supplier_payment_id=paid["id"]).status, "cancelled")
        self.assertEqual(self.accounts()["expenses"]["value"], 0)
        self.assertEqual(self.call("get", f"/purchase/purchases/{self.purchase['id']}/")["paid_amount"], 0)
        self.call("post", f"/purchase/payments/{paid['id']}/cancel/", expected=400)

    def test_scheduled_supplier_payment_is_deleted_not_cancelled(self):
        scheduled = self.pay_supplier(500, status="pending", payment_date=(today() + timedelta(days=2)).isoformat())
        self.call("post", f"/purchase/payments/{scheduled['id']}/cancel/", expected=400)
        self.call("delete", f"/purchase/payments/{scheduled['id']}/", expected=204)
        self.assertFalse(Transaction.objects.exists())

    def test_only_payment_managers_cancel_supplier_payments(self):
        paid = self.pay_supplier(500)
        res = client_for(make_user("sales")).post(f"{API}/purchase/payments/{paid['id']}/cancel/", {}, format="json")
        self.assertEqual(res.status_code, 403)

    # --- Accounts side --------------------------------------------------------------------------
    def test_posted_rows_cant_be_edited_in_accounts(self):
        p = self.receive(1000)
        t = Transaction.objects.get(sales_payment_id=p["id"])
        res = self.api.patch(f"{API}/finance/transactions/{t.id}/", {"amount": 1}, format="json")
        self.assertEqual(res.status_code, 409)
        self.assertIn("Sales → Payments", res.data["detail"])
        self.assertEqual(self.api.post(f"{API}/finance/transactions/{t.id}/mark-paid/", {}, format="json").status_code, 409)
        # Hand-entered rows keep working
        manual = self.call("post", "/finance/transactions/", {"type": "expense", "category": "utilities", "description": "TEST power",
                                                              "amount": 300, "date": today().isoformat()}, 201)
        self.assertTrue(manual["can_edit"])
        self.assertIsNone(manual["source"])
        self.call("patch", f"/finance/transactions/{manual['id']}/", {"amount": 350})

    def test_accounts_report_leaves_cancelled_rows_out(self):
        self.receive(1000)
        p2 = self.receive(400)
        self.call("post", f"/sales/payments/{p2['id']}/cancel/")
        preview = self.call("get", "/reports/preview/?type=finance&range=this_month")
        self.assertEqual([r["amount"] for r in preview["table"]["rows"]], [1000])
        self.assertEqual(sum(point["revenue"] for point in preview["chart"]["data"]), 1000)

    # --- Payments that existed before the link (migration finance 0003) ----------------------------
    def test_existing_payments_are_posted_once_and_a_matching_manual_row_is_linked(self):
        sp = SalesPayment.objects.get(pk=self.receive(1000)["id"])
        other = SalesPayment.objects.get(pk=self.receive(250)["id"])
        pp = SupplierPayment.objects.get(pk=self.pay_supplier(700)["id"])
        Transaction.objects.all().delete()  # as before the link existed
        manual = Transaction.objects.create(type="income", category="product_sales", description="TEST sale typed in by hand",
                                            amount=Decimal("1000"), date=today(), reference=self.invoice["invoice_number"].lower())
        unrelated = Transaction.objects.create(type="income", category="other_income", description="TEST interest",
                                               amount=Decimal("1000"), date=today())

        post_existing(apps, None)
        post_existing(apps, None)  # running again changes nothing

        manual.refresh_from_db()
        self.assertEqual(manual.sales_payment_id, sp.id)  # linked, not duplicated
        self.assertEqual(manual.reference, sp.receipt_number)
        self.assertTrue(Transaction.objects.filter(sales_payment=other).exists())
        self.assertTrue(Transaction.objects.filter(supplier_payment=pp, type="expense").exists())
        unrelated.refresh_from_db()
        self.assertIsNone(unrelated.sales_payment_id)
        self.assertEqual(Transaction.objects.count(), 4)
        self.assertEqual(self.accounts()["revenue"]["value"], 2250)  # 1000 + 250 + the unrelated 1000, nothing twice
