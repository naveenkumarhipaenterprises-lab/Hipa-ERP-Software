"""The campaign list and the dashboard's low-stock block don't run one query per record. TEST records only."""
from datetime import timedelta

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from apps.core.periods import today
from apps.inventory.models import Product
from apps.marketing.models import Campaign, MarketingMetric

from .helpers import API, client_for, make_user


class CampaignListQueryTests(TestCase):
    def campaign(self, n):
        c = Campaign.objects.create(name=f"TEST Campaign {n}", platform="instagram", objective="awareness", budget=1000,
                                    start_date=today() - timedelta(days=10), end_date=today() + timedelta(days=10))
        for day in (1, 2):
            MarketingMetric.objects.create(campaign=c, platform="instagram", date=today() - timedelta(days=day),
                                           reach=100 * n, engagement=1, website_visitors=1, leads=n, sales_amount=50)
        return c

    def queries_for_list(self, api):
        with CaptureQueriesContext(connection) as ctx:
            rows = api.get(f"{API}/marketing/campaigns/").data["results"]
        return len(ctx.captured_queries), rows

    def test_same_number_of_queries_for_one_or_many_campaigns(self):
        api = client_for(make_user("admin"))
        self.campaign(1)
        one, _ = self.queries_for_list(api)
        for n in range(2, 7):
            self.campaign(n)
        many, rows = self.queries_for_list(api)
        self.assertEqual(one, many)
        third = next(r for r in rows if r["name"] == "TEST Campaign 3")
        self.assertEqual((third["reach"], third["leads"], third["sales"]), (600, 6, 100))  # both days added up


class DashboardLowStockTests(TestCase):
    def test_low_stock_matches_the_stock_status_rule_and_order(self):
        def product(name, stock, minimum, reorder, active=True):
            return Product.objects.create(name=name, price_per_kg=100, stock_kg=stock, min_stock_kg=minimum,
                                          reorder_level_kg=reorder, is_active=active)

        product("TEST Plenty", 100, 10, 30)
        product("TEST Low", 25, 10, 30)
        product("TEST Critical", 5, 10, 30)
        product("TEST Out", 0, 10, 30)
        product("TEST At Reorder", 30, 10, 30)
        product("TEST Off", 0, 10, 30, active=False)
        rows = client_for(make_user("admin")).get(f"{API}/dashboard/summary/").data["low_stock"]
        self.assertEqual([(r["product"], r["status"]) for r in rows],
                         [("TEST Out", "Out of Stock"), ("TEST Critical", "Critical"), ("TEST Low", "Low Stock"),
                          ("TEST At Reorder", "Low Stock")])
