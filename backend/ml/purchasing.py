"""
Purchase recommendations from real records only.

Raw materials
  demand      average daily usage over the last 120 days (usage recorded under Purchase → material movements);
              needs MIN_USAGE_DAYS days of history with usage on MIN_USED_DAYS of them
  lead time   average days from purchase date to the first goods receipt, over past purchases of the
              material (any supplier); when there is none yet, the material's own reorder level is used
              as the reorder point and the row says so
  safety      Z × std(daily usage) × √lead time
  order       usage over the horizon + safety stock − stock on hand − quantity still to be received
Finished products (bought for resale)
  demand      the sales forecast in ml.forecasting (needs 4+ weeks of sales on 6+ days)
  order       forecast + safety stock − stock − quantity still to be received
Prices: last and average unit price, change since the previous purchase, and the supplier with the
lowest average price over the last 180 days. Anything without enough data is listed separately with
the reason; nothing is estimated.
"""
import math
from datetime import timedelta

import numpy as np
from django.utils import timezone

from apps.core.periods import today

from .data import InsufficientData, continuous_daily, daily_material_usage
from .forecasting import SERVICE_LEVEL_Z, forecast_product

MIN_USAGE_DAYS = 14
MIN_USED_DAYS = 3
PRICE_DAYS = 180
INSUFFICIENT = "Insufficient data for AI recommendation."
PRIORITY_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}


def _lead_times():
    """{('material'|'product', id): average days from purchase to first goods receipt}."""
    from django.db.models import Min

    from apps.purchase.models import Purchase

    out = {}
    rows = (Purchase.objects.exclude(status=Purchase.Status.CANCELLED).annotate(first=Min("goods_receipts__received_date"))
            .exclude(first=None).values("material_id", "product_id", "purchase_date", "first"))
    for r in rows:
        key = ("material", r["material_id"]) if r["material_id"] else ("product", r["product_id"])
        out.setdefault(key, []).append((r["first"] - r["purchase_date"]).days)
    return {k: sum(v) / len(v) for k, v in out.items()}


def _on_order():
    from apps.purchase.models import Purchase

    out = {}
    for p in Purchase.objects.filter(status__in=Purchase.OPEN).values("material_id", "product_id", "quantity", "received_quantity"):
        key = ("material", p["material_id"]) if p["material_id"] else ("product", p["product_id"])
        out[key] = out.get(key, 0.0) + max(float(p["quantity"] - p["received_quantity"]), 0.0)
    return out


def _prices(item_type, item_id):
    from django.db.models import Avg

    from apps.purchase.models import Purchase

    qs = Purchase.objects.exclude(status=Purchase.Status.CANCELLED).filter(**{f"{item_type}_id": item_id}).select_related("supplier")
    recent = list(qs.order_by("-purchase_date", "-id")[:2])
    if not recent:
        return {"last_price": None, "avg_price": None, "price_change_pct": None, "best_supplier": None}
    since = timezone.localdate() - timedelta(days=PRICE_DAYS)
    window = qs.filter(purchase_date__gte=since)
    avg = window.aggregate(a=Avg("unit_price"))["a"]
    best = window.values("supplier__name").annotate(a=Avg("unit_price")).order_by("a").first()
    change = None
    if len(recent) == 2 and recent[1].unit_price:
        change = round(float((recent[0].unit_price - recent[1].unit_price) / recent[1].unit_price * 100), 1)
    return {"last_price": float(recent[0].unit_price), "avg_price": round(float(avg), 2) if avg is not None else None,
            "price_change_pct": change, "best_supplier": best["supplier__name"] if best else None}


def _priority(available, reorder_point, recommended, days_cover, lead):
    if recommended > 0 and (available <= reorder_point or (days_cover is not None and lead is not None and days_cover <= lead)):
        return "HIGH"
    return "MEDIUM" if recommended > 0 else "LOW"


def _round_up(value):
    return math.ceil(value * 10) / 10 if value > 0 else 0.0


def material_rows(horizon, lead_times, on_order):
    from apps.purchase.models import RawMaterial

    rows, skipped = [], []
    for m in RawMaterial.objects.filter(status=RawMaterial.Status.ACTIVE).select_related("supplier"):
        history = daily_material_usage(m.id)
        # Today is not over yet: count up to yesterday (or the last recorded usage, if that is today)
        end = max(history["date"].max().date(), today() - timedelta(days=1)) if not history.empty else None
        usage = continuous_daily(history, value="quantity", end=end)
        used_days = int((usage > 0).sum()) if len(usage) else 0
        if len(usage) < MIN_USAGE_DAYS or used_days < MIN_USED_DAYS:
            skipped.append({"item": m.name, "item_type": "material",
                            "reason": f"Needs {MIN_USAGE_DAYS}+ days of recorded usage on {MIN_USED_DAYS}+ days "
                                      f"(has {len(usage)} days, used on {used_days})."})
            continue
        values = usage.values
        avg = float(values.mean())
        std = float(np.std(values, ddof=1)) if len(values) > 1 else 0.0
        lead = lead_times.get(("material", m.id))
        stock = float(m.current_stock)
        pending = on_order.get(("material", m.id), 0.0)
        notes = []
        if lead is not None:
            safety = SERVICE_LEVEL_Z * std * math.sqrt(max(lead, 0))
            reorder_point = avg * lead + safety
        else:
            safety = 0.0
            reorder_point = float(m.reorder_level)
            notes.append("No goods receipt yet to measure supplier lead time; using the material's reorder level.")
        recommended = _round_up(avg * horizon + safety - stock - pending)
        days_cover = round(stock / avg, 1) if avg > 0 else None
        prices = _prices("material", m.id)
        rows.append({
            "item_type": "material", "item_id": m.id, "item": m.name, "unit": m.unit, "current_stock": round(stock, 3),
            "on_order": round(pending, 3), "avg_daily_demand": round(avg, 3), "demand_basis": "usage",
            "lead_time_days": round(lead, 1) if lead is not None else None, "safety_stock": round(safety, 1),
            "reorder_point": round(reorder_point, 1), "days_of_cover": days_cover, "recommended_quantity": recommended,
            "estimated_cost": round(recommended * prices["last_price"], 2) if prices["last_price"] is not None and recommended else None,
            "priority": _priority(stock + pending, reorder_point, recommended, days_cover, lead),
            "preferred_supplier": m.supplier.name if m.supplier else None, **prices, "notes": notes,
        })
    return rows, skipped


def product_rows(horizon, lead_times, on_order):
    from apps.inventory.models import Product

    rows, skipped = [], []
    for p in Product.objects.filter(is_active=True):
        f = forecast_product(p.id, horizon)
        if isinstance(f, InsufficientData):
            skipped.append({"item": p.name, "item_type": "product", "reason": f.reason})
            continue
        stock = float(p.stock_kg)
        pending = on_order.get(("product", p.id), 0.0)
        avg = f["forecast_kg"] / horizon if horizon else 0.0
        lead = lead_times.get(("product", p.id))
        reorder_point = avg * lead + f["safety_stock_kg"] if lead is not None else float(p.reorder_level_kg)
        recommended = _round_up(f["forecast_kg"] + f["safety_stock_kg"] - stock - pending)
        days_cover = round(stock / avg, 1) if avg > 0 else None
        prices = _prices("product", p.id)
        notes = [] if lead is not None else ["No goods receipt yet to measure supplier lead time; using the product's reorder level."]
        rows.append({
            "item_type": "product", "item_id": p.id, "item": p.name, "unit": "kg", "current_stock": round(stock, 3),
            "on_order": round(pending, 3), "avg_daily_demand": round(avg, 3), "demand_basis": "sales forecast",
            "lead_time_days": round(lead, 1) if lead is not None else None, "safety_stock": f["safety_stock_kg"],
            "reorder_point": round(reorder_point, 1), "days_of_cover": days_cover, "recommended_quantity": recommended,
            "estimated_cost": round(recommended * prices["last_price"], 2) if prices["last_price"] is not None and recommended else None,
            "priority": _priority(stock + pending, reorder_point, recommended, days_cover, lead),
            "preferred_supplier": None, **prices, "notes": notes,
        })
    return rows, skipped


def recommend(horizon_days=30):
    lead_times, on_order = _lead_times(), _on_order()
    m_rows, m_skipped = material_rows(horizon_days, lead_times, on_order)
    p_rows, p_skipped = product_rows(horizon_days, lead_times, on_order)
    rows = sorted(m_rows + p_rows, key=lambda r: (PRIORITY_ORDER[r["priority"]], r["days_of_cover"] if r["days_of_cover"] is not None else 1e9))
    skipped = m_skipped + p_skipped
    if not rows:
        return {"generated_at": None, "status": "insufficient_data", "message": INSUFFICIENT, "horizon_days": horizon_days,
                "summary": {"items": 0, "high": 0, "medium": 0, "low": 0, "estimated_cost": None}, "rows": [], "insufficient": skipped}
    costs = [r["estimated_cost"] for r in rows if r["estimated_cost"] is not None]
    return {
        "generated_at": timezone.now(), "status": "ok", "message": None, "horizon_days": horizon_days,
        "summary": {"items": len(rows), "high": sum(r["priority"] == "HIGH" for r in rows),
                    "medium": sum(r["priority"] == "MEDIUM" for r in rows), "low": sum(r["priority"] == "LOW" for r in rows),
                    "estimated_cost": round(sum(costs), 2) if costs else None},
        "rows": rows, "insufficient": skipped,
    }
