"""Customer deliveries (Supply Chain): one status for the dashboard, the deliveries list and Sales orders."""
from datetime import timedelta

from django.test import TestCase

from apps.core.periods import today
from apps.supply_chain.models import CustomerDelivery, Shipment

from .helpers import API, client_for, make_user

BASE = "/supply-chain/customer-deliveries/"


class CustomerDeliveriesTests(TestCase):
    def setUp(self):
        self.admin = make_user("admin")
        self.api = client_for(self.admin)
        self.product = self.post("/inventory/items/", {"product_name": "TEST Turmeric", "opening_stock_kg": 100, "price_per_kg": 250,
                                                       "min_stock_kg": 10, "reorder_level_kg": 30})
        self.cust = self.post("/customers/", {"name": "TEST Traders", "type": "retailer", "city": "Erode", "phone": "98765 43210"})

    def post(self, path, body, expected=201, api=None):
        res = (api or self.api).post(API + path, body, format="json")
        self.assertEqual(res.status_code, expected, f"{path}: {res.data}")
        return res.data

    def order(self, days_ago=0):
        return self.post("/sales/orders/", {"customer_id": self.cust["id"], "product_id": self.product["id"], "quantity_kg": 1,
                                            "order_date": (today() - timedelta(days=days_ago)).isoformat()})

    def summary(self, api=None):
        return (api or self.api).get(f"{API}/supply-chain/overview/").data["customer_deliveries"]["summary"]

    def test_empty_state_has_zero_counts_and_no_rows(self):
        block = self.api.get(f"{API}/supply-chain/overview/").data["customer_deliveries"]
        self.assertEqual(block["summary"], {"total": 0, "pending": 0, "in_transit": 0, "delivered": 0, "delayed": 0})
        self.assertEqual(block["recent"], [])
        self.assertEqual(self.api.get(API + BASE).data["count"], 0)

    def test_full_flow_dispatch_then_confirm(self):
        o = self.order(days_ago=3)
        row = self.api.get(f"{API}{BASE}{o['id']}/").data
        self.assertEqual((row["delivery_status"], row["can_dispatch"], row["can_confirm"]), ("Pending", True, False))
        self.assertEqual(row["items"], [{"product": "TEST Turmeric", "quantity_kg": 1}])

        # Confirming before dispatch is refused: Delivered needs the order on its way first
        self.post(f"{BASE}{o['id']}/confirm/", {}, expected=400)
        expected = (today() + timedelta(days=2)).isoformat()
        row = self.post(f"{BASE}{o['id']}/dispatch/", {"carrier": "TEST Lorry", "tracking_reference": "TRK-1",
                                                        "expected_delivery_date": expected}, expected=200)
        self.assertEqual((row["delivery_status"], row["order_status"], row["tracking_reference"]), ("In Transit", "In Transit", "TRK-1"))
        self.assertEqual(str(row["expected_delivery_date"]), expected)
        self.assertEqual(self.summary(), {"total": 1, "pending": 0, "in_transit": 1, "delivered": 0, "delayed": 0})

        row = self.post(f"{BASE}{o['id']}/confirm/", {"received_by": "TEST Store"}, expected=200)
        self.assertEqual((row["delivery_status"], row["confirmed_by"], row["received_by"]), ("Delivered", "TEST admin", "TEST Store"))
        self.assertIsNotNone(row["confirmed_at"])
        self.assertEqual(self.summary()["delivered"], 1)
        # Sales shows the same delivery status
        sales_row = self.api.get(f"{API}/sales/orders/{o['id']}/").data
        self.assertEqual((sales_row["status"], sales_row["delivery_status"]), ("Delivered", "Delivered"))
        # Final: no more edits, no second confirmation
        self.assertEqual(self.api.patch(f"{API}{BASE}{o['id']}/", {"notes": "x"}, format="json").status_code, 400)
        self.post(f"{BASE}{o['id']}/confirm/", {}, expected=400)
        self.assertEqual(CustomerDelivery.objects.count(), 1)  # one record per order, never duplicated

    def test_delayed_only_with_a_passed_expected_date(self):
        no_date = self.order(days_ago=30)  # old order but no expected date: still Pending, never Delayed
        late = self.order(days_ago=5)
        res = self.api.patch(f"{API}{BASE}{late['id']}/", {"expected_delivery_date": (today() - timedelta(days=1)).isoformat()}, format="json")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["delivery_status"], "Delayed")
        due_today = self.order()
        self.api.patch(f"{API}{BASE}{due_today['id']}/", {"expected_delivery_date": today().isoformat()}, format="json")
        self.assertEqual(self.summary(), {"total": 3, "pending": 2, "in_transit": 0, "delivered": 0, "delayed": 1})
        self.assertEqual(self.api.get(f"{API}{BASE}{no_date['id']}/").data["delivery_status"], "Pending")
        self.assertEqual([r["order_number"] for r in self.api.get(f"{API}{BASE}?status=delayed").data["results"]], [late["order_number"]])
        self.assertEqual(self.api.get(f"{API}/sales/orders/{late['id']}/").data["delivery_status"], "Delayed")
        # Delivered orders are never delayed, even with an old expected date
        self.post(f"{BASE}{late['id']}/dispatch/", {"dispatched_on": (today() - timedelta(days=4)).isoformat()}, expected=200)
        self.post(f"{BASE}{late['id']}/confirm/", {}, expected=200)
        self.assertEqual(self.summary()["delayed"], 0)

    def test_validation(self):
        o = self.order(days_ago=2)
        bad = self.api.patch(f"{API}{BASE}{o['id']}/", {"expected_delivery_date": (today() - timedelta(days=5)).isoformat()}, format="json")
        self.assertIn("expected_delivery_date", bad.data)
        self.assertIn("dispatched_on", self.post(f"{BASE}{o['id']}/dispatch/", {"dispatched_on": (today() + timedelta(days=1)).isoformat()}, expected=400))
        self.post(f"{BASE}{o['id']}/dispatch/", {}, expected=200)
        self.assertIn("delivered_on", self.post(f"{BASE}{o['id']}/confirm/", {"delivered_on": (today() + timedelta(days=1)).isoformat()}, expected=400))
        self.post(f"{BASE}{o['id']}/dispatch/", {}, expected=400)  # already dispatched
        self.assertEqual(self.api.get(f"{API}{BASE}?status=wrong").status_code, 400)

    def test_cancelled_orders_are_not_deliveries(self):
        o = self.order()
        self.post(f"/sales/orders/{o['id']}/cancel/", {}, expected=200)
        self.assertEqual(self.summary()["total"], 0)
        self.assertEqual(self.api.get(f"{API}{BASE}{o['id']}/").status_code, 404)

    def test_sales_status_buttons_record_dispatch_and_confirmation(self):
        o = self.order()
        for step in ("processing", "in_transit", "delivered"):
            self.post(f"/sales/orders/{o['id']}/status/", {"status": step}, expected=200)
        d = CustomerDelivery.objects.get(order_id=o["id"])
        self.assertEqual((d.dispatched_on, d.delivered_on, d.confirmed_by), (today(), today(), self.admin))
        self.assertEqual(self.summary(), {"total": 1, "pending": 0, "in_transit": 0, "delivered": 1, "delayed": 0})

    def test_inbound_shipment_figures_are_unchanged(self):
        before = self.api.get(f"{API}/supply-chain/overview/").data
        o = self.order()
        self.post(f"{BASE}{o['id']}/dispatch/", {}, expected=200)
        after = self.api.get(f"{API}/supply-chain/overview/").data
        self.assertEqual(before["kpis"]["active_shipments"], after["kpis"]["active_shipments"])
        self.assertEqual(before["shipment_summary"], after["shipment_summary"])
        self.assertEqual(Shipment.objects.count(), 0)

    def test_permissions(self):
        o = self.order()
        sales, supply, inventory, finance = (client_for(make_user(r)) for r in ("sales", "supply_chain", "inventory", "finance"))
        self.post(f"{BASE}{o['id']}/dispatch/", {}, expected=200, api=sales)
        self.post(f"{BASE}{o['id']}/confirm/", {}, expected=403, api=inventory)  # Inventory can view, not update
        self.assertEqual(inventory.get(f"{API}{BASE}").status_code, 200)
        self.assertEqual(finance.get(f"{API}{BASE}").status_code, 403)
        self.post(f"{BASE}{o['id']}/confirm/", {}, expected=200, api=supply)
        # The dashboard block is only for roles that may see deliveries
        self.assertTrue(supply.get(f"{API}/supply-chain/overview/").data["customer_deliveries"]["can_update"])
        self.assertFalse(inventory.get(f"{API}/supply-chain/overview/").data["customer_deliveries"]["can_update"])

    def test_deleting_an_order_removes_its_delivery(self):
        o = self.order()
        self.post(f"{BASE}{o['id']}/dispatch/", {}, expected=200)
        self.assertEqual(self.api.delete(f"{API}/records/sales_order/{o['id']}/").status_code, 204)
        self.assertEqual(CustomerDelivery.objects.count(), 0)
