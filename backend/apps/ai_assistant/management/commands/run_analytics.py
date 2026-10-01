"""
Runs the analytics engine (ml/) on real records and replaces the stored insights.
Schedule it daily (e.g. Windows Task Scheduler). Parts without enough data are skipped
and reported, never filled with estimates.
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from apps.ai_assistant.models import AnalyticsRun, Insight
from apps.core.periods import today
from ml.anomaly import sales_anomalies
from ml.data import InsufficientData
from ml.segmentation import segment_customers
from ml.stockout import stockout_risks

MIN_TESTS_PER_PRODUCT = 5
FAIL_RATE_ALERT_PCT = 20


def inr(v):
    return f"₹{v:,.0f}"


def stock_insights():
    result = stockout_risks()
    if isinstance(result, InsufficientData):
        return result, []
    out = []
    for r in result["risks"][:5]:
        out.append(Insight(kind=Insight.Kind.STOCK, module="inventory", title=f"{r['product']} may run out in {r['days_left']:g} days",
                           text=f"{r['product']} has {r['stock_kg']:g} kg in stock and sells about {r['daily_demand_kg']:g} kg a day "
                                f"(forecast from recent sales), so it lasts about {r['days_left']:g} days.",
                           action=f"Schedule production of {r['product']} or reorder soon.", data=r))
    return result, out


def anomaly_insights():
    result = sales_anomalies()
    if isinstance(result, InsufficientData):
        return result, []
    out = []
    for a in result["anomalies"]:
        word = "higher" if a["direction"] == "high" else "lower"
        out.append(Insight(kind=Insight.Kind.ANOMALY, module="sales", title=f"Unusual sales on {a['date']}",
                           text=f"Sales on {a['date']} were {inr(a['sales'])}, much {word} than the usual {inr(result['median_daily_sales'])} a day.",
                           action="Check the orders from that day." if a["direction"] == "high" else "Look into why sales dropped that day.",
                           data=a))
    return result, out


def segment_insights():
    result = segment_customers()
    if isinstance(result, InsufficientData):
        return result, []
    out = []
    for s in result["segments"]:
        out.append(Insight(kind=Insight.Kind.SEGMENT, module="customers", title=f"{s['name']} customers: {s['customers']}",
                           text=f"{s['customers']} {s['name'].lower()} customers bring {s['share_of_sales_pct']:g}% of sales "
                                f"(average {inr(s['avg_spend'])} over {s['avg_orders']:g} orders; last order about {s['avg_days_since_order']} days ago).",
                           data=s))
    return result, out


def quality_insights():
    from apps.quality.models import QualityTest

    since = today() - timedelta(days=90)
    rows = (QualityTest.objects.filter(test_date__gte=since).values("batch__product__name")
            .annotate(n=Count("id"), failed=Count("id", filter=Q(result="fail"))).filter(n__gte=MIN_TESTS_PER_PRODUCT))
    rows = list(rows)
    if not rows:
        return InsufficientData(f"Needs at least {MIN_TESTS_PER_PRODUCT} quality tests for a product in the last 90 days."), []
    out = []
    for r in rows:
        rate = r["failed"] / r["n"] * 100
        if rate >= FAIL_RATE_ALERT_PCT:
            out.append(Insight(kind=Insight.Kind.QUALITY, module="quality", title=f"{r['batch__product__name']}: {rate:.0f}% of tests failed",
                               text=f"{r['failed']} of {r['n']} tests for {r['batch__product__name']} failed in the last 90 days.",
                               action=f"Review raw material and process checks for {r['batch__product__name']}.",
                               data={"product": r["batch__product__name"], "tests": r["n"], "failed": r["failed"]}))
    return {"products_checked": len(rows)}, out


class Command(BaseCommand):
    help = "Generate insights (stock-out risk, sales anomalies, customer segments, quality) from real data."

    def handle(self, *args, **options):
        run = AnalyticsRun.objects.create()
        summary, insights = {}, []
        for name, fn in (("stockout", stock_insights), ("anomalies", anomaly_insights),
                         ("segments", segment_insights), ("quality", quality_insights)):
            result, found = fn()
            summary[name] = result.as_dict() if isinstance(result, InsufficientData) else {"status": "ok", "insights": len(found)}
            insights += found
            state = summary[name].get("message") or f"{len(found)} insight(s)"
            self.stdout.write(f"{name}: {state}")
        with transaction.atomic():
            Insight.objects.all().delete()
            Insight.objects.bulk_create(insights)
        run.finished_at = timezone.now()
        run.summary = summary
        run.save()
        self.stdout.write(self.style.SUCCESS(f"Stored {len(insights)} insight(s)."))
