"""
Customer segmentation with RFM features (recency, frequency, monetary) and KMeans.
Runs only when enough customers have orders; otherwise returns InsufficientData.
"""
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

from apps.core.periods import today

from .data import InsufficientData

MIN_CUSTOMERS = 8
SEGMENT_NAMES = ["High value", "Regular", "Occasional"]


def segment_customers(days=365):
    from datetime import timedelta

    from django.db.models import Count, Max, Sum

    from apps.sales.models import SalesOrder

    start = today() - timedelta(days=days)
    rows = list(
        SalesOrder.objects.filter(order_date__gte=start).exclude(status=SalesOrder.Status.CANCELLED)
        .values("customer_id", "customer__name")
        .annotate(last=Max("order_date"), frequency=Count("id"), monetary=Sum("total_amount"))
    )
    if len(rows) < MIN_CUSTOMERS:
        return InsufficientData(f"Segmentation needs at least {MIN_CUSTOMERS} customers with orders (has {len(rows)}).")

    df = pd.DataFrame(rows)
    df["recency"] = (pd.Timestamp(today()) - pd.to_datetime(df["last"])).dt.days
    df["monetary"] = df["monetary"].astype(float)
    features = StandardScaler().fit_transform(df[["recency", "frequency", "monetary"]])
    k = min(3, len(df) // 3)
    model = KMeans(n_clusters=k, n_init=10, random_state=0).fit(features)
    df["cluster"] = model.labels_

    # Name clusters by average spend, highest first
    order = df.groupby("cluster")["monetary"].mean().sort_values(ascending=False).index
    names = {cluster: SEGMENT_NAMES[i] if i < len(SEGMENT_NAMES) else f"Segment {i + 1}" for i, cluster in enumerate(order)}
    segments = []
    for cluster in order:
        part = df[df["cluster"] == cluster]
        segments.append({
            "name": names[cluster],
            "customers": int(len(part)),
            "avg_spend": round(float(part["monetary"].mean()), 2),
            "avg_orders": round(float(part["frequency"].mean()), 1),
            "avg_days_since_order": int(np.round(part["recency"].mean())),
            "share_of_sales_pct": round(float(part["monetary"].sum() / df["monetary"].sum() * 100), 1),
        })
    return {"segments": segments, "customers": int(len(df))}
