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
from apps.system.models import BillingSettings
from services import audit, notifications

from . import selectors, services
from .models import PaymentMethod, SalesInvoice, SalesOrder, SalesQuotation, SalesReturn

St = SalesOrder.Status


def order_row(o):
    lines = list(o.items.all())
    invoice = next((i for i in o.invoices.all() if i.status != SalesInvoice.Status.CANCELLED), None)
    return {
        "id": o.id,
        "order_number": o.order_number,
        "date": o.order_date,
        "customer_id": o.customer_id,
        "customer": o.customer.name,
        "product": ", ".join(i.product.name for i in lines) or None,
        "quantity_kg": num(sum((i.quantity_kg for i in lines), Decimal("0"))),
        "subtotal": num(o.subtotal),
        "discount_amount": num(o.discount_amount),
        "gst_amount": num(o.gst_amount),
        "amount": num(o.total_amount),
        "status": o.get_status_display(),
        "quotation_number": o.quotation.quotation_number if o.quotation else None,
        "invoice_id": invoice.id if invoice else None,
        "invoice_number": invoice.invoice_number if invoice else None,
        "can_cancel": o.status in SalesOrder.CANCELLABLE and invoice is None,
        "can_invoice": o.status != St.CANCELLED and invoice is None,
    }


def orders_qs():
    return SalesOrder.objects.select_related("customer", "quotation").prefetch_related("items__product", "invoices")


class SalesView(ModuleAPIView):
    module = "sales"


class OverviewView(SalesView):
    def get(self, request):
        cur, prev = periods.resolve(self.param("range"))
        product = self.int_param("product")
        now, before = selectors.totals_pair(cur, prev, product)
        new = Customer.objects.aggregate(now=Count("id", filter=Q(created_at__range=periods.moments(cur.start, cur.end))),
                                         before=Count("id", filter=Q(created_at__range=periods.moments(prev.start, prev.end))))
        new_now, new_before = new["now"], new["before"]

        rows = list(selectors.by_product(cur.start, cur.end))
        if product:
            rows = [r for r in rows if r["product_id"] == product]
        prev_sales = {r["product_id"]: r["sales"] for r in selectors.by_product(prev.start, prev.end)}
        trends = selectors.monthly_sales_by_product(periods.last_n_months(6), [r["product_id"] for r in rows])
        products = [{
            "id": r["product_id"],
            "product": r["product__name"],
            "quantity_kg": num(r["kg"]),
            "sales": num(r["sales"]),
            "orders": r["orders"],
            "avg_price": num((r["sales"] / r["kg"]).quantize(Decimal("0.01"))) if r["kg"] else None,
            "growth": pct_change(r["sales"], prev_sales.get(r["product_id"])),
            "trend": [num(v) for v in trends[r["product_id"]]],
        } for r in rows]

        order_qs = selectors.orders(cur.start, cur.end, product)
        in_range = Q(orders__order_date__range=(cur.start, cur.end)) & ~Q(orders__status=St.CANCELLED)
        if product:  # only that product's lines, so the amounts match the product's sales figures
            amount = Sum("orders__items__amount", filter=in_range & Q(orders__items__product_id=product))
        else:
            amount = selectors.customer_sales(in_range)
        top = Customer.objects.annotate(amount=amount).filter(amount__gt=0).order_by("-amount")[:5]
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
            "quotations": quotation_summary(cur),
            "insights": insights.texts("sales"),
        })


def quotation_summary(period):
    """Quotations dated in the period: count, value and how many sit in each status now."""
    services.expire_quotations()
    qs = SalesQuotation.objects.filter(quotation_date__range=(period.start, period.end))
    # One query: count and value per status
    by_status = {r["status"]: r for r in qs.values("status").annotate(n=Count("id"), v=Sum("grand_total")).order_by()}
    counts = {s: r["n"] for s, r in by_status.items()}
    total = sum(counts.values())
    decided = sum(counts.get(s, 0) for s in ("accepted", "rejected", "converted"))
    return {
        "count": total, "value": num(sum((r["v"] or 0 for r in by_status.values()), Decimal("0"))),
        **{s: counts.get(s, 0) for s in ("draft", "sent", "accepted", "rejected", "expired", "converted")},
        "converted_value": num((by_status.get("converted") or {}).get("v") or 0),
        "conversion_rate_pct": round(counts.get("converted", 0) / decided * 100, 1) if decided else None,
    }


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
        b = BillingSettings.load()
        return Response({
            "customers": list(Customer.objects.filter(status=Customer.Status.ACTIVE).values(
                "id", "name", "contact_person", "phone", "email", "city", "address", "shipping_address", "gstin")),
            "products": [{"id": p.id, "name": p.name, "price_per_kg": num(p.price_per_kg), "stock_kg": num(p.stock_kg)}
                         for p in Product.objects.filter(is_active=True)],
            "statuses": label_choices(St),
            "quotation_statuses": label_choices(SalesQuotation.Status),
            "invoice_statuses": label_choices(SalesInvoice.Status),
            "invoice_payment_statuses": label_choices(SalesInvoice.PaymentStatus),
            "payment_methods": label_choices(PaymentMethod),
            "return_reasons": label_choices(SalesReturn.Reason),
            "return_statuses": label_choices(SalesReturn.Status),
            "defaults": {
                "gst_pct": num(b.default_sales_gst_pct), "quotation_validity_days": b.quotation_validity_days,
                "quotation_payment_terms": b.quotation_payment_terms, "quotation_delivery_terms": b.quotation_delivery_terms,
                "quotation_terms": b.quotation_terms, "invoice_due_days": b.invoice_due_days,
                "invoice_payment_terms": b.invoice_payment_terms, "invoice_terms": b.invoice_terms,
            },
        })


class OrdersView(SalesView):
    def get(self, request):
        qs = orders_qs()
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
        """Body: customer_id, order_date, notes and either items[] (several products, with discount / GST)
        or the single-product fields product_id + quantity_kg (price from the product, no discount or GST)."""
        d = request.data
        errors = {}
        customer = Customer.objects.filter(pk=d.get("customer_id"), status=Customer.Status.ACTIVE).first() if str(d.get("customer_id", "")).isdigit() else None
        if not customer:
            errors["customer_id"] = ["Choose an active customer."]
        if "items" in d:
            lines = services.read_lines(d, errors)
        else:
            lines = []
            product = Product.objects.filter(pk=d.get("product_id"), is_active=True).first() if str(d.get("product_id", "")).isdigit() else None
            if not product:
                errors["product_id"] = ["Choose a product."]
            try:
                qty = Decimal(str(d.get("quantity_kg")))
                if qty <= 0 or qty.as_tuple().exponent < -3:
                    raise InvalidOperation
            except (InvalidOperation, ValueError, TypeError):
                errors["quantity_kg"] = ["Enter a quantity greater than 0 (up to 3 decimals)."]
            if product and "quantity_kg" not in errors:
                lines = [{"product": product, "quantity_kg": qty, "unit_price": product.price_per_kg,
                          "discount_pct": Decimal("0"), "gst_pct": Decimal("0")}]
        order_date = parse_date(str(d.get("order_date") or ""))
        if not order_date:
            errors["order_date"] = ["Enter the order date (YYYY-MM-DD)."]
        elif order_date > periods.today():
            errors["order_date"] = ["The order date can't be in the future."]
        if errors:
            raise ValidationError(errors)

        with transaction.atomic():
            order = services.create_order(customer=customer, order_date=order_date, lines=lines,
                                          notes=str(d.get("notes") or "").strip()[:500], user=request.user)
        audit.record(request, "Created sales order", order.order_number)
        summary = ", ".join(f"{line['quantity_kg'].normalize():f} kg {line['product'].name}" for line in lines)
        notifications.notify("new_orders", f"New order {order.order_number}", f"{customer.name}: {summary}"[:500], type="info",
                             link="/sales")
        return Response(order_row(orders_qs().get(pk=order.pk)), status=status.HTTP_201_CREATED)


def item_row(i):
    return {"id": i.id, "product_id": i.product_id, "product": i.product.name, "quantity_kg": num(i.quantity_kg),
            "unit_price": num(i.unit_price), "discount_pct": num(i.discount_pct), "gst_pct": num(i.gst_pct),
            "subtotal": num(i.subtotal), "discount_amount": num(i.discount_amount), "gst_amount": num(i.gst_amount),
            "amount": num(i.total)}


class OrderDetailView(SalesView):
    def get(self, request, pk):
        o = get_object_or_404(orders_qs(), pk=pk)
        row = order_row(o)
        row["notes"] = o.notes or None
        row["items"] = [item_row(i) for i in o.items.all()]
        return Response(row)


class OrderToInvoiceView(SalesView):
    def post(self, request, pk):
        from .document_views import invoice_detail, read_invoice_dates

        order = get_object_or_404(SalesOrder, pk=pk)
        invoice_date, due_date = read_invoice_dates(request.data)
        invoice = services.order_to_invoice(order, request.user, invoice_date=invoice_date, due_date=due_date)
        audit.record(request, "Created sales invoice", f"{invoice.invoice_number} from {order.order_number}")
        return Response(invoice_detail(invoice.pk, True), status=status.HTTP_201_CREATED)


class CancelOrderView(SalesView):
    def post(self, request, pk):
        with transaction.atomic():
            order = get_object_or_404(SalesOrder.objects.select_for_update(of=("self",)), pk=pk)
            if order.status not in SalesOrder.CANCELLABLE:
                raise ValidationError({"detail": f"A {order.get_status_display().lower()} order can't be cancelled."})
            invoice = services.active_invoice(sales_order=order)
            if invoice:
                raise ValidationError({"detail": f"This order is invoiced as {invoice.invoice_number}. Cancel the invoice first."})
            order.status = St.CANCELLED
            order.save(update_fields=["status", "updated_at"])
            for item in order.items.select_related("product"):
                move_stock(item.product, "in", item.quantity_kg, source=StockMovement.Source.SALE_CANCEL,
                           reference=order.order_number, user=request.user)
        audit.record(request, "Cancelled sales order", order.order_number)
        notifications.notify("new_orders", f"Order {order.order_number} cancelled", order.customer.name, type="warning", link="/sales")
        return Response(order_row(orders_qs().get(pk=pk)))
