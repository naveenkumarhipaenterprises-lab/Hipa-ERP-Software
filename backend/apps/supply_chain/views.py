from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.db.models import Avg, Count, F, Q, Sum
from django.utils.dateparse import parse_date
from rest_framework import serializers, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.ai_assistant import insights
from apps.core import periods
from apps.core.metrics import choices, kpi, label_choices, num, ratio_pct, resolve_choice
from apps.core.views import ModuleAPIView
from apps.customers.models import Customer
from apps.production.models import ProductionBatch
from apps.sales.models import SalesOrder
from services import audit

from .models import PurchaseOrder, RawMaterial, Shipment, Supplier
from .services import monthly_usage

Sh = Shipment.Status


def shipment_row(s):
    return {"id": s.id, "shipment_number": s.shipment_number, "supplier": s.supplier.name, "material": s.material.name,
            "quantity_kg": num(s.quantity_kg), "destination": s.destination, "eta": s.eta,
            "delivered_on": s.delivered_on, "status": s.get_status_display()}


def supplier_scores(supplier_ids=None, since=None):
    """quality_pct, on_time_pct and cost_efficiency_pct per supplier from delivered shipments and POs."""
    delivered = Shipment.objects.filter(status=Sh.DELIVERED)
    pos = PurchaseOrder.objects.exclude(status=PurchaseOrder.Status.CANCELLED).exclude(rate_per_kg=None)
    if since:
        delivered = delivered.filter(delivered_on__gte=since)
        pos = pos.filter(order_date__gte=since)
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
    # Cost efficiency: the average rate paid for each material across all suppliers divided by
    # this supplier's rate, weighted by quantity; capped at 100%.
    market = {r["material_id"]: r["avg"] for r in pos.values("material_id").annotate(avg=Avg("rate_per_kg"))}
    per_supplier = {}
    for po in pos.values("supplier_id", "material_id", "rate_per_kg", "quantity_kg"):
        if not po["rate_per_kg"]:
            continue
        eff = min(float(market[po["material_id"]]) / float(po["rate_per_kg"]), 1.0)
        total = per_supplier.setdefault(po["supplier_id"], [0.0, 0.0])
        total[0] += eff * float(po["quantity_kg"])
        total[1] += float(po["quantity_kg"])
    for sid, (weighted, qty) in per_supplier.items():
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

        def procurement(p):
            return PurchaseOrder.objects.filter(order_date__range=(p.start, p.end)).exclude(
                status=PurchaseOrder.Status.CANCELLED).exclude(rate_per_kg=None).aggregate(
                v=Sum(F("quantity_kg") * F("rate_per_kg")))["v"] or 0

        def on_time(p):
            d = Shipment.objects.filter(status=Sh.DELIVERED, delivered_on__range=(p.start, p.end))
            return ratio_pct(d.filter(delivered_on__lte=F("eta")).count(), d.count())

        raw = []
        for m in RawMaterial.objects.filter(is_active=True):
            usage = monthly_usage(m)
            days_left = round(float(m.stock_kg) / (float(usage) / 30), 1) if usage > 0 else None
            raw.append({"id": m.id, "material": m.name, "stock_kg": num(m.stock_kg), "monthly_usage_kg": num(usage),
                        "days_left": days_left, "status": material_status(m.stock_kg, m.reorder_level_kg, days_left)})

        alerts = []
        for s in Shipment.objects.select_related("supplier").filter(Q(status=Sh.DELAYED) | Q(status=Sh.IN_TRANSIT, eta__lt=t))[:5]:
            alerts.append({"id": f"shipment-{s.id}", "type": "error", "title": f"Shipment {s.shipment_number} is delayed",
                           "detail": f"{s.supplier.name}, expected {s.eta:%d %b %Y}"})
        for r in raw:
            if r["status"] in ("Reorder", "Out of Stock"):
                alerts.append({"id": f"material-{r['id']}", "type": "warning", "title": f"{r['material']}: {r['status'].lower()}",
                               "detail": f"{r['stock_kg']} kg left" + (f", about {r['days_left']:g} days of use" if r["days_left"] is not None else "")})
        for po in PurchaseOrder.objects.select_related("supplier", "material").filter(status__in=PurchaseOrder.OPEN, expected_delivery__lt=t)[:5]:
            alerts.append({"id": f"po-{po.id}", "type": "warning", "title": f"{po.po_number} is overdue",
                           "detail": f"{po.material.name} from {po.supplier.name}, expected {po.expected_delivery:%d %b %Y}"})

        open_pos = PurchaseOrder.objects.filter(status__in=PurchaseOrder.OPEN)
        suppliers = Supplier.objects.filter(is_active=True).count()
        has_flow = any([suppliers, open_pos.exists(), RawMaterial.objects.exists(), Customer.objects.exists()])
        flow = [
            {"stage": "farmers", "label": "Suppliers", "count": suppliers, "detail": "Active suppliers"},
            {"stage": "processing", "label": "Procurement", "count": open_pos.count(), "detail": "Open purchase orders"},
            {"stage": "warehouse", "label": "Warehouse", "count": RawMaterial.objects.filter(is_active=True, stock_kg__gt=0).count(), "detail": "Materials in stock"},
            {"stage": "production", "label": "Production", "count": ProductionBatch.objects.filter(stage__in=ProductionBatch.OPEN_STAGES).count(), "detail": "Batches in progress"},
            {"stage": "distribution", "label": "Distribution", "count": SalesOrder.objects.filter(status=SalesOrder.Status.IN_TRANSIT).count(), "detail": "Orders in transit"},
            {"stage": "customers", "label": "Customers", "count": Customer.objects.filter(status=Customer.Status.ACTIVE).count(), "detail": "Active customers"},
        ] if has_flow else []

        return Response({
            "kpis": {
                "total_suppliers": kpi(suppliers, compare=False),
                "active_shipments": kpi(Shipment.objects.exclude(status=Sh.DELIVERED).count(), compare=False),
                "on_time_delivery_pct": kpi(on_time(cur), on_time(prev)),
                "procurement_cost": kpi(procurement(cur), procurement(prev)),
                "pending_orders": kpi(open_pos.count(), compare=False),
            },
            "flow": flow,
            "shipment_summary": {
                "in_transit": Shipment.objects.filter(status=Sh.IN_TRANSIT).count(),
                "delivered": Shipment.objects.filter(status=Sh.DELIVERED, delivered_on__range=(cur.start, cur.end)).count(),
                "delayed": Shipment.objects.filter(status=Sh.DELAYED).count(),
            },
            "raw_materials": raw,
            "recent_shipments": [shipment_row(s) for s in Shipment.objects.select_related("supplier", "material")[:6]],
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
            "suppliers": list(Supplier.objects.filter(is_active=True).values("id", "name")),
            "materials": list(RawMaterial.objects.filter(is_active=True).values("id", "name")),
            "shipment_statuses": label_choices(Sh),
        })


class ShipmentsView(SupplyView):
    def get(self, request):
        qs = Shipment.objects.select_related("supplier", "material")
        q = self.param("search")
        if q:
            qs = qs.filter(Q(shipment_number__icontains=q) | Q(supplier__name__icontains=q) | Q(destination__icontains=q) | Q(material__name__icontains=q))
        st = resolve_choice(Sh, self.param("status"), "status")
        if st:
            qs = qs.filter(status=st)
        return self.paginated(qs, shipment_row)


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = ["name", "city", "contact_person", "phone", "email"]

    def validate_name(self, value):
        value = value.strip()
        if Supplier.objects.filter(name__iexact=value).exists():
            raise serializers.ValidationError(f"Supplier {value} already exists.")
        return value


def supplier_row(s, scores):
    sc = scores.get(s.id, {})
    return {"id": s.id, "name": s.name, "city": s.city, "contact_person": s.contact_person, "phone": s.phone,
            "email": s.email, "quality_pct": sc.get("quality_pct"), "on_time_pct": sc.get("on_time_pct"),
            "status": "Active" if s.is_active else "Inactive"}


class SuppliersView(SupplyView):
    def get(self, request):
        qs = Supplier.objects.all()
        q = self.param("search")
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(city__icontains=q) | Q(contact_person__icontains=q))
        page = self.paginate_queryset(qs.order_by("name"))
        scores = supplier_scores([s.id for s in page])
        return self.get_paginated_response([supplier_row(s, scores) for s in page])

    def post(self, request):
        data = {k: (v.strip() if isinstance(v, str) else v) for k, v in request.data.items()}
        if data.get("phone"):
            data["phone"] = data["phone"].replace(" ", "").replace("-", "")
        ser = SupplierSerializer(data=data)
        ser.is_valid(raise_exception=True)
        supplier = ser.save()
        audit.record(request, "Added supplier", supplier.name)
        return Response(supplier_row(supplier, {}), status=status.HTTP_201_CREATED)


class PurchaseOrdersView(SupplyView):
    def post(self, request):
        d = request.data
        errors = {}
        supplier = Supplier.objects.filter(pk=d.get("supplier_id"), is_active=True).first() if str(d.get("supplier_id", "")).isdigit() else None
        if not supplier:
            errors["supplier_id"] = ["Choose a supplier."]
        material = RawMaterial.objects.filter(pk=d.get("material_id"), is_active=True).first() if str(d.get("material_id", "")).isdigit() else None
        if not material:
            errors["material_id"] = ["Choose a material."]
        try:
            qty = Decimal(str(d.get("quantity_kg")))
            if qty <= 0 or qty.as_tuple().exponent < -3:
                raise InvalidOperation
        except (InvalidOperation, ValueError, TypeError):
            errors["quantity_kg"] = ["Enter a quantity greater than 0 (up to 3 decimals)."]
        rate = None
        if d.get("rate_per_kg") not in (None, ""):
            try:
                rate = Decimal(str(d.get("rate_per_kg")))
                if rate < 0 or rate.as_tuple().exponent < -2:
                    raise InvalidOperation
            except (InvalidOperation, ValueError, TypeError):
                errors["rate_per_kg"] = ["Enter a rate of 0 or more (up to 2 decimals)."]
        expected = parse_date(str(d.get("expected_delivery") or ""))
        if not expected:
            errors["expected_delivery"] = ["Enter the expected delivery date (YYYY-MM-DD)."]
        elif expected < periods.today():
            errors["expected_delivery"] = ["The expected delivery date can't be in the past."]
        if errors:
            raise ValidationError(errors)
        po = PurchaseOrder.objects.create(supplier=supplier, material=material, quantity_kg=qty, rate_per_kg=rate,
                                          order_date=periods.today(), expected_delivery=expected,
                                          notes=str(d.get("notes") or "").strip()[:500], created_by=request.user)
        audit.record(request, "Created purchase order", po.po_number)
        return Response({"id": po.id, "po_number": po.po_number, "supplier": supplier.name, "material": material.name,
                         "quantity_kg": num(qty), "rate_per_kg": num(rate), "amount": num(po.amount),
                         "expected_delivery": expected, "status": po.get_status_display()}, status=status.HTTP_201_CREATED)
