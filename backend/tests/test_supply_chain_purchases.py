"""
Supply Chain → New Shipment: which purchases can be linked (open = Pending or Partially Received), that the shipment
takes supplier and item from the purchase, and that creating a shipment never adds stock. TEST records only.
"""
from datetime import timedelta

from django.test import TestCase

from apps.core.periods import today
from apps.purchase.models import RawMaterial

from .helpers import API, client_for, make_user


class ShipmentPurchaseTests(TestCase):
    def setUp(self):
        self.api = client_for(make_user("admin"))
        self.supplier = self.post("/purchase/suppliers/", {"name": "TEST Farms", "city": "Erode"})
        self.other = self.post("/purchase/suppliers/", {"name": "TEST Other Farms", "city": "Salem"})
        self.material = self.post("/purchase/raw-materials/", {"name": "TEST Raw Pepper", "category": "whole_spice", "unit": "kg"})
        self.other_material = self.post("/purchase/raw-materials/", {"name": "TEST Raw Clove", "category": "whole_spice", "unit": "kg"})

    def post(self, path, body, expected=201):
        res = self.api.post(API + path, body, format="json")
        self.assertEqual(res.status_code, expected, f"{path}: {res.data}")
        return res.data

    def purchase(self, qty=100):
        return self.post("/purchase/purchases/", {"supplier_id": self.supplier["id"], "material_id": self.material["id"], "quantity": qty,
                                                  "unit_price": 500, "purchase_date": today().isoformat()})

    def receive(self, purchase, qty):
        return self.post("/purchase/goods-receipts/", {"purchase_id": purchase["id"], "received_date": today().isoformat(),
                                                       "received_quantity": qty})

    def offered(self):
        return {p["purchase_number"]: p["quantity"] for p in self.api.get(f"{API}/supply-chain/options/").data["purchases"]}

    def test_only_purchases_still_waiting_for_goods_are_offered(self):
        pending, partial, received, cancelled = self.purchase(), self.purchase(), self.purchase(), self.purchase()
        self.receive(partial, 40)
        self.receive(received, 100)
        self.post(f"/purchase/purchases/{cancelled['id']}/cancel/", {}, expected=200)
        self.assertEqual(self.offered(), {pending["purchase_number"]: 100, partial["purchase_number"]: 60})  # still to receive
        eta = (today() + timedelta(days=2)).isoformat()
        err = self.post("/supply-chain/shipments/", {"purchase_id": received["id"], "destination": "Main", "eta": eta}, expected=400)
        self.assertEqual(err["purchase_id"], ["Choose an open purchase."])

    def test_supplier_and_item_come_from_the_purchase_and_no_stock_is_added(self):
        p = self.purchase()
        stock_before = RawMaterial.objects.get(pk=self.material["id"]).current_stock
        sh = self.post("/supply-chain/shipments/", {"purchase_id": p["id"], "supplier_id": self.other["id"],
                                                    "material_id": self.other_material["id"], "destination": "Main",
                                                    "eta": (today() + timedelta(days=2)).isoformat()})
        self.assertEqual((sh["purchase_number"], sh["supplier"], sh["item"], sh["quantity"]),
                         (p["purchase_number"], "TEST Farms", "TEST Raw Pepper", 100))  # other supplier / material ignored
        self.assertEqual(RawMaterial.objects.get(pk=self.material["id"]).current_stock, stock_before)  # stock comes from the GRN

    def test_no_purchases_at_all(self):
        self.assertEqual(self.offered(), {})
