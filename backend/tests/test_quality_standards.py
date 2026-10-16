"""Quality standards on screen: add / edit (one limit per parameter and product, or all products), Super Admin delete."""
from django.test import TestCase

from apps.quality.models import QualityStandard
from apps.system.models import AuditLog

from .helpers import API, client_for, make_user


class QualityStandardTests(TestCase):
    def setUp(self):
        self.api = client_for(make_user("quality", username="qa"))
        admin = client_for(make_user("admin", username="boss"))
        res = admin.post(f"{API}/inventory/items/", {"product_name": "TEST Chilli Powder", "opening_stock_kg": 0, "price_per_kg": 200,
                                                     "min_stock_kg": 0, "reorder_level_kg": 0}, format="json")
        self.product = res.data["id"]
        self.admin = admin

    def add(self, expected=201, **body):
        res = self.api.post(f"{API}/quality/standards/", body, format="json")
        self.assertEqual(res.status_code, expected, res.data)
        return res.data

    def test_add_edit_and_list(self):
        s = self.add(parameter="Moisture", limit="≤ 10%")
        self.assertEqual((s["applies_to"], s["product_id"]), ("All products", None))
        p = self.add(parameter="Moisture", limit="≤ 8%", product_id=self.product)  # a product's own limit
        self.assertEqual(p["applies_to"], "TEST Chilli Powder")
        edited = self.api.patch(f"{API}/quality/standards/{s['id']}/", {"limit": "≤ 11%"}, format="json")
        self.assertEqual((edited.status_code, edited.data["limit"], edited.data["parameter"]), (200, "≤ 11%", "Moisture"))
        self.assertEqual(len(self.api.get(f"{API}/quality/standards/").data), 2)
        self.assertTrue(AuditLog.objects.filter(action="Added quality standard").exists())

    def test_duplicates_and_required_fields(self):
        self.add(parameter="Moisture", limit="≤ 10%")
        dup = self.add(expected=400, parameter="moisture", limit="≤ 9%")  # all products already has it
        self.assertIn("already has a limit", dup["parameter"][0])
        self.add(expected=400, product_id=self.product, parameter="Moisture", limit="")
        other = self.add(parameter="Ash", limit="≤ 7%")
        clash = self.api.patch(f"{API}/quality/standards/{other['id']}/", {"parameter": "Moisture"}, format="json")
        self.assertEqual(clash.status_code, 400)

    def test_permissions(self):
        s = self.add(parameter="Moisture", limit="≤ 10%")
        sales = client_for(make_user("sales", username="seller"))
        self.assertEqual(sales.post(f"{API}/quality/standards/", {"parameter": "x", "limit": "y"}, format="json").status_code, 403)
        self.assertEqual(self.api.delete(f"{API}/records/quality_standard/{s['id']}/").status_code, 403)
        self.assertEqual(self.admin.delete(f"{API}/records/quality_standard/{s['id']}/").status_code, 204)
        self.assertFalse(QualityStandard.objects.exists())
