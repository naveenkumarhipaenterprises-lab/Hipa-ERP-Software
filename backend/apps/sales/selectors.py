"""
Sales figures used by the Sales page, Dashboard, Reports and analytics. Cancelled orders never count.

The database is remote (Supabase), so every query costs a network round trip: figures for several
periods or months are fetched in one query and split in Python instead of one query each.
"""
from decimal import Decimal

from django.db.models import Count, F, Q, Sum

from .models import SalesOrder, SalesOrderItem

ZERO = Decimal("0")


def customer_sales(in_range):
    """Annotation for Customer querysets: their sales before GST (subtotal − discount), like every other Sales figure."""
    return Sum(F("orders__subtotal") - F("orders__discount_amount"), filter=in_range)


def items(start, end, product=None):
    qs = SalesOrderItem.objects.filter(order__order_date__range=(start, end)).exclude(order__status=SalesOrder.Status.CANCELLED)
    return qs.filter(product_id=product) if product else qs


def orders(start, end, product=None):
    qs = SalesOrder.objects.filter(order_date__range=(start, end)).exclude(status=SalesOrder.Status.CANCELLED)
    return qs.filter(items__product_id=product).distinct() if product else qs


def totals(start, end, product=None):
    agg = items(start, end, product).aggregate(sales=Sum("amount"), kg=Sum("quantity_kg"))
    return {
        "sales": agg["sales"] or ZERO,
        "kg": agg["kg"] or ZERO,
        "orders": orders(start, end, product).count(),
    }


def totals_pair(cur, prev, product=None):
    """(totals for cur, totals for prev) — the same figures as totals(), in two queries instead of four."""
    start, end = min(cur.start, prev.start), max(cur.end, prev.end)
    in_cur, in_prev = Q(order__order_date__range=(cur.start, cur.end)), Q(order__order_date__range=(prev.start, prev.end))
    agg = items(start, end, product).aggregate(
        s1=Sum("amount", filter=in_cur), k1=Sum("quantity_kg", filter=in_cur),
        s2=Sum("amount", filter=in_prev), k2=Sum("quantity_kg", filter=in_prev))
    counts = orders(start, end, product).aggregate(
        o1=Count("id", filter=Q(order_date__range=(cur.start, cur.end)), distinct=True),
        o2=Count("id", filter=Q(order_date__range=(prev.start, prev.end)), distinct=True))
    return ({"sales": agg["s1"] or ZERO, "kg": agg["k1"] or ZERO, "orders": counts["o1"]},
            {"sales": agg["s2"] or ZERO, "kg": agg["k2"] or ZERO, "orders": counts["o2"]})


def by_product(start, end):
    return (items(start, end).values("product_id", "product__name")
            .annotate(sales=Sum("amount"), kg=Sum("quantity_kg"), orders=Count("order", distinct=True))
            .order_by("-sales"))


def _daily(months, product_ids=None):
    """{(product_id, date): sales} for the whole span of `months`, in one query."""
    qs = items(months[0][0], months[-1][1])
    if product_ids is not None:
        qs = qs.filter(product_id__in=product_ids)
    return {(r["product_id"], r["order__order_date"]): r["t"] for r in
            qs.values("product_id", "order__order_date").annotate(t=Sum("amount")).order_by()}


def _bucket(daily, months, product_id=None):
    return [(label, sum((v for (pid, d), v in daily.items() if s <= d <= e and (product_id is None or pid == product_id)), ZERO))
            for s, e, label in months]


def monthly_sales(months, product=None):
    """[(label, sales)] for month buckets from periods.last_n_months() — one query for all months."""
    if not months:
        return []
    return _bucket(_daily(months, None if product is None else [product]), months, product)


def monthly_sales_by_product(months, product_ids):
    """{product_id: [sales per month]} for many products at once (one query, not one per product per month)."""
    product_ids = list(product_ids)
    if not months or not product_ids:
        return {pid: [] for pid in product_ids}
    daily = _daily(months, product_ids)
    return {pid: [v for _l, v in _bucket(daily, months, pid)] for pid in product_ids}
