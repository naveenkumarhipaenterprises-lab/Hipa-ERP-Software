from datetime import timedelta
from decimal import Decimal

from django.db.models import Avg, Count, F, Q, Sum
from rest_framework.response import Response

from apps.ai_assistant import insights
from apps.core import periods
from apps.core.metrics import kpi, label_choices, num, ratio_pct, resolve_choice
from apps.core.views import ModuleAPIView
from apps.customers.models import Customer
from apps.purchase.models import Purchase, RawMaterial, Supplier
from apps.sales.models import SalesOrder

from .models import Shipment
from .services import monthly_usage_by_material

Sh = Shipment.Status


def shipment_row(s):
    return {"id": s.id, "shipment_number": s.shipment_number, "supplier": s.supplier.name,
            "purchase_number": s.purchase.purchase_number if s.purchase else None, "item": s.item.name,
            "quantity": num(s.quantity), "unit": s.unit, "destination": s.destination, "eta": s.eta,
            "delivered_on": s.delivered_on, "status": s.get_status_display()}


def supplier_scores(supplier_ids=None, since=None):
    """quality_pct, on_time_pct and cost_efficiency_pct per supplier from delivered shipments and purchases."""
    delivered = Shipment.objects.filter(status=Sh.DELIVERED)
    purchases = Purchase.objects.exclude(status=Purchase.Status.CANCELLED).filter(material__isnull=False)
    if since:
        delivered = delivered.filter(delivered_on__gte=since)
        purchases = purchases.filter(purchase_date__gte=since)
    if supplier_ids is not None:
        delivered = delivered.filter(supplier_id__in=supplier_ids)
    scores = {}
    for row in delivered.values("supplier_id").annotate(
        n=Count("id"),
        on_time=Count("id", filter=Q(delivered_on__lte=F("eta"))),
        checked=Count("id", filter=Q(quality_passed__isnull=False)),
        passed=Count("id", filter=Q(quality_passed=True)),
    ):
        scores[row["supplier_id"]] = {"on_time_pct": ratio_pct(row["on_time"], row["n"]),
                                      "quality_pct": ratio_pct(row["passed"], row["checked"])}
    # Cost efficiency: the average unit price paid for each material across all suppliers divided by
    # this supplier's price, weighted by quantity; capped at 100%.
    market = {r["material_id"]: r["avg"] for r in purchases.values("material_id").annotate(avg=Avg("unit_price"))}
    per_supplier = {}
    for p in purchases.values("supplier_id", "material_id", "unit_price", "quantity"):
        if not p["unit_price"]:
            continue
        eff = min(float(market[p["material_id"]]) / float(p["unit_price"]), 1.0)
        total = per_supplier.setdefault(p["supplier_id"], [0.0, 0.0])
        total[0] += eff * float(p["quantity"])
        total[1] += float(p["quantity"])
    for sid, (weighted, qty) in per_supplier.items():
        if supplier_ids is not None and sid not in supplier_ids:
            continue
        scores.setdefault(sid, {"on_time_pct": None, "quality_pct": None})["cost_efficiency_pct"] = round(weighted / qty * 100, 1) if qty else None
    return scores


def material_status(stock, reorder, days_left):
    if stock <= 0:
        return "Out of Stock"
    if stock <= reorder or (days_left is not None and days_left < 7):
        return "Reorder"
    if days_left is not None and days_left < 15:
        return "Low Stock"
    return "In Stock"


class SupplyView(ModuleAPIView):
    module = "supply_chain"


class OverviewView(SupplyView):
    def get(self, request):
        cur, prev = periods.resolve(self.param("range"))
        t = periods.today()
        live = Purchase.objects.exclude(status=Purchase.Status.CANCELLED)
        # The database is remote: each figure group below is one query instead of one per period / material
        cost = live.aggregate(now=Sum("total_amount", filter=Q(purchase_date__range=(cur.start, cur.end))),
                              before=Sum("total_amount", filter=Q(purchase_date__range=(prev.start, prev.end))),
                              pending=Count("id", filter=Q(status__in=Purchase.OPEN)))

        def delivered(p, *extra):
            return Count("id", filter=Q(status=Sh.DELIVERED, delivered_on__range=(p.start, p.end), *extra))

        ships = Shipment.objects.aggregate(
            d1=delivered(cur), ok1=delivered(cur, Q(delivered_on__lte=F("eta"))),
            d2=delivered(prev), ok2=delivered(prev, Q(delivered_on__lte=F("eta"))),
            in_transit=Count("id", filter=Q(status=Sh.IN_TRANSIT)), delayed=Count("id", filter=Q(status=Sh.DELAYED)),
            active=Count("id", filter=~Q(status=Sh.DELIVERED)))
        usage_by_material = monthly_usage_by_material()

        raw = []
        for m in RawMaterial.objects.filter(status=RawMaterial.Status.ACTIVE):
            usage = usage_by_material.get(m.id, Decimal("0"))
            days_left = round(float(m.current_stock) / (float(usage) / 30), 1) if usage > 0 else None
            raw.append({"id": m.id, "material": m.name, "current_stock": num(m.current_stock), "unit": m.unit,
                        "monthly_usage": num(usage), "days_left": days_left,
                        "status": material_status(m.current_stock, m.reorder_level, days_left)})

        alerts = []
        for s in Shipment.objects.select_related("supplier").filter(Q(status=Sh.DELAYED) | Q(status=Sh.IN_TRANSIT, eta__lt=t))[:5]:
            alerts.append({"id": f"shipment-{s.id}", "type": "error", "title": f"Shipment {s.shipment_number} is delayed",
                           "detail": f"{s.supplier.name}, expected {s.eta:%d %b %Y}"})
        for r in raw:
            if r["status"] in ("Reorder", "Out of Stock"):
                alerts.append({"id": f"material-{r['id']}", "type": "warning", "title": f"{r['material']}: {r['status'].lower()}",
                               "detail": f"{r['current_stock']} {r['unit']} left" +
                                         (f", about {r['days_left']:g} days of use" if r["days_left"] is not None else "")})
        late = (live.select_related("supplier", "material", "product")
                .filter(status__in=Purchase.OPEN, expected_receipt_date__lt=t)[:5])
        for p in late:
            alerts.append({"id": f"purchase-{p.id}", "type": "warning", "title": f"{p.purchase_number} is overdue",
                           "detail": f"{p.item_name} from {p.supplier.name}, expected {p.expected_receipt_date:%d %b %Y}"})

        suppliers = Supplier.objects.filter(status=Supplier.Status.ACTIVE).count()
        customers = Customer.objects.aggregate(any=Count("id"), active=Count("id", filter=Q(status=Customer.Status.ACTIVE)))
        has_flow = any([suppliers, cost["pending"], RawMaterial.objects.exists(), customers["any"]])
        flow = [
            {"stage": "farmers", "label": "Suppliers", "count": suppliers, "detail": "Active suppliers"},
            {"stage": "procurement", "label": "Procurement", "count": cost["pending"], "detail": "Purchases awaiting receipt"},
            {"stage": "warehouse", "label": "Warehouse", "count": sum(1 for r in raw if (r["current_stock"] or 0) > 0),
             "detail": "Materials in stock"},
            {"stage": "distribution", "label": "Distribution", "count": SalesOrder.objects.filter(status=SalesOrder.Status.IN_TRANSIT).count(),
             "detail": "Orders in transit"},
            {"stage": "customers", "label": "Customers", "count": customers["active"], "detail": "Active customers"},
        ] if has_flow else []

        return Response({
            "kpis": {
                "total_suppliers": kpi(suppliers, compare=False),
                "active_shipments": kpi(ships["active"], compare=False),
                "on_time_delivery_pct": kpi(ratio_pct(ships["ok1"], ships["d1"]), ratio_pct(ships["ok2"], ships["d2"])),
                "procurement_cost": kpi(cost["now"] or 0, cost["before"] or 0),
                "pending_purchases": kpi(cost["pending"], compare=False),
            },
            "flow": flow,
            "shipment_summary": {"in_transit": ships["in_transit"], "delivered": ships["d1"], "delayed": ships["delayed"]},
            "raw_materials": raw,
            "recent_shipments": [shipment_row(s) for s in Shipment.objects.select_related(
                "supplier", "purchase", "material", "product")[:6]],
            "alerts": alerts,
            "insights": insights.block("supply_chain"),
        })


class SupplierPerformanceView(SupplyView):
    def get(self, request):
        months = int(periods.parse_choice(self.param("months"), ["6", "3"], "months", "6"))
        since = periods.today() - timedelta(days=30 * months)
        scores = supplier_scores(since=since)
        names = dict(Supplier.objects.filter(pk__in=scores).values_list("id", "name"))
        return Response([
            {"supplier": names[sid], "quality_pct": s.get("quality_pct"), "on_time_pct": s.get("on_time_pct"),
             "cost_efficiency_pct": s.get("cost_efficiency_pct")}
            for sid, s in sorted(scores.items(), key=lambda kv: names.get(kv[0], "")) if sid in names
        ])


class OptionsView(SupplyView):
    def get(self, request):
        return Response({
            "suppliers": list(Supplier.objects.filter(status=Supplier.Status.ACTIVE).values("id", "name")),
            "materials": list(RawMaterial.objects.filter(status=RawMaterial.Status.ACTIVE).values("id", "name")),
            "shipment_statuses": label_choices(Sh),
        })


class ShipmentsView(SupplyView):
    def get(self, request):
        qs = Shipment.objects.select_related("supplier", "purchase", "material", "product")
        q = self.param("search")
        if q:
            qs = qs.filter(Q(shipment_number__icontains=q) | Q(supplier__name__icontains=q) | Q(destination__icontains=q) |
                           Q(material__name__icontains=q) | Q(product__name__icontains=q) | Q(purchase__purchase_number__icontains=q))
        st = resolve_choice(Sh, self.param("status"), "status")
        if st:
            qs = qs.filter(status=st)
        return self.paginated(qs, shipment_row)
