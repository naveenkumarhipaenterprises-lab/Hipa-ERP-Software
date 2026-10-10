from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Avg, Count, F, Q, Sum
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.ai_assistant import insights
from apps.core import periods
from apps.core import parsing
from apps.core.metrics import choices, kpi, label_choices, num, ratio_pct, resolve_choice
from apps.core.views import ModuleAPIView
from apps.customers.models import Customer
from apps.purchase.models import Purchase, RawMaterial, Supplier, Unit
from apps.sales.models import SalesOrder
from services import audit, notifications

from .models import Shipment
from .services import monthly_usage_by_material

Sh = Shipment.Status


def shipment_row(s):
    return {"id": s.id, "shipment_number": s.shipment_number, "supplier": s.supplier.name,
            "purchase_number": s.purchase.purchase_number if s.purchase else None, "item": s.item.name,
            "quantity": num(s.quantity), "unit": s.unit, "destination": s.destination, "eta": s.eta,
            "dispatched_on": s.dispatched_on, "delivered_on": s.delivered_on, "status": s.get_status_display(),
            "quality_passed": s.quality_passed, "can_update": s.status != Sh.DELIVERED, "can_link_purchase": s.purchase_id is None}


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
            "units": choices(Unit),
            # Open purchases a shipment can be linked to (supplier, item and unit are copied from it)
            "purchases": [{"id": p.id, "purchase_number": p.purchase_number, "supplier": p.supplier.name, "item": p.item_name,
                           "quantity": num(p.quantity - p.received_quantity), "unit": p.unit}
                          for p in Purchase.objects.select_related("supplier", "material", "product").filter(status__in=Purchase.OPEN)],
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

    def post(self, request):
        d, errors = request.data, {}
        purchase = parsing.record(d, "purchase_id", Purchase.objects.select_related("supplier", "material", "product")
                                  .filter(status__in=Purchase.OPEN), errors, required=False, message="Choose an open purchase.")
        if purchase:  # supplier, item and unit come from the purchase
            supplier, material, product, unit = purchase.supplier, purchase.material, purchase.product, purchase.unit
        else:
            supplier = parsing.record(d, "supplier_id", Supplier.objects.filter(status=Supplier.Status.ACTIVE), errors,
                                      message="Choose the supplier (or a purchase).")
            material = parsing.record(d, "material_id", RawMaterial.objects.filter(status=RawMaterial.Status.ACTIVE), errors,
                                      message="Choose the raw material (or a purchase).")
            product = None
            unit = parsing.choice(d, "unit", Unit, errors, default=Unit.KG)
        quantity = parsing.decimal(d, "quantity", errors, places=3, positive=True,
                                   default=(purchase.quantity - purchase.received_quantity) if purchase else None,
                                   message="Enter the quantity shipped.")
        destination = parsing.text(d, "destination", 120, required=True, errors=errors)
        dispatched_on = parsing.date(d, "dispatched_on", errors, required=False, label="dispatch date") or periods.today()
        eta = parsing.date(d, "eta", errors, label="expected arrival date")
        if dispatched_on > periods.today():
            errors["dispatched_on"] = ["The dispatch date can't be in the future."]
        if eta and eta < dispatched_on:
            errors["eta"] = ["The expected arrival can't be before the dispatch date."]
        if errors:
            raise ValidationError(errors)
        s = Shipment.objects.create(supplier=supplier, purchase=purchase, material=material, product=product, quantity=quantity,
                                    unit=unit, destination=destination, dispatched_on=dispatched_on, eta=eta)
        audit.record(request, "Created shipment", f"{s.shipment_number} from {supplier.name}")
        return Response(shipment_row(s), status=status.HTTP_201_CREATED)


def linkable_purchases(s):
    """Open purchases (Pending / Partially Received) from the shipment's supplier for the same item and unit."""
    qs = Purchase.objects.select_related("supplier", "material", "product").filter(
        status__in=Purchase.OPEN, supplier_id=s.supplier_id, unit=s.unit)
    return qs.filter(material_id=s.material_id) if s.material_id else qs.filter(product_id=s.product_id)


class ShipmentPurchaseView(SupplyView):
    """
    GET: the purchases a shipment saved without one can be linked to. POST {purchase_id}: links it.
    Only the link changes: supplier, item, quantity, dates, status and stock stay as they are.
    """

    def get(self, request, pk):
        s = get_object_or_404(Shipment, pk=pk)
        return Response([{"id": p.id, "purchase_number": p.purchase_number, "supplier": p.supplier.name, "item": p.item_name,
                          "quantity": num(p.quantity - p.received_quantity), "unit": p.unit, "purchase_date": p.purchase_date}
                         for p in linkable_purchases(s).order_by("-purchase_date", "-id")])

    def post(self, request, pk):
        errors = {}
        with transaction.atomic():
            s = get_object_or_404(Shipment.objects.select_for_update(of=("self",)).select_related("supplier", "material", "product"), pk=pk)
            if s.purchase_id:
                raise ValidationError({"purchase_id": [f"{s.shipment_number} is already linked to a purchase."]})
            purchase = parsing.record(request.data, "purchase_id", linkable_purchases(s), errors,
                                      message=f"Choose an open purchase from {s.supplier.name} for {s.item.name} ({s.unit}).")
            if errors:
                raise ValidationError(errors)
            s.purchase = purchase
            s.save(update_fields=["purchase"])
        audit.record(request, "Linked shipment to purchase", f"{s.shipment_number} -> {purchase.purchase_number}")
        return Response(shipment_row(Shipment.objects.select_related("supplier", "purchase", "material", "product").get(pk=pk)))


class ShipmentStatusView(SupplyView):
    """
    POST {status, delivered_on?, quality_passed?}: In Transit <-> Delayed, either -> Delivered (final).
    Delivery doesn't add stock: that is the goods receipt in Purchase.
    """

    def post(self, request, pk):
        d, errors = request.data, {}
        with transaction.atomic():
            s = get_object_or_404(Shipment.objects.select_for_update(of=("self",)).select_related("supplier"), pk=pk)
            if s.status == Sh.DELIVERED:
                raise ValidationError({"status": ["A delivered shipment can't change status."]})
            new = parsing.choice(d, "status", Sh, errors, message="Choose the new status.")
            if new and new == s.status:
                errors["status"] = [f"The shipment is already {s.get_status_display().lower()}."]
            if new == Sh.DELIVERED:
                s.delivered_on = parsing.date(d, "delivered_on", errors, required=False, label="delivery date") or periods.today()
                if s.delivered_on > periods.today():
                    errors["delivered_on"] = ["The delivery date can't be in the future."]
                elif s.delivered_on < s.dispatched_on:
                    errors["delivered_on"] = ["The delivery date can't be before the dispatch date."]
                passed = d.get("quality_passed")
                s.quality_passed = None if passed in (None, "") else str(passed).lower() in ("true", "1", "yes")
            if errors:
                raise ValidationError(errors)
            s.status = new
            s.save()
        audit.record(request, f"Marked shipment {s.get_status_display().lower()}", s.shipment_number)
        if new == Sh.DELAYED:
            notifications.notify("shipment_delays", f"Shipment {s.shipment_number} delayed",
                                 f"{s.supplier.name}, was expected {s.eta:%d %b %Y}", type="error", link="/supply-chain")
        return Response(shipment_row(Shipment.objects.select_related("supplier", "purchase", "material", "product").get(pk=pk)))
