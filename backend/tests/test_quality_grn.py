"""
Quality tests linked to a goods receipt (GRN), including a GRN that was recorded as Passed when it was received
(it used to be offered only while awaiting inspection, so such tests were saved without their GRN). TEST records only.
"""
from datetime import timedelta

from django.test import TestCase

from apps.core.periods import today
from apps.purchase.models import GoodsReceipt
from apps.quality.models import QualityTest

from .helpers import API, client_for, make_user


class QualityGrnTests(TestCase):
    def setUp(self):
        self.api = client_for(make_user("admin"))

    def post(self, path, body, expected=201):
        res = self.api.post(API + path, body, format="json")
        self.assertEqual(res.status_code, expected, f"{path}: {res.data}")
        return res.data

    def received(self, quality_status=None):
        s = self.post("/purchase/suppliers/", {"name": "TEST Farms", "city": "Erode"})
        m = self.post("/purchase/raw-materials/", {"name": "TEST Raw Pepper", "category": "whole_spice", "unit": "kg", "reorder_level": 10})
        p = self.post("/purchase/purchases/", {"supplier_id": s["id"], "material_id": m["id"], "quantity": 20, "unit_price": 500,
                                               "purchase_date": today().isoformat(), "expected_receipt_date": today().isoformat()})
        body = {"purchase_id": p["id"], "received_date": today().isoformat(), "received_quantity": 20}
        if quality_status:
            body["quality_status"] = quality_status
        return self.post("/purchase/goods-receipts/", body)

    def test_a_grn_passed_at_receipt_can_be_tested_and_shows_in_the_results(self):
        grn = self.received(quality_status="passed")
        options = self.api.get(f"{API}/quality/options/").data
        self.assertEqual(options["pending_receipts"], [])  # not awaiting inspection...
        self.assertEqual([g["grn_number"] for g in options["goods_receipts"]], [grn["grn_number"]])  # ...but offered for testing
        test = self.post("/quality/tests/", {"goods_receipt_id": grn["id"], "batch_number": "TEST-LOT", "test_date": today().isoformat(),
                                             "result": "pass", "readings": [{"parameter": "Moisture", "value": "11.5"}]})
        self.assertEqual((test["grn_number"], test["goods_receipt_id"], test["product"]), (grn["grn_number"], grn["id"], "TEST Raw Pepper"))
        self.assertEqual(QualityTest.objects.get(pk=test["id"]).goods_receipt_id, grn["id"])  # saved in the database
        listed = self.api.get(f"{API}/quality/tests/").data["results"]  # what the table shows after a reload
        self.assertEqual([(r["id"], r["grn_number"]) for r in listed], [(test["id"], grn["grn_number"])])
        self.assertEqual(self.api.get(f"{API}/quality/tests/?search={grn['grn_number']}").data["count"], 1)  # search by GRN

    def test_the_grn_follows_its_latest_test_and_unlinked_tests_stay_unlinked(self):
        grn = self.received(quality_status="passed")
        unlinked = self.post("/quality/tests/", {"material_id": GoodsReceipt.objects.get().purchase.material_id,
                                                 "test_date": today().isoformat(), "result": "pass", "parameters": "TEST"})
        self.assertIsNone(unlinked["grn_number"])
        self.post("/quality/tests/", {"goods_receipt_id": grn["id"], "test_date": today().isoformat(), "result": "fail",
                                      "readings": [{"parameter": "Moisture", "value": "16"}]})
        self.assertEqual(GoodsReceipt.objects.get(pk=grn["id"]).quality_status, "failed")
        self.assertIsNone(QualityTest.objects.get(pk=unlinked["id"]).goods_receipt_id)  # never linked by guesswork

    def test_awaiting_inspection_comes_first(self):
        passed = self.received(quality_status="passed")
        waiting = self.received_again()  # Pending Inspection
        GoodsReceipt.objects.filter(pk=waiting["id"]).update(received_date=today() - timedelta(days=3))  # older than the passed one
        numbers = [g["grn_number"] for g in self.api.get(f"{API}/quality/options/").data["goods_receipts"]]
        self.assertEqual(numbers, [waiting["grn_number"], passed["grn_number"]])

    def received_again(self):
        s_id = GoodsReceipt.objects.get().purchase.supplier_id
        m_id = GoodsReceipt.objects.get().purchase.material_id
        p = self.post("/purchase/purchases/", {"supplier_id": s_id, "material_id": m_id, "quantity": 5, "unit_price": 500,
                                               "purchase_date": today().isoformat(), "expected_receipt_date": today().isoformat()})
        return self.post("/purchase/goods-receipts/", {"purchase_id": p["id"], "received_date": today().isoformat(),
                                                       "received_quantity": 5})  # Pending Inspection by default
