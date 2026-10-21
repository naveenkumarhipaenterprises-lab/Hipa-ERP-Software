"""
Quality: test readings are checked against standards that have a lowest / highest value (a product's own standard
first, else the one for all items), and certificates near or past expiry are reminded once. TEST records only.
"""
import io
from datetime import timedelta

from django.core.management import call_command
from django.test import TestCase

from apps.core.periods import today
from apps.quality.models import Certification
from apps.system.models import Notification

from .helpers import API, client_for, make_user


class StandardCheckTests(TestCase):
    def setUp(self):
        self.api = client_for(make_user("admin"))
        self.product_id = self.post("/inventory/items/", {"product_name": "TEST Chilli Powder", "opening_stock_kg": 10,
                                                          "price_per_kg": 200, "min_stock_kg": 1, "reorder_level_kg": 2})["id"]

    def post(self, path, body, expected=201):
        res = self.api.post(API + path, body, format="json")
        self.assertEqual(res.status_code, expected, res.data)
        return res.data

    def record(self, *readings):
        return self.post("/quality/tests/", {"product_id": self.product_id, "test_date": today().isoformat(), "result": "pass",
                                             "readings": [{"parameter": p, "value": v} for p, v in readings]})

    def test_readings_outside_the_numbers_are_flagged(self):
        self.post("/quality/standards/", {"parameter": "Moisture", "limit": "≤ 10%", "max_value": "10"})
        self.post("/quality/standards/", {"parameter": "Ash", "limit": "2 – 7%", "min_value": "2", "max_value": "7"})
        self.post("/quality/standards/", {"parameter": "Colour", "limit": "Bright red"})  # text only: not checked
        row = self.record(("moisture", "12.5"), ("Ash", "2"), ("Colour", "80"), ("Pungency", "40"))
        self.assertEqual(row["outside_standard"], ["moisture"])
        self.assertEqual([(c["standard"], c["within_standard"]) for c in row["checks"]],
                         [("≤ 10%", False), ("2 – 7%", True), (None, None), (None, None)])
        self.assertEqual(row["readings"][0], {"parameter": "moisture", "value": "12.5"})  # stored as entered
        listed = self.api.get(f"{API}/quality/tests/").data["results"][0]
        self.assertEqual(listed["outside_standard"], ["moisture"])

    def test_a_products_own_standard_comes_before_the_one_for_all_items(self):
        self.post("/quality/standards/", {"parameter": "Moisture", "limit": "≤ 10%", "max_value": "10"})
        self.post("/quality/standards/", {"parameter": "Moisture", "limit": "≤ 12% for chilli", "max_value": "12",
                                          "product_id": self.product_id})
        self.assertEqual(self.record(("Moisture", "11"))["outside_standard"], [])

    def test_lowest_and_highest_values_are_validated_and_editable(self):
        bad = self.post("/quality/standards/", {"parameter": "Ash", "limit": "x", "min_value": "7", "max_value": "2"}, expected=400)
        self.assertIn("max_value", bad)
        self.assertIn("min_value", self.post("/quality/standards/", {"parameter": "Ash", "limit": "x", "min_value": "abc"}, expected=400))
        s = self.post("/quality/standards/", {"parameter": "Ash", "limit": "≤ 7%", "max_value": "7"})
        self.assertEqual((s["min_value"], s["max_value"]), (None, 7))
        edited = self.api.patch(f"{API}/quality/standards/{s['id']}/", {"min_value": "1.5"}, format="json").data
        self.assertEqual((edited["min_value"], edited["max_value"], edited["limit"]), (1.5, 7, "≤ 7%"))
        cleared = self.api.patch(f"{API}/quality/standards/{s['id']}/", {"max_value": ""}, format="json").data
        self.assertEqual(cleared["max_value"], None)


class CertificateExpiryAlertTests(TestCase):
    def setUp(self):
        make_user("quality", username="qc")

    def cert(self, name, days, **extra):
        return Certification.objects.create(name=name, valid_until=today() + timedelta(days=days), **extra)

    def titles(self):
        return sorted(set(Notification.objects.filter(key="certification_expiry").values_list("title", flat=True)))

    def run_alerts(self):
        call_command("send_due_alerts", stdout=io.StringIO())
        return Notification.objects.filter(key="certification_expiry").count()

    def test_near_and_past_expiry_are_reminded_once(self):
        soon, gone = self.cert("TEST FSSAI", 20), self.cert("TEST ISO", -1)
        self.cert("TEST Far", 200)
        self.cert("TEST Suspended", 5, status=Certification.Status.SUSPENDED)
        first = self.run_alerts()
        self.assertGreater(first, 0)
        self.assertEqual(self.run_alerts(), first)  # the next day's run doesn't repeat them
        self.assertEqual(self.titles(), sorted([f"TEST FSSAI certificate expires on {soon.valid_until:%d %b %Y}",
                                                f"TEST ISO certificate expired on {gone.valid_until:%d %b %Y}"]))

    def test_a_renewed_certificate_is_reminded_again(self):
        c = self.cert("TEST FSSAI", 10)
        self.run_alerts()
        c.valid_until = today() + timedelta(days=30)
        c.save()
        self.run_alerts()
        self.assertEqual(len(self.titles()), 2)
