"""
Marketing → Enter Data: daily numbers, content and audience splits entered from each platform's analytics, and how
they show on the Marketing dashboard. TEST records only.
"""
from datetime import timedelta

from django.test import TestCase

from apps.core.periods import today
from apps.marketing.models import AudienceSegment, ContentItem, MarketingMetric
from apps.system.models import AuditLog

from .helpers import API, client_for, make_user


class MarketingEntryTests(TestCase):
    def setUp(self):
        self.api = client_for(make_user("marketing", username="mkt"))

    def call(self, method, path, body=None, expected=200):
        res = getattr(self.api, method)(f"{API}/marketing/{path}", body or {}, format="json")
        self.assertEqual(res.status_code, expected, f"{method.upper()} {path}: {getattr(res, 'data', '')}")
        return res.data

    def metric(self, expected=201, **extra):
        return self.call("post", "metrics/", {"date": today().isoformat(), "platform": "instagram", "reach": 1200,
                                              "engagement": 300, "website_visitors": 80, "leads": 6, "sales_amount": "4500.50",
                                              **extra}, expected)

    def test_daily_numbers_reach_the_dashboard(self):
        m = self.metric()
        self.assertEqual((m["platform"], m["reach"], m["sales_amount"]), ("Instagram", 1200, 4500.5))
        ov = self.call("get", "overview/?range=this_month")
        self.assertEqual((ov["kpis"]["reach"]["value"], ov["kpis"]["marketing_sales"]["value"]), (1200, 4500.5))
        self.assertEqual(self.call("get", "metrics/")["count"], 1)
        self.assertTrue(AuditLog.objects.filter(action="Added marketing numbers").exists())

    def test_one_entry_per_day_platform_and_campaign(self):
        self.metric()
        err = self.metric(expected=400)
        self.assertIn("already entered", err["detail"])
        self.metric(platform="facebook")  # another platform the same day is fine
        self.assertEqual(MarketingMetric.objects.count(), 2)

    def test_invalid_numbers_are_refused_not_turned_into_zero(self):
        cases = [({"reach": "abc"}, "reach"), ({"leads": -3}, "leads"), ({"leads": "2.5"}, "leads"),
                 ({"sales_amount": "-1"}, "sales_amount"), ({"sales_amount": "10.123"}, "sales_amount"),
                 ({"date": (today() + timedelta(days=1)).isoformat()}, "date"), ({"platform": "myspace"}, "platform"),
                 ({"reach": 0, "engagement": 0, "website_visitors": 0, "leads": 0, "sales_amount": 0}, "detail")]
        for fields, field in cases:
            err = self.metric(expected=400, **fields)
            self.assertIn(field, err, fields)
        self.assertFalse(MarketingMetric.objects.exists())

    def test_a_campaign_must_run_on_that_platform(self):
        c = self.call("post", "campaigns/", {"name": "TEST Diwali", "platform": "facebook", "objective": "sales",
                                             "start_date": today().isoformat(), "end_date": today().isoformat(), "budget": 1000}, 201)
        self.assertIn("campaign_id", self.metric(expected=400, campaign_id=c["id"]))
        m = self.metric(platform="facebook", campaign_id=c["id"])
        self.assertEqual(m["campaign"], "TEST Diwali")
        self.assertEqual(self.call("get", "campaigns/")["results"][0]["reach"], 1200)  # shows on the campaign

    def test_edit_keeps_what_is_not_sent(self):
        m = self.metric()
        edited = self.call("patch", f"metrics/{m['id']}/", {"leads": 9})
        self.assertEqual((edited["leads"], edited["reach"]), (9, 1200))
        self.assertIn("reach", self.call("patch", f"metrics/{m['id']}/", {"reach": "x"}, 400))

    def test_content_and_top_content(self):
        c = self.call("post", "content/", {"title": "TEST Sambar recipe reel", "platform": "instagram",
                                           "published_on": today().isoformat(), "views": 5000, "likes": 400, "shares": 50,
                                           "url": "https://instagram.com/p/test"}, 201)
        self.assertEqual(c["views"], 5000)
        top = self.call("get", "overview/?range=this_month")["top_content"]
        self.assertEqual(top[0]["title"], "TEST Sambar recipe reel")
        self.assertIn("url", self.call("post", "content/", {"title": "TEST", "platform": "instagram",
                                                            "published_on": today().isoformat(), "url": "not a link"}, 400))
        self.assertIn("title", self.call("post", "content/", {"platform": "instagram", "published_on": today().isoformat()}, 400))
        self.assertEqual(self.call("patch", f"content/{c['id']}/", {"views": 6000})["views"], 6000)

    def test_audience_shares(self):
        day = today().isoformat()
        self.call("post", "audience-segments/", {"platform": "instagram", "name": "25-34", "value": "38.5", "as_of": day}, 201)
        self.call("post", "audience-segments/", {"platform": "instagram", "name": "18-24", "value": 22, "as_of": day}, 201)
        self.assertIn("value", self.call("post", "audience-segments/", {"platform": "instagram", "name": "35-44", "value": 120,
                                                                         "as_of": day}, 400))  # a share is at most 100%
        dup = self.call("post", "audience-segments/", {"platform": "instagram", "name": "25-34", "value": 30, "as_of": day}, 400)
        self.assertIn("already entered", dup["detail"])
        shown = {r["name"]: r["value"] for r in self.call("get", "audience/")}
        self.assertEqual(shown, {"18-24": 22.0, "25-34": 38.5})

    def test_permissions_and_super_admin_delete(self):
        m = self.metric()
        c = self.call("post", "content/", {"title": "TEST", "platform": "youtube", "published_on": today().isoformat()}, 201)
        sales = client_for(make_user("sales", username="seller"))
        self.assertEqual(sales.post(f"{API}/marketing/metrics/", {}, format="json").status_code, 403)
        self.assertEqual(sales.get(f"{API}/marketing/metrics/").status_code, 403)
        self.assertEqual(self.api.delete(f"{API}/records/marketing_metric/{m['id']}/").status_code, 403)  # Super Admins only
        admin = client_for(make_user("admin", username="boss"))
        self.assertEqual(admin.delete(f"{API}/records/marketing_metric/{m['id']}/").status_code, 204)
        self.assertEqual(admin.delete(f"{API}/records/content_item/{c['id']}/").status_code, 204)
        self.assertFalse(MarketingMetric.objects.exists() or ContentItem.objects.exists())
        self.assertFalse(AudienceSegment.objects.exists())

    def test_filters(self):
        self.metric()
        self.metric(platform="youtube", date=(today() - timedelta(days=40)).isoformat())
        self.assertEqual(self.call("get", "metrics/?platform=youtube")["count"], 1)
        self.assertEqual(self.call("get", f"metrics/?date_from={(today() - timedelta(days=7)).isoformat()}")["count"], 1)
        self.assertIn("date_from", self.call("get", "metrics/?date_from=yesterday", expected=400))


class CampaignEditAndPostTests(MarketingEntryTests):
    def campaign(self, platform="instagram"):
        return self.call("post", "campaigns/", {"name": "TEST Diwali", "platform": platform, "objective": "sales",
                                               "start_date": today().isoformat(), "end_date": (today() + timedelta(days=10)).isoformat(),
                                               "budget": 5000}, 201)

    def test_edit_a_campaign(self):
        c = self.campaign()
        self.assertTrue(c["can_edit"])
        res = self.call("patch", f"campaigns/{c['id']}/", {"name": "TEST Diwali Sale", "budget": "7500.50"})
        self.assertEqual((res["name"], res["budget"], res["platform"]), ("TEST Diwali Sale", 7500.5, "Instagram"))
        self.assertIn("end_date", self.call("patch", f"campaigns/{c['id']}/", {"end_date": (today() - timedelta(days=1)).isoformat()}, 400))
        self.assertTrue(AuditLog.objects.filter(action="Edited campaign").exists())
        seller = client_for(make_user("sales", username="seller2"))
        self.assertEqual(seller.patch(f"{API}/marketing/campaigns/{c['id']}/", {"name": "x"}, format="json").status_code, 403)

    def test_platform_is_fixed_once_numbers_are_entered(self):
        c = self.campaign()
        self.assertEqual(self.call("patch", f"campaigns/{c['id']}/", {"platform": "youtube"})["platform"], "YouTube")  # no numbers yet
        self.call("patch", f"campaigns/{c['id']}/", {"platform": "instagram"})
        self.metric(campaign_id=c["id"])
        err = self.call("patch", f"campaigns/{c['id']}/", {"platform": "youtube"}, 400)
        self.assertIn("can't change", err["platform"][0])

    def test_a_post_links_to_its_campaign_and_only_a_super_admin_deletes_it(self):
        from django.utils import timezone

        c = self.campaign()
        when = (timezone.now() + timedelta(days=2)).isoformat()
        self.assertIn("campaign_id", self.call("post", "posts/", {"platform": "instagram", "scheduled_for": when, "caption": "TEST",
                                                                   "campaign_id": 999999}, 400))
        post = self.call("post", "posts/", {"platform": "youtube", "scheduled_for": when, "caption": "TEST", "campaign_id": c["id"]}, 201)
        self.assertEqual(post["campaign"], "TEST Diwali")
        self.assertEqual(self.api.delete(f"{API}/records/scheduled_post/{post['id']}/").status_code, 403)  # Super Admins only
        admin = client_for(make_user("admin", username="boss2"))
        self.assertEqual(admin.delete(f"{API}/records/scheduled_post/{post['id']}/").status_code, 204)
