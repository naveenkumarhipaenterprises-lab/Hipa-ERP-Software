"""
Runs the analytics engine (ml/) on real records and replaces the stored insights.
Schedule it daily (e.g. Windows Task Scheduler). Parts without enough data are skipped
and reported, never filled with estimates.
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count, Q
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.ai_assistant.models import AnalyticsRun, Insight
from apps.core.periods import today
from ml.anomaly import sales_anomalies
from ml.data import InsufficientData
from ml.purchasing import recommend
from services import notifications
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
                           action=f"Plan a purchase of {r['product']} soon.", data=r))
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
    rows = (QualityTest.objects.filter(test_date__gte=since).annotate(item=Coalesce("product__name", "material__name"))
            .values("item").annotate(n=Count("id"), failed=Count("id", filter=Q(result="fail"))).filter(n__gte=MIN_TESTS_PER_PRODUCT))
    rows = list(rows)
    if not rows:
        return InsufficientData(f"Needs at least {MIN_TESTS_PER_PRODUCT} quality tests for an item in the last 90 days."), []
    out = []
    for r in rows:
        rate = r["failed"] / r["n"] * 100
        if rate >= FAIL_RATE_ALERT_PCT:
            out.append(Insight(kind=Insight.Kind.QUALITY, module="quality", title=f"{r['item']}: {rate:.0f}% of tests failed",
                               text=f"{r['failed']} of {r['n']} tests for {r['item']} failed in the last 90 days.",
                               action=f"Review supplier and incoming quality checks for {r['item']}.",
                               data={"item": r["item"], "tests": r["n"], "failed": r["failed"]}))
    return {"products_checked": len(rows)}, out


def purchase_insights():
    result = recommend(30)
    if result["status"] != "ok":
        return InsufficientData(result["message"]), []
    out = []
    for r in result["rows"]:
        if r["priority"] != "HIGH":
            continue
        qty = f"{r['recommended_quantity']:g} {r['unit']}"
        cover = f"about {r['days_of_cover']:g} days of {r['demand_basis']}" if r["days_of_cover"] is not None else "little cover"
        lead = f", supplier lead time about {r['lead_time_days']:g} days" if r["lead_time_days"] is not None else ""
        cost = f" (about {inr(r['estimated_cost'])} at the last price)" if r["estimated_cost"] else ""
        out.append(Insight(kind=Insight.Kind.PURCHASE, module="purchase", title=f"Buy {qty} of {r['item']}",
                           text=f"{r['item']} has {r['current_stock']:g} {r['unit']} in stock and {r['on_order']:g} on order: "
                                f"{cover}{lead}.",
                           action=f"Purchase {qty} of {r['item']}{cost}" + (f" — lowest recent price from {r['best_supplier']}."
                                                                            if r["best_supplier"] else "."),
                           data={k: v for k, v in r.items() if k != "notes"}))
    return {"items": len(result["rows"])}, out


class Command(BaseCommand):
    help = "Generate insights (stock-out risk, sales anomalies, customer segments, quality, purchase recommendations) from real data."

    def handle(self, *args, **options):
        run = AnalyticsRun.objects.create()
        summary, insights = {}, []
        for name, fn in (("stockout", stock_insights), ("anomalies", anomaly_insights),
                         ("segments", segment_insights), ("quality", quality_insights), ("purchase", purchase_insights)):
            result, found = fn()
            summary[name] = result.as_dict() if isinstance(result, InsufficientData) else {"status": "ok", "insights": len(found)}
            insights += found
            state = summary[name].get("message") or f"{len(found)} insight(s)"
            self.stdout.write(f"{name}: {state}")
        with transaction.atomic():
            Insight.objects.all().delete()
            Insight.objects.bulk_create(insights)
        buys = [i for i in insights if i.kind == Insight.Kind.PURCHASE]
        if buys:
            notifications.notify("purchase_recommendations", f"{len(buys)} item(s) need purchasing",
                                 "; ".join(i.title for i in buys[:5]), type="warning", link="/purchase?tab=recommendations")
        run.finished_at = timezone.now()
        run.summary = summary
        run.save()
        self.stdout.write(self.style.SUCCESS(f"Stored {len(insights)} insight(s)."))
