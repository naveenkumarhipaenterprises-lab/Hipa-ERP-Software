"""Sales figures used by the Sales page, Dashboard, Reports and analytics. Cancelled orders never count."""
from decimal import Decimal

from django.db.models import Count, Sum

from .models import SalesOrder, SalesOrderItem

ZERO = Decimal("0")


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


def by_product(start, end):
    return (items(start, end).values("product_id", "product__name")
            .annotate(sales=Sum("amount"), kg=Sum("quantity_kg"), orders=Count("order", distinct=True))
            .order_by("-sales"))


def monthly_sales(months, product=None):
    """[(label, sales)] for month buckets from periods.last_n_months()."""
    return [(label, items(s, e, product).aggregate(t=Sum("amount"))["t"] or ZERO) for s, e, label in months]
