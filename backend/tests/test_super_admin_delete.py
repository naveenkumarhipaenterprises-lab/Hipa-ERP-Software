"""Super Admin deletes (DELETE /records/<kind>/<id>/): an entry is removed as if it was never made."""
from datetime import timedelta

from django.test import TestCase

from apps.core.periods import today
from apps.inventory.models import Product, StockMovement
from apps.purchase.models import RawMaterial
from apps.sales.models import SalesInvoice
from apps.system.models import AuditLog

from .helpers import API, client_for, make_user


class SuperAdminDeleteTests(TestCase):
    def setUp(self):
        self.api = client_for(make_user("admin"))

    def call(self, method, path, body=None, expected=200):
        res = getattr(self.api, method)(API + path, body or {}, format="json")
        self.assertEqual(res.status_code, expected, f"{method.upper()} {path}: {getattr(res, 'data', '')}")
        return getattr(res, "data", None)

    def delete(self, kind, pk, expected=204):
        return self.call("delete", f"/records/{kind}/{pk}/", expected=expected)

    def product(self, name="TEST Turmeric Powder", stock=100):
        p = self.call("post", "/inventory/items/", {"product_name": name, "opening_stock_kg": stock, "price_per_kg": 250,
                                                    "min_stock_kg": 0, "reorder_level_kg": 0}, 201)
        return Product.objects.get(pk=p["id"])

    def customer(self):
        return self.call("post", "/customers/", {"name": "TEST Traders", "type": "retailer", "city": "Erode"}, 201)

    def stock(self, p):
        return Product.objects.get(pk=p.pk).stock_kg

    def test_only_super_admin(self):
        p = self.product()
        for role in ("management", "inventory", "sales"):
            res = client_for(make_user(role, username=f"t_{role}")).delete(f"{API}/records/product/{p.pk}/")
            self.assertEqual(res.status_code, 403, role)
        self.delete("product", 99999, expected=404)
        self.delete("nonsense", p.pk, expected=404)

    def test_invoice_payment_order_chain(self):
        tur, cust = self.product(), self.customer()
        inv = self.call("post", "/sales/invoices/", {"customer_id": cust["id"], "due_date": (today() + timedelta(days=10)).isoformat(),
                                                     "items": [{"product_id": tur.id, "quantity_kg": 20, "gst_pct": 5}]}, 201)
        self.assertEqual(self.stock(tur), 80)
        pay = self.call("post", "/sales/payments/", {"invoice_id": inv["id"], "amount": 1000, "payment_method": "upi"}, 201)
        err = self.delete("sales_invoice", inv["id"], expected=400)
        self.assertIn("Delete the payments first", err["detail"])
        self.delete("sales_payment", pay["id"])
        self.assertEqual(SalesInvoice.objects.get(pk=inv["id"]).amount_paid, 0)
        self.delete("sales_invoice", inv["id"])
        self.assertEqual(self.stock(tur), 100)  # stock put back
        self.assertFalse(StockMovement.objects.filter(reference=inv["invoice_number"]).exists())
        self.assertTrue(AuditLog.objects.filter(action__startswith="Deleted", target=inv["invoice_number"]).exists())

        order = self.call("post", "/sales/orders/", {"customer_id": cust["id"], "order_date": today().isoformat(),
                                                     "items": [{"product_id": tur.id, "quantity_kg": 7}]}, 201)
        self.assertEqual(self.stock(tur), 93)
        self.delete("sales_order", order["id"])
        self.assertEqual(self.stock(tur), 100)
        # The customer has no sales left, so it can go; the product only has its opening stock
        self.delete("customer", cust["id"])
        self.delete("product", tur.id)

    def test_goods_receipt_then_purchase(self):
        s = self.call("post", "/purchase/suppliers/", {"name": "TEST Spice Farms", "city": "Erode"}, 201)
        m = self.call("post", "/purchase/raw-materials/", {"name": "TEST Raw Turmeric", "category": "whole_spice", "unit": "kg",
                                                            "minimum_stock": 0, "reorder_level": 0}, 201)
        p = self.call("post", "/purchase/purchases/", {"supplier_id": s["id"], "item_type": "material", "material_id": m["id"],
                                                       "quantity": 100, "unit_price": 120, "purchase_date": today().isoformat()}, 201)
        grn = self.call("post", "/purchase/goods-receipts/", {"purchase_id": p["id"], "received_date": today().isoformat(),
                                                              "received_quantity": 60}, 201)
        self.assertEqual(RawMaterial.objects.get(pk=m["id"]).current_stock, 60)
        self.assertIn("goods receipt", self.delete("purchase", p["id"], expected=400)["detail"])
        self.delete("goods_receipt", grn["id"])
        self.assertEqual(RawMaterial.objects.get(pk=m["id"]).current_stock, 0)
        self.assertEqual(self.call("get", f"/purchase/purchases/{p['id']}/")["status"], "Pending")
        self.delete("purchase", p["id"])
        self.delete("raw_material", m["id"])
        self.delete("supplier", s["id"])

    def test_stock_that_was_used_cant_be_taken_back(self):
        s = self.call("post", "/purchase/suppliers/", {"name": "TEST Farms", "city": "Erode"}, 201)
        tur = self.product(stock=0)
        p = self.call("post", "/purchase/purchases/", {"supplier_id": s["id"], "item_type": "product", "product_id": tur.id,
                                                       "quantity": 10, "unit_price": 100, "purchase_date": today().isoformat()}, 201)
        grn = self.call("post", "/purchase/goods-receipts/", {"purchase_id": p["id"], "received_date": today().isoformat(),
                                                              "received_quantity": 10}, 201)
        self.call("post", "/inventory/movements/", {"item_id": tur.id, "type": "out", "quantity_kg": 8}, 201)
        self.assertIn("can't be taken back", self.delete("goods_receipt", grn["id"], expected=400)["detail"])
        self.assertEqual(self.stock(tur), 2)  # nothing changed
