from datetime import datetime, time, timedelta

from django.db.models import Count, Q, Sum
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
from apps.production.models import ProductionBatch
from apps.quality.models import QualityAudit
from apps.sales import selectors
from apps.sales.models import SalesOrder
from apps.supply_chain.models import PurchaseOrder, Supplier


def end_of(day):
    return timezone.make_aware(datetime.combine(day, time.max))


def net_profit(p):
    qs = Transaction.objects.filter(date__range=(p.start, p.end))
    income = qs.filter(type=Transaction.Type.INCOME).aggregate(t=Sum("amount"))["t"] or 0
    expense = qs.filter(type=Transaction.Type.EXPENSE).aggregate(t=Sum("amount"))["t"] or 0
    return income - expense


def upcoming(user, today):
    horizon = today + timedelta(days=7)  # the Dashboard card is titled "Next 7 days"
    items = []
    if can_read(user, "quality"):
        for a in QualityAudit.objects.filter(status=QualityAudit.Status.SCHEDULED, date__range=(today, horizon)):
            items.append({"id": f"audit-{a.id}", "title": a.get_audit_type_display() + (f" ({a.auditor})" if a.auditor else ""),
                          "date": a.date, "category": "Quality"})
    if can_read(user, "production"):
        for b in ProductionBatch.objects.select_related("product").filter(stage__in=ProductionBatch.OPEN_STAGES, due_date__range=(today, horizon)):
            items.append({"id": f"batch-{b.id}", "title": f"Batch {b.batch_number} due ({b.product.name})", "date": b.due_date, "category": "Production"})
    if can_read(user, "finance"):
        for t in Transaction.objects.filter(status=Transaction.Status.PENDING, type=Transaction.Type.EXPENSE, due_date__range=(today, horizon)):
            items.append({"id": f"payment-{t.id}", "title": f"Payment due: {t.party or t.description}", "date": t.due_date, "category": "Finance"})
    if can_read(user, "supply_chain"):
        for po in PurchaseOrder.objects.select_related("material").filter(status__in=PurchaseOrder.OPEN, expected_delivery__range=(today, horizon)):
            items.append({"id": f"po-{po.id}", "title": f"{po.po_number} delivery ({po.material.name})", "date": po.expected_delivery, "category": "Supply Chain"})
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
            now, before = selectors.totals(cur.start, cur.end), selectors.totals(prev.start, prev.end)
            k["total_sales"] = kpi(now["sales"], before["sales"])
            k["total_orders"] = kpi(now["orders"], before["orders"])
            data["product_contribution"] = [{"name": r["product__name"], "value": num(r["sales"])} for r in selectors.by_product(cur.start, cur.end)]
            data["order_status"] = [
                {"status": SalesOrder.Status(r["status"]).label, "count": r["n"]}
                for r in SalesOrder.objects.filter(order_date__range=(cur.start, cur.end)).values("status").annotate(n=Count("id")).order_by("-n")
            ]
            recent = SalesOrder.objects.select_related("customer").prefetch_related("items__product")[:5]
            data["recent_orders"] = [
                {"id": o.id, "customer": o.customer.name, "product": ", ".join(i.product.name for i in o.items.all()) or None,
                 "amount": num(o.total_amount), "status": o.get_status_display()}
                for o in recent
            ]
        if can_read(user, "sales") or can_read(user, "customers"):
            k["total_customers"] = kpi(Customer.objects.filter(created_at__lte=end_of(cur.end)).count(),
                                       Customer.objects.filter(created_at__lte=end_of(prev.end)).count())
            in_range = Q(orders__order_date__range=(cur.start, cur.end)) & ~Q(orders__status=SalesOrder.Status.CANCELLED)
            top = Customer.objects.annotate(amount=Sum("orders__total_amount", filter=in_range)).filter(amount__gt=0).order_by("-amount")[:5]
            data["top_customers"] = [{"id": c.id, "name": c.name, "amount": num(c.amount)} for c in top]
        if can_read(user, "supply_chain"):
            k["active_suppliers"] = kpi(Supplier.objects.filter(is_active=True).count(), compare=False)
        if can_read(user, "finance"):
            k["net_profit"] = kpi(net_profit(cur), net_profit(prev))
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
