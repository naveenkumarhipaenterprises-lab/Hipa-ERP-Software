from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_date
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.ai_assistant import insights
from apps.core import periods
from apps.core.metrics import kpi, label_choices, num, pct_change, resolve_choice
from apps.core.views import ModuleAPIView
from apps.customers.models import Customer
from apps.inventory.models import Product, StockMovement
from apps.inventory.services import move_stock
from services import audit, notifications

from . import selectors
from .models import SalesOrder, SalesOrderItem

St = SalesOrder.Status


def order_row(o):
    lines = list(o.items.all())
    return {
        "id": o.id,
        "order_number": o.order_number,
        "date": o.order_date,
        "customer": o.customer.name,
        "product": ", ".join(i.product.name for i in lines) or None,
        "quantity_kg": num(sum((i.quantity_kg for i in lines), Decimal("0"))),
        "amount": num(o.total_amount),
        "status": o.get_status_display(),
        "can_cancel": o.status in SalesOrder.CANCELLABLE,
    }


class SalesView(ModuleAPIView):
    module = "sales"


class OverviewView(SalesView):
    def get(self, request):
        cur, prev = periods.resolve(self.param("range"))
        product = self.int_param("product")
        now, before = selectors.totals(cur.start, cur.end, product), selectors.totals(prev.start, prev.end, product)
        new_now = Customer.objects.filter(created_at__range=periods.moments(cur.start, cur.end)).count()
        new_before = Customer.objects.filter(created_at__range=periods.moments(prev.start, prev.end)).count()

        rows = list(selectors.by_product(cur.start, cur.end))
        if product:
            rows = [r for r in rows if r["product_id"] == product]
        prev_sales = {r["product_id"]: r["sales"] for r in selectors.by_product(prev.start, prev.end)}
        months = periods.last_n_months(6)
        products = [{
            "id": r["product_id"],
            "product": r["product__name"],
            "quantity_kg": num(r["kg"]),
            "sales": num(r["sales"]),
            "orders": r["orders"],
            "avg_price": num((r["sales"] / r["kg"]).quantize(Decimal("0.01"))) if r["kg"] else None,
            "growth": pct_change(r["sales"], prev_sales.get(r["product_id"])),
            "trend": [num(v) for _l, v in selectors.monthly_sales(months, r["product_id"])],
        } for r in rows]

        order_qs = selectors.orders(cur.start, cur.end, product)
        in_range = Q(orders__order_date__range=(cur.start, cur.end)) & ~Q(orders__status=St.CANCELLED)
        if product:
            in_range &= Q(orders__items__product_id=product)
        top = (Customer.objects.annotate(amount=Sum("orders__total_amount", filter=in_range))
               .filter(amount__gt=0).order_by("-amount")[:5])
        return Response({
            "kpis": {
                "total_sales": kpi(now["sales"], before["sales"]),
                "total_orders": kpi(now["orders"], before["orders"]),
                "quantity_sold_kg": kpi(now["kg"], before["kg"]),
                "new_customers": kpi(new_now, new_before),
            },
            "product_share": [{"name": p["product"], "value": p["sales"]} for p in products],
            "customer_types": [
                {"name": Customer.Type(r["customer__type"]).label, "value": r["n"]}
                for r in order_qs.values("customer__type").annotate(n=Count("id", distinct=True)).order_by("-n")
            ],
            "products": products,
            "top_customers": [{"id": c.id, "name": c.name, "type": c.get_type_display(), "amount": num(c.amount)} for c in top],
            "insights": insights.texts("sales"),
        })


class TrendView(SalesView):
    def get(self, request):
        cur, _prev = periods.resolve(self.param("range"))
        product = self.int_param("product")
        granularity = periods.parse_choice(self.param("granularity"), ["daily", "weekly"], "granularity", "daily")
        daily = dict(selectors.items(cur.start, cur.end, product).values_list("order__order_date").annotate(t=Sum("amount")))
        if not daily:
            return Response([])
        points, day = [], cur.start
        step = 1 if granularity == "daily" else 7
        while day <= cur.end:
            last = min(day + timedelta(days=step - 1), cur.end)
            total = sum((v for d, v in daily.items() if day <= d <= last), Decimal("0"))
            label = day.strftime("%d %b") if step == 1 else f"{day:%d %b}–{last:%d %b}"
            points.append({"label": label, "sales": num(total)})
            day = last + timedelta(days=1)
        return Response(points)


class OptionsView(SalesView):
    def get(self, request):
        return Response({
            "customers": list(Customer.objects.filter(status=Customer.Status.ACTIVE).values("id", "name")),
            "products": list(Product.objects.filter(is_active=True).values("id", "name")),
            "statuses": label_choices(St),
        })


class OrdersView(SalesView):
    def get(self, request):
        qs = SalesOrder.objects.select_related("customer").prefetch_related("items__product")
        q = self.param("search")
        if q:
            qs = qs.filter(Q(order_number__icontains=q) | Q(customer__name__icontains=q) | Q(items__product__name__icontains=q)).distinct()
        st = resolve_choice(St, self.param("status"), "status")
        if st:
            qs = qs.filter(status=st)
        if self.param("range"):
            cur, _ = periods.resolve(self.param("range"))
            qs = qs.filter(order_date__range=(cur.start, cur.end))
        product = self.int_param("product")
        if product:
            qs = qs.filter(items__product_id=product).distinct()
        customer = self.int_param("customer")
        if customer:
            qs = qs.filter(customer_id=customer)
        return self.paginated(qs.order_by("-order_date", "-id"), order_row)

    def post(self, request):
        d = request.data
        errors = {}
        customer = Customer.objects.filter(pk=d.get("customer_id"), status=Customer.Status.ACTIVE).first() if str(d.get("customer_id", "")).isdigit() else None
        if not customer:
            errors["customer_id"] = ["Choose an active customer."]
        product = Product.objects.filter(pk=d.get("product_id"), is_active=True).first() if str(d.get("product_id", "")).isdigit() else None
        if not product:
            errors["product_id"] = ["Choose a product."]
        try:
            qty = Decimal(str(d.get("quantity_kg")))
            if qty <= 0 or qty.as_tuple().exponent < -3:
                raise InvalidOperation
        except (InvalidOperation, ValueError, TypeError):
            errors["quantity_kg"] = ["Enter a quantity greater than 0 (up to 3 decimals)."]
        order_date = parse_date(str(d.get("order_date") or ""))
        if not order_date:
            errors["order_date"] = ["Enter the order date (YYYY-MM-DD)."]
        elif order_date > periods.today():
            errors["order_date"] = ["The order date can't be in the future."]
        if errors:
            raise ValidationError(errors)

        with transaction.atomic():
            order = SalesOrder.objects.create(customer=customer, order_date=order_date,
                                              notes=str(d.get("notes") or "").strip()[:500], created_by=request.user)
            SalesOrderItem.objects.create(order=order, product=product, quantity_kg=qty, unit_price=product.price_per_kg)
            order.recalculate_total()
            move_stock(product, "out", qty, source=StockMovement.Source.SALE, reference=order.order_number, user=request.user)
        audit.record(request, "Created sales order", order.order_number)
        notifications.notify("new_orders", f"New order {order.order_number}",
                             f"{customer.name}: {qty.normalize():f} kg {product.name}", type="info", link="/sales")
        order = SalesOrder.objects.select_related("customer").prefetch_related("items__product").get(pk=order.pk)
        return Response(order_row(order), status=status.HTTP_201_CREATED)


class CancelOrderView(SalesView):
    def post(self, request, pk):
        with transaction.atomic():
            order = get_object_or_404(SalesOrder.objects.select_for_update(), pk=pk)
            if order.status not in SalesOrder.CANCELLABLE:
                raise ValidationError({"detail": f"A {order.get_status_display().lower()} order can't be cancelled."})
            order.status = St.CANCELLED
            order.save(update_fields=["status", "updated_at"])
            for item in order.items.select_related("product"):
                move_stock(item.product, "in", item.quantity_kg, source=StockMovement.Source.SALE_CANCEL,
                           reference=order.order_number, user=request.user)
        audit.record(request, "Cancelled sales order", order.order_number)
        notifications.notify("new_orders", f"Order {order.order_number} cancelled", order.customer.name, type="warning", link="/sales")
        order = SalesOrder.objects.select_related("customer").prefetch_related("items__product").get(pk=pk)
        return Response(order_row(order))
