from datetime import date

from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError

from apps.core.metrics import kpi, pct_change
from apps.core.periods import last_n_months, resolve


class PeriodTests(SimpleTestCase):
    def test_this_month_compares_same_days_of_previous_month(self):
        cur, prev = resolve("this_month", date(2026, 3, 31))
        self.assertEqual((cur.start, cur.end), (date(2026, 3, 1), date(2026, 3, 31)))
        self.assertEqual((prev.start, prev.end), (date(2026, 2, 1), date(2026, 2, 28)))

    def test_last_month_across_new_year(self):
        cur, prev = resolve("last_month", date(2026, 1, 15))
        self.assertEqual((cur.start, cur.end), (date(2025, 12, 1), date(2025, 12, 31)))
        self.assertEqual((prev.start, prev.end), (date(2025, 11, 1), date(2025, 11, 30)))

    def test_last_3_months(self):
        cur, prev = resolve("last_3_months", date(2026, 2, 10))
        self.assertEqual((cur.start, cur.end), (date(2025, 11, 1), date(2026, 1, 31)))
        self.assertEqual((prev.start, prev.end), (date(2025, 8, 1), date(2025, 10, 31)))

    def test_this_year(self):
        cur, prev = resolve("this_year", date(2026, 9, 28))
        self.assertEqual((cur.start, cur.end), (date(2026, 1, 1), date(2026, 9, 28)))
        self.assertEqual(prev.start, date(2025, 1, 1))
        self.assertEqual(prev.days, cur.days)

    def test_unknown_range(self):
        with self.assertRaises(ValidationError):
            resolve("forever")

    def test_last_n_months_spans_december(self):
        months = last_n_months(12, date(2026, 9, 28))
        self.assertEqual(months[0][2], "Oct 2025")
        self.assertEqual(months[2], (date(2025, 12, 1), date(2025, 12, 31), "Dec 2025"))
        self.assertEqual(months[-1], (date(2026, 9, 1), date(2026, 9, 28), "Sep 2026"))

    def test_change_needs_a_previous_value(self):
        self.assertIsNone(pct_change(100, 0))
        self.assertEqual(pct_change(150, 100), 50.0)
        self.assertEqual(kpi(5, 0), {"value": 5})
        self.assertEqual(kpi(5, 4), {"value": 5, "change": 25.0})
