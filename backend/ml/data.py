"""Loads real sales / quality records into pandas frames."""
from dataclasses import dataclass
from datetime import timedelta

import pandas as pd

from apps.core.periods import today


@dataclass(frozen=True)
class InsufficientData:
    reason: str

    def as_dict(self):
        return {"status": "insufficient_data", "message": self.reason}


def daily_sales(days=365, product_id=None):
    """
    DataFrame indexed by date with columns product_id, kg, amount — one row per product per day
    that had sales. Cancelled orders are excluded.
    """
    from apps.sales.models import SalesOrder, SalesOrderItem
    from django.db.models import Sum

    start = today() - timedelta(days=days)
    qs = SalesOrderItem.objects.filter(order__order_date__gte=start).exclude(order__status=SalesOrder.Status.CANCELLED)
    if product_id:
        qs = qs.filter(product_id=product_id)
    rows = list(qs.values("order__order_date", "product_id").annotate(kg=Sum("quantity_kg"), amount=Sum("amount")))
    if not rows:
        return pd.DataFrame(columns=["date", "product_id", "kg", "amount"])
    df = pd.DataFrame(rows).rename(columns={"order__order_date": "date"})
    df["kg"] = df["kg"].astype(float)
    df["amount"] = df["amount"].astype(float)
    df["date"] = pd.to_datetime(df["date"])
    return df


def continuous_daily(df, value="kg", end=None):
    """Sums per day and fills days without sales with 0, from the first sale to `end` (today)."""
    if df.empty:
        return pd.Series(dtype=float)
    series = df.groupby("date")[value].sum()
    idx = pd.date_range(series.index.min(), pd.Timestamp(end or today()), freq="D")
    return series.reindex(idx, fill_value=0.0)
