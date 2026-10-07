"""
The database is remote (Supabase), so every query is a network round trip. These tests make sure the busiest
pages use a fixed number of queries however many products, materials or orders exist (no N+1), and that the
AI purchase recommendations are reused until their input data changes.
"""
from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.core.cache import cache
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from apps.core.periods import today
from apps.customers.models import Customer
from apps.inventory.models import Product
from apps.purchase.models import MaterialMovement, Purchase, RawMaterial, Supplier
from apps.purchase.services import move_material
from apps.sales.models import SalesOrder

from .helpers import API, client_for, make_user

PAGES = ["/dashboard/summary/", "/dashboard/sales-trend/", "/sales/overview/", "/supply-chain/overview/", "/purchase/overview/"]


class QueryCountTests(TestCase):
    def setUp(self):
        self.api = client_for(make_user("admin"))
        self.supplier = Supplier.objects.create(name="TEST Farms", city="Erode")
        self.made = 0

    def add(self, n):
        for _ in range(n):
            i = self.made = self.made + 1
            product = Product.objects.create(name=f"TEST Product {i}", price_per_kg=Decimal("100"))
            customer = Customer.objects.create(name=f"TEST Customer {i}", type="retailer", city="Erode")
            for days_ago in (1, 40, 100):  # sales in several months, so every trend bucket has data
                order = SalesOrder.objects.create(customer=customer, order_date=today() - timedelta(days=days_ago))
                order.items.create(product=product, quantity_kg=Decimal("2"), unit_price=Decimal("100"))
                order.recalculate_total()
            material = RawMaterial.objects.create(name=f"TEST Material {i}", category="seed", unit="kg", reorder_level=5)
            move_material(material, "in", 50, source=MaterialMovement.Source.OPENING, date=today() - timedelta(days=20))
            move_material(material, "out", 5, source=MaterialMovement.Source.USAGE, date=today() - timedelta(days=2))
            Purchase.objects.create(supplier=self.supplier, material=material, unit="kg", quantity=10, unit_price=5,
                                    purchase_date=today() - timedelta(days=3))

    def counts(self):
        out = {}
        for path in PAGES:
            with CaptureQueriesContext(connection) as ctx:
                res = self.api.get(API + path)
            self.assertEqual(res.status_code, 200, path)
            out[path] = len(ctx)
        return out

    def test_query_counts_do_not_grow_with_data(self):
        self.add(1)
        few = self.counts()
        self.add(9)
        many = self.counts()
        for path in PAGES:
            self.assertEqual(many[path], few[path], f"{path}: {few[path]} queries with 1 item, {many[path]} with 10")

    def test_dashboard_stays_small(self):
        self.add(3)
        self.assertLessEqual(self.counts()["/dashboard/summary/"], 25)

    def test_sales_overview_trend_matches_per_month_totals(self):
        self.add(2)
        data = self.api.get(f"{API}/sales/overview/?range=this_year").data
        for row in data["products"]:
            self.assertEqual(len(row["trend"]), 6)
            self.assertEqual(row["trend"][-1], 200)  # this month: 2 kg x ₹100
        trend = self.api.get(f"{API}/dashboard/sales-trend/?period=last_6_months").data
        self.assertEqual(trend[-1]["sales"], 400)  # two products this month


class RecommendationCacheTests(TestCase):
    def setUp(self):
        cache.clear()
        self.api = client_for(make_user("admin"))
        self.engine = mock.Mock(side_effect=lambda horizon: {"status": "insufficient_data", "horizon_days": horizon, "rows": [],
                                                             "summary": {}, "insufficient": [], "message": "TEST"})
        patcher = mock.patch("apps.purchase.views.load_analytics", return_value=self.engine)
        patcher.start()
        self.addCleanup(patcher.stop)

    def get(self, horizon=30):
        res = self.api.get(f"{API}/purchase/recommendations/?horizon={horizon}")
        self.assertEqual(res.status_code, 200)
        return res.data

    def test_results_are_reused_until_the_data_changes(self):
        self.get()
        self.get()
        self.assertEqual(self.engine.call_count, 1)  # second visit served from the cache
        self.get(horizon=7)
        self.assertEqual(self.engine.call_count, 2)  # a different horizon is its own result
        material = RawMaterial.objects.create(name="TEST Pepper", category="whole_spice", unit="kg")
        move_material(material, "in", 10, source=MaterialMovement.Source.OPENING)
        self.get()
        self.assertEqual(self.engine.call_count, 3)  # new stock data: recomputed
        self.get()
        self.assertEqual(self.engine.call_count, 3)

    def test_export_uses_the_same_cache(self):
        self.get()
        res = self.api.get(f"{API}/purchase/recommendations/export/?horizon=30")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(self.engine.call_count, 1)
