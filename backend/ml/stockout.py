"""Products likely to run out soon: stock on hand divided by forecast daily demand."""
from .data import InsufficientData
from .forecasting import forecast_product

WARN_DAYS = 14


def stockout_risks(horizon_days=30):
    from apps.inventory.models import Product

    risks, forecasted = [], 0
    for product in Product.objects.filter(is_active=True):
        f = forecast_product(product.id, horizon_days)
        if isinstance(f, InsufficientData):
            continue
        forecasted += 1
        daily = f["forecast_kg"] / horizon_days
        if daily <= 0:
            continue
        days_left = float(product.stock_kg) / daily
        if days_left < WARN_DAYS:
            risks.append({"product_id": product.id, "product": product.name, "stock_kg": float(product.stock_kg),
                          "daily_demand_kg": round(daily, 2), "days_left": round(days_left, 1)})
    if forecasted == 0:
        return InsufficientData("No product has enough sales history for stock-out forecasting yet.")
    return {"risks": sorted(risks, key=lambda r: r["days_left"])}
