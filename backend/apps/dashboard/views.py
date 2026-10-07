from datetime import datetime, time, timedelta

from django.db.models import Count, F, Prefetch, Q, Sum
from django.utils import timezone
from rest_framework.response import Response

from apps.core import periods
from apps.core.metrics import kpi, num
from apps.core.roles import can_read
from apps.core.views import ModuleAPIView
from apps.customers.models import Customer
from apps.finance.models import Transaction
from apps.inventory.models import Product
from apps.marketing.models import Campaign
from apps.purchase.models import Purchase, PurchaseReturn, Supplier, SupplierPayment
from apps.quality.models import QualityAudit
from apps.sales import selectors
from apps.sales.models import SalesOrder, SalesOrderItem


def end_of(day):
    return timezone.make_aware(datetime.combine(day, time.max))


def net_profit_pair(cur, prev):
    """(net profit for cur, for prev) in one query (the database is remote; each query is a round trip)."""
    def period(p, kind):
        return Sum("amount", filter=Q(date__range=(p.start, p.end), type=kind))

    a = Transaction.objects.aggregate(i1=period(cur, Transaction.Type.INCOME), e1=period(cur, Transaction.Type.EXPENSE),
                                      i2=period(prev, Transaction.Type.INCOME), e2=period(prev, Transaction.Type.EXPENSE))
    return (a["i1"] or 0) - (a["e1"] or 0), (a["i2"] or 0) - (a["e2"] or 0)


def upcoming(user, today):
    horizon = today + timedelta(days=7)  # the Dashboard card is titled "Next 7 days"
    items = []
    if can_read(user, "quality"):
        for a in QualityAudit.objects.filter(status=QualityAudit.Status.SCHEDULED, date__range=(today, horizon)):
            items.append({"id": f"audit-{a.id}", "title": a.get_audit_type_display() + (f" ({a.auditor})" if a.auditor else ""),
                          "date": a.date, "category": "Quality"})
    if can_read(user, "purchase"):
        for p in Purchase.objects.select_related("material", "product").filter(status__in=Purchase.OPEN,
                                                                               expected_receipt_date__range=(today, horizon)):
            items.append({"id": f"purchase-{p.id}", "title": f"{p.purchase_number} receipt ({p.item_name})",
                          "date": p.expected_receipt_date, "category": "Purchase"})
        for pm in SupplierPayment.objects.select_related("supplier").filter(status=SupplierPayment.Status.PENDING,
                                                                            payment_date__range=(today, horizon)):
            items.append({"id": f"supplier-payment-{pm.id}", "title": f"Supplier payment: {pm.supplier.name}",
                          "date": pm.payment_date, "category": "Purchase"})
    if can_read(user, "finance"):
        for t in Transaction.objects.filter(status=Transaction.Status.PENDING, type=Transaction.Type.EXPENSE, due_date__range=(today, horizon)):
            items.append({"id": f"payment-{t.id}", "title": f"Payment due: {t.party or t.description}", "date": t.due_date, "category": "Finance"})
    if can_read(user, "marketing"):
        for c in Campaign.objects.filter(ended_on__isnull=True, start_date__range=(today, horizon)):
            items.append({"id": f"campaign-{c.id}", "title": f"Campaign starts: {c.name}", "date": c.start_date, "category": "Marketing"})
    return sorted(items, key=lambda i: i["date"])[:8]


class SummaryView(ModuleAPIView):
    module = "dashboard"

    def get(self, request):
        user = request.user
        cur, prev = periods.resolve(self.param("range"))
        today = periods.today()
        data = {"kpis": {}}
        k = data["kpis"]

        if can_read(user, "sales"):
            now, before = selectors.totals_pair(cur, prev)
            k["total_sales"] = kpi(now["sales"], before["sales"])
            k["total_orders"] = kpi(now["orders"], before["orders"])
            data["product_contribution"] = [{"name": r["product__name"], "value": num(r["sales"])} for r in selectors.by_product(cur.start, cur.end)]
            data["order_status"] = [
                {"status": SalesOrder.Status(r["status"]).label, "count": r["n"]}
                for r in SalesOrder.objects.filter(order_date__range=(cur.start, cur.end)).values("status").annotate(n=Count("id")).order_by("-n")
            ]
            recent = SalesOrder.objects.select_related("customer").prefetch_related(
                Prefetch("items", queryset=SalesOrderItem.objects.select_related("product")))[:5]
            data["recent_orders"] = [
                {"id": o.id, "order_number": o.order_number, "customer": o.customer.name, "product": ", ".join(i.product.name for i in o.items.all()) or None,
                 "amount": num(o.total_amount), "status": o.get_status_display()}
                for o in recent
            ]
        if can_read(user, "sales") or can_read(user, "customers"):
            counts = Customer.objects.aggregate(now=Count("id", filter=Q(created_at__lte=end_of(cur.end))),
                                                before=Count("id", filter=Q(created_at__lte=end_of(prev.end))))
            k["total_customers"] = kpi(counts["now"], counts["before"])
            in_range = Q(orders__order_date__range=(cur.start, cur.end)) & ~Q(orders__status=SalesOrder.Status.CANCELLED)
            top = Customer.objects.annotate(amount=selectors.customer_sales(in_range)).filter(amount__gt=0).order_by("-amount")[:5]
            data["top_customers"] = [{"id": c.id, "name": c.name, "amount": num(c.amount)} for c in top]
        if can_read(user, "purchase"):
            from apps.ai_assistant.insights import latest
            from apps.purchase.views import MONEY, low_stock_materials, payable_expr, supplier_performance

            # Every purchase figure (both periods, counts, outstanding, 6-month trend) in one query
            months = periods.last_n_months(6)
            cur_range = Q(purchase_date__range=(cur.start, cur.end))
            p = (Purchase.objects.exclude(status=Purchase.Status.CANCELLED).annotate(payable_amt=payable_expr()).aggregate(
                value_now=Sum("total_amount", filter=cur_range),
                value_before=Sum("total_amount", filter=Q(purchase_date__range=(prev.start, prev.end))),
                purchases=Count("id", filter=cur_range),
                pending=Count("id", filter=Q(status__in=Purchase.OPEN)),
                received=Count("id", filter=cur_range & Q(status=Purchase.Status.RECEIVED)),
                outstanding=Sum(F("payable_amt") - F("paid_amount"), output_field=MONEY, filter=Q(paid_amount__lt=F("payable_amt"))),
                **{f"m{i}": Sum("total_amount", filter=Q(purchase_date__range=(s, e))) for i, (s, e, _l) in enumerate(months)}))
            k["active_suppliers"] = kpi(Supplier.objects.filter(status=Supplier.Status.ACTIVE).count(), compare=False)
            k["purchase_value"] = kpi(p["value_now"] or 0, p["value_before"] or 0)
            k["outstanding_supplier_payments"] = kpi(p["outstanding"] or 0, compare=False)
            data["purchase_overview"] = {
                "purchases": p["purchases"], "pending": p["pending"], "received": p["received"],
                "returns": PurchaseReturn.objects.exclude(status=PurchaseReturn.Status.CANCELLED)
                .filter(return_date__range=(cur.start, cur.end)).count(),
            }
            trend = [{"label": label, "value": num(p[f"m{i}"] or 0)} for i, (_s, _e, label) in enumerate(months)]
            data["purchase_trend"] = trend if any(t["value"] for t in trend) else []
            data["purchase_recommendations"] = [{"id": i.id, "title": i.title, "text": i.text, "action": i.action or None,
                                                 "priority": i.data.get("priority"), "created_at": i.created_at}
                                                for i in latest("purchase", 5)]
            data["supplier_performance"] = supplier_performance(today - timedelta(days=180))[:5]
            data["low_stock_materials"] = low_stock_materials()[:5]
        if can_read(user, "finance"):
            k["net_profit"] = kpi(*net_profit_pair(cur, prev))
        if can_read(user, "inventory"):
            low = [p for p in Product.objects.filter(is_active=True) if p.stock_status != Product.StockStatus.IN_STOCK]
            data["low_stock"] = [
                {"id": p.id, "product": p.name, "stock_kg": num(p.stock_kg), "reorder_level_kg": num(p.reorder_level_kg),
                 "status": Product.StockStatus(p.stock_status).label}
                for p in sorted(low, key=lambda p: p.stock_kg - p.reorder_level_kg)[:5]
            ]
        data["upcoming"] = upcoming(user, today)
        return Response(data)


class SalesTrendView(ModuleAPIView):
    module = "dashboard"

    def get(self, request):
        period = periods.parse_choice(self.param("period"), ["last_12_months", "last_6_months"], "period", "last_12_months")
        if not can_read(request.user, "sales"):
            return Response([])
        months = periods.last_n_months(12 if period == "last_12_months" else 6)
        series = selectors.monthly_sales(months)
        if not any(v for _l, v in series):
            return Response([])
        return Response([{"label": label, "sales": num(v)} for label, v in series])
