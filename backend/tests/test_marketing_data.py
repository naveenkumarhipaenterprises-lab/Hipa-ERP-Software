"""Marketing figures entered in the admin: one metrics row per day and platform, and audience shares that stay within 100%."""
from datetime import date
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.accounts.models import User
from apps.marketing.models import AudienceSegment, MarketingMetric

from .helpers import API, PASSWORD, client_for, make_user


class MarketingDataTests(TestCase):
    def test_one_metrics_row_per_day_and_platform_without_a_campaign(self):
        MarketingMetric.objects.create(date=date(2026, 10, 1), platform="instagram", reach=100)
        with self.assertRaises(IntegrityError), transaction.atomic():
            MarketingMetric.objects.create(date=date(2026, 10, 1), platform="instagram", reach=100)
        MarketingMetric.objects.create(date=date(2026, 10, 1), platform="facebook", reach=50)  # other platform is fine

    def test_audience_shares_from_several_platforms_are_averaged(self):
        for platform, young, older in (("instagram", 60, 40), ("facebook", 20, 80)):
            AudienceSegment.objects.create(platform=platform, name="18-34", value=Decimal(young), as_of=date(2026, 10, 1))
            AudienceSegment.objects.create(platform=platform, name="35+", value=Decimal(older), as_of=date(2026, 10, 1))
        api = client_for(make_user("admin"))
        rows = {r["name"]: r["value"] for r in api.get(f"{API}/marketing/audience/").data}
        self.assertEqual(rows, {"18-34": 40, "35+": 60})
        rows = {r["name"]: r["value"] for r in api.get(f"{API}/marketing/audience/?platform=instagram").data}
        self.assertEqual(rows, {"18-34": 60, "35+": 40})


class SuperuserRoleTests(TestCase):
    def test_superuser_is_stored_as_admin(self):
        su = User.objects.create_superuser(username="TEST_root", email="root@test.invalid", password=PASSWORD, name="TEST Root")
        su.refresh_from_db()
        self.assertEqual(su.role, "admin")
        self.assertEqual(make_user("sales").role, "sales")  # ordinary users keep their role
