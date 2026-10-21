"""
Editing sales orders (pending and not invoiced; stock is rebalanced, the customer stays) and inbound shipments
(until delivered). Direct single-product orders carry the default sales GST. TEST records only.
"""
from datetime import timedelta

from django.test import TestCase

from apps.core.periods import today
from apps.inventory.models import Product, StockMovement
from apps.system.models import AuditLog, BillingSettings

from .helpers import API, client_for, make_user


class Base(TestCase):
    def setUp(self):
        self.api = client_for(make_user("admin"))

    def call(self, method, path, body=None, expected=200):
        res = getattr(self.api, method)(API + path, body, format="json")
        self.assertEqual(res.status_code, expected, f"{path}: {res.data}")
        return res.data


class OrderEditTests(Base):
    def setUp(self):
        super().setUp()
        self.turmeric = self.call("post", "/inventory/items/", {"product_name": "TEST Turmeric", "opening_stock_kg": 100, "price_per_kg": 250,
                                                                "min_stock_kg": 1, "reorder_level_kg": 2}, 201)
        self.chilli = self.call("post", "/inventory/items/", {"product_name": "TEST Chilli", "opening_stock_kg": 50, "price_per_kg": 300,
                                                              "min_stock_kg": 1, "reorder_level_kg": 2}, 201)
        self.customer = self.call("post", "/customers/", {"name": "TEST Traders", "type": "retailer", "city": "Erode"}, 201)
        self.other = self.call("post", "/customers/", {"name": "TEST Other", "type": "retailer", "city": "Salem"}, 201)

    def stock(self, p):
        return Product.objects.get(pk=p["id"]).stock_kg

    def order(self, kg=10):
        return self.call("post", "/sales/orders/", {"customer_id": self.customer["id"], "order_date": today().isoformat(),
                                                    "items": [{"product_id": self.turmeric["id"], "quantity_kg": kg, "gst_pct": 0}]}, 201)

    def test_products_and_quantities_change_and_stock_follows(self):
        o = self.order(10)
        self.assertTrue(o["can_edit"])
        self.assertEqual(self.stock(self.turmeric), 90)
        edited = self.call("patch", f"/sales/orders/{o['id']}/", {
            "notes": "TEST changed", "items": [{"product_id": self.turmeric["id"], "quantity_kg": 4, "gst_pct": 5},
                                               {"product_id": self.chilli["id"], "quantity_kg": 5, "discount_pct": 10, "gst_pct": 5}]})
        self.assertEqual((self.stock(self.turmeric), self.stock(self.chilli)), (96, 45))
        self.assertEqual(edited["notes"], "TEST changed")
        self.assertEqual([(i["product"], i["quantity_kg"]) for i in edited["items"]], [("TEST Turmeric", 4), ("TEST Chilli", 5)])
        # 4 × 250 = 1000 and 5 × 300 − 10% = 1350, plus 5% GST on both
        self.assertEqual(edited["amount"], 2467.5)
        self.assertTrue(AuditLog.objects.filter(action="Edited sales order", target=o["order_number"]).exists())

    def test_not_enough_stock_changes_nothing(self):
        o = self.order(10)
        err = self.call("patch", f"/sales/orders/{o['id']}/", {"items": [{"product_id": self.chilli["id"], "quantity_kg": 500}]}, 400)
        self.assertTrue(err)
        self.assertEqual((self.stock(self.turmeric), self.stock(self.chilli)), (90, 50))
        self.assertEqual(self.call("get", f"/sales/orders/{o['id']}/")["items"][0]["product"], "TEST Turmeric")

    def test_only_pending_uninvoiced_orders_and_never_the_customer(self):
        o = self.order()
        err = self.call("patch", f"/sales/orders/{o['id']}/", {"customer_id": self.other["id"]}, 400)
        self.assertIn("customer_id", err)
        self.call("patch", f"/sales/orders/{o['id']}/", {"customer_id": self.customer["id"], "notes": "same customer is fine"})
        self.assertIn("future", str(self.call("patch", f"/sales/orders/{o['id']}/",
                                                {"order_date": (today() + timedelta(days=1)).isoformat()}, 400)))
        invoiced = self.order()
        self.call("post", f"/sales/orders/{invoiced['id']}/convert-to-invoice/", {}, 201)
        self.assertFalse(self.call("get", f"/sales/orders/{invoiced['id']}/")["can_edit"])
        self.assertIn("invoiced", str(self.call("patch", f"/sales/orders/{invoiced['id']}/", {"notes": "x"}, 400)))
        moved = self.order()
        self.call("post", f"/sales/orders/{moved['id']}/status/", {"status": "processing"})
        self.assertIn("processing order can't be edited", str(self.call("patch", f"/sales/orders/{moved['id']}/", {"notes": "x"}, 400)))

    def test_editing_needs_sales_write_access(self):
        o = self.order()
        res = client_for(make_user("marketing", username="mk")).patch(f"{API}/sales/orders/{o['id']}/", {"notes": "x"}, format="json")
        self.assertEqual(res.status_code, 403)

    def test_direct_single_product_order_carries_the_default_gst(self):
        billing = BillingSettings.load()
        billing.default_sales_gst_pct = 5
        billing.save()
        o = self.call("post", "/sales/orders/", {"customer_id": self.customer["id"], "product_id": self.turmeric["id"],
                                                 "quantity_kg": 10, "order_date": today().isoformat()}, 201)
        self.assertEqual((o["gst_amount"], o["amount"]), (125, 2625))
        self.assertEqual(StockMovement.objects.filter(reference=o["order_number"]).count(), 1)


class ShipmentEditTests(Base):
    def setUp(self):
        super().setUp()
        supplier = self.call("post", "/purchase/suppliers/", {"name": "TEST Farms", "city": "Erode"}, 201)
        material = self.call("post", "/purchase/raw-materials/", {"name": "TEST Raw Pepper", "category": "whole_spice", "unit": "kg"}, 201)
        self.eta = (today() + timedelta(days=5)).isoformat()
        self.s = self.call("post", "/supply-chain/shipments/", {"supplier_id": supplier["id"], "material_id": material["id"], "quantity": 20,
                                                                 "unit": "kg", "destination": "TEST Godown", "eta": self.eta}, 201)

    def test_quantity_destination_and_dates_can_change(self):
        later = (today() + timedelta(days=9)).isoformat()
        edited = self.call("patch", f"/supply-chain/shipments/{self.s['id']}/", {"quantity": 25.5, "eta": later})
        self.assertEqual((edited["quantity"], edited["eta"].isoformat(), edited["destination"]), (25.5, later, "TEST Godown"))
        err = self.call("patch", f"/supply-chain/shipments/{self.s['id']}/", {"eta": (today() - timedelta(days=3)).isoformat()}, 400)
        self.assertIn("eta", err)
        self.assertIn("quantity", self.call("patch", f"/supply-chain/shipments/{self.s['id']}/", {"quantity": 0}, 400))
        self.assertTrue(AuditLog.objects.filter(action="Edited shipment").exists())

    def test_a_delivered_shipment_cant_change(self):
        self.call("post", f"/supply-chain/shipments/{self.s['id']}/status/", {"status": "delivered", "delivered_on": today().isoformat()})
        self.assertIn("delivered", str(self.call("patch", f"/supply-chain/shipments/{self.s['id']}/", {"quantity": 30}, 400)))

    def test_editing_needs_supply_chain_write_access(self):
        res = client_for(make_user("sales", username="sl")).patch(f"{API}/supply-chain/shipments/{self.s['id']}/", {"quantity": 30},
                                                                   format="json")
        self.assertEqual(res.status_code, 403)
