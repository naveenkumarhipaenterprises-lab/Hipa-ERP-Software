"""
Production plan: per product, forecast demand over the horizon, add safety stock, subtract
stock on hand and batches already in production, then share the available line capacity
between products by urgency (days of stock cover).
"""
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from apps.core.periods import today

from .data import InsufficientData
from .forecasting import LEAD_TIME_DAYS, forecast_product


def build_plan(horizon_days):
    from datetime import timedelta

    from apps.inventory.models import Product
    from apps.production.models import ProductionBatch, ProductionLine

    horizon_end = today() + timedelta(days=horizon_days)
    daily_capacity = ProductionLine.objects.filter(is_active=True).aggregate(c=Sum("capacity_kg_per_day"))["c"]
    open_batches = ProductionBatch.objects.filter(stage__in=[s for s in ProductionBatch.OPEN_STAGES if s != "hold"],
                                                  due_date__lte=horizon_end)
    committed = dict(open_batches.values_list("product_id").annotate(q=Sum("quantity_kg")))
    remaining = None
    if daily_capacity is not None:
        remaining = max(float(daily_capacity) * horizon_days - float(sum(committed.values(), Decimal("0"))), 0.0)

    candidates, skipped = [], []
    for product in Product.objects.filter(is_active=True):
        f = forecast_product(product.id, horizon_days)
        if isinstance(f, InsufficientData):
            skipped.append(product.name)
            continue
        stock = float(product.stock_kg)
        in_progress = float(committed.get(product.id, 0))
        required = max(f["forecast_kg"] + f["safety_stock_kg"] - stock - in_progress, 0.0)
        cover = (stock + in_progress) / f["daily_avg_kg"] if f["daily_avg_kg"] > 0 else None
        if required > 0 and cover is not None and cover < LEAD_TIME_DAYS:
            priority = "HIGH"
        elif required > 0:
            priority = "MEDIUM"
        else:
            priority = "LOW"
        candidates.append({"product": product, "f": f, "stock": stock, "required": required, "cover": cover, "priority": priority})

    rank = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    candidates.sort(key=lambda c: (rank[c["priority"]], c["cover"] if c["cover"] is not None else float("inf")))
    rows = []
    for c in candidates:
        capacity = remaining
        recommended = c["required"] if remaining is None else min(c["required"], remaining)
        if remaining is not None:
            remaining -= recommended
        rows.append({
            "product_id": c["product"].id,
            "product": c["product"].name,
            "stock_kg": round(c["stock"], 1),
            "forecast_kg": c["f"]["forecast_kg"],
            "safety_stock_kg": c["f"]["safety_stock_kg"],
            "required_kg": round(c["required"], 1),
            "capacity_kg": round(capacity, 1) if capacity is not None else None,
            "recommended_kg": round(recommended, 1),
            "priority": c["priority"],
            "days_of_cover": round(c["cover"], 1) if c["cover"] is not None else None,
        })

    summary = {"total_products": len(rows), **{p.lower(): sum(r["priority"] == p for r in rows) for p in ("HIGH", "MEDIUM", "LOW")}}
    notes = []
    if skipped:
        notes.append(f"Not enough sales history to plan: {', '.join(skipped)}.")
    if daily_capacity is None:
        notes.append("No active production lines are set up, so line capacity is not applied.")
    short = [r for r in rows if r["recommended_kg"] < r["required_kg"]]
    actions = [f"Capacity covers only {r['recommended_kg']:g} of {r['required_kg']:g} kg needed for {r['product']}." for r in short]
    actions += [f"Schedule {r['recommended_kg']:g} kg of {r['product']} first ({r['days_of_cover']:g} days of stock left)."
                for r in rows if r["priority"] == "HIGH" and r["days_of_cover"] is not None and r["recommended_kg"] > 0]

    if not rows:
        return {
            "generated_at": None,
            "status": "insufficient_data",
            "message": notes[0] if notes else "Add products and record sales to get a production plan.",
            "summary": summary,
            "rows": [],
            "insights": {"text": " ".join(notes)} if notes else {},
        }
    return {
        "generated_at": timezone.now(),
        "status": "ok",
        "horizon_days": horizon_days,
        "summary": summary,
        "rows": rows,
        "insights": {**({"text": " ".join(notes)} if notes else {}), **({"actions": actions} if actions else {})},
    }
