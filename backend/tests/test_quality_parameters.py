"""
Quality → New Test Entry: Parameter + Value rows (decimal values), saved with the test, shown again and editable
(only the rows). TEST records only.
"""
from django.test import TestCase

from apps.core.periods import today
from apps.quality.models import QualityTest
from apps.system.models import AuditLog

from .helpers import API, client_for, make_user


class QualityParameterTests(TestCase):
    def setUp(self):
        self.api = client_for(make_user("admin"))
        res = self.api.post(f"{API}/inventory/items/", {"product_name": "TEST Chilli Powder", "opening_stock_kg": 10,
                                                        "price_per_kg": 200, "min_stock_kg": 1, "reorder_level_kg": 2}, format="json")
        self.product_id = res.data["id"]

    def create(self, readings, expected=201):
        res = self.api.post(f"{API}/quality/tests/", {"product_id": self.product_id, "test_date": today().isoformat(), "result": "pass",
                                                      "readings": readings}, format="json")
        self.assertEqual(res.status_code, expected, res.data)
        return res.data

    def test_rows_are_saved_and_shown_again(self):
        rows = [{"parameter": "Moisture", "value": "8.25"}, {"parameter": "Ash", "value": "3"}, {"parameter": "Colour", "value": "-0.5"}]
        test = self.create(rows)
        self.assertEqual(test["readings"], rows)
        self.assertEqual(test["parameters"], "Moisture: 8.25; Ash: 3; Colour: -0.5")  # for search, exports and reports
        listed = self.api.get(f"{API}/quality/tests/").data["results"][0]
        self.assertEqual(listed["readings"], rows)
        self.assertEqual(self.api.get(f"{API}/quality/tests/?search=Moisture").data["count"], 1)

    def test_invalid_rows_are_refused_not_turned_into_zero(self):
        cases = [
            ([], "Add at least one parameter and its value."),
            ([{"parameter": "", "value": "1"}], "Row 1: enter the parameter name."),
            ([{"parameter": "Moisture", "value": ""}], "Row 1: enter the value."),
            ([{"parameter": "Moisture", "value": "abc"}], "Row 1: the value must be a number, e.g. 8.5."),
            ([{"parameter": "Moisture", "value": "8,5"}], "Row 1: the value must be a number, e.g. 8.5."),
            ([{"parameter": "Moisture", "value": True}], "Row 1: enter the value."),
            ([{"parameter": "Ash", "value": "1"}, {"parameter": "ash", "value": "2"}], "Row 2: ash is listed twice."),
            ("Moisture 8", "Add at least one parameter and its value."),
        ]
        for readings, message in cases:
            err = self.create(readings, expected=400)
            self.assertIn(message, err["readings"], readings)
        self.assertFalse(QualityTest.objects.exists())

    def test_edit_changes_only_the_rows(self):
        test = self.create([{"parameter": "Moisture", "value": "8.5"}])
        res = self.api.patch(f"{API}/quality/tests/{test['id']}/", {
            "readings": [{"parameter": "Moisture", "value": "9.75"}, {"parameter": "Ash", "value": "4.1"}],
            "result": "fail", "notes": "TEST ignored"}, format="json")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["readings"], [{"parameter": "Moisture", "value": "9.75"}, {"parameter": "Ash", "value": "4.1"}])
        t = QualityTest.objects.get(pk=test["id"])
        self.assertEqual((t.parameters, t.result, t.notes), ("Moisture: 9.75; Ash: 4.1", "pass", ""))  # nothing else changed
        self.assertTrue(AuditLog.objects.filter(action="Edited quality test parameters").exists())
        removed = self.api.patch(f"{API}/quality/tests/{test['id']}/", {"readings": [{"parameter": "Ash", "value": "4.1"}]}, format="json")
        self.assertEqual(removed.data["readings"], [{"parameter": "Ash", "value": "4.1"}])  # a row removed
        bad = self.api.patch(f"{API}/quality/tests/{test['id']}/", {"readings": [{"parameter": "Ash", "value": "x"}]}, format="json")
        self.assertEqual(bad.status_code, 400)
        self.assertEqual(QualityTest.objects.get(pk=test["id"]).readings, [{"parameter": "Ash", "value": "4.1"}])

    def test_older_text_entries_still_work(self):
        res = self.api.post(f"{API}/quality/tests/", {"product_id": self.product_id, "test_date": today().isoformat(), "result": "pass",
                                                      "parameters": "TEST moisture 8%"}, format="json")
        self.assertEqual((res.status_code, res.data["parameters"], res.data["readings"]), (201, "TEST moisture 8%", []))

    def test_only_quality_users_can_edit(self):
        test = self.create([{"parameter": "Moisture", "value": "8.5"}])
        sales = client_for(make_user("sales", username="seller"))
        res = sales.patch(f"{API}/quality/tests/{test['id']}/", {"readings": [{"parameter": "Moisture", "value": "1"}]}, format="json")
        self.assertEqual(res.status_code, 403)
        self.assertEqual(self.api.patch(f"{API}/quality/tests/999999/", {"readings": [{"parameter": "A", "value": "1"}]},
                                        format="json").status_code, 404)
