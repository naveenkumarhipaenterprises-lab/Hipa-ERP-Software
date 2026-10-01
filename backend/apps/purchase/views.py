from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Min, Q, Sum
from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.ai_assistant import insights
from apps.core import parsing, periods
from apps.core.metrics import choices, kpi, label_choices, num, ratio_pct, resolve_choice
from apps.core.roles import can_write
from apps.core.views import ModuleAPIView
from apps.inventory.models import Product
from apps.system.models import BillingSettings
from services import audit

from . import services
from .models import GoodsReceipt, MaterialMovement, Purchase, PurchaseReturn, RawMaterial, Supplier, SupplierPayment, Unit

ZERO = Decimal("0")
PSt = Purchase.Status
PaySt = Purchase.PaymentStatus
QSt = GoodsReceipt.QualityStatus
RSt = PurchaseReturn.Status
SPSt = SupplierPayment.Status
MONEY = DecimalField(max_digits=14, decimal_places=2)
MAX_QTY = Decimal("999999999")
MAX_PRICE = Decimal("9999999999")


def ref(obj):
    return {"id": obj.id, "name": obj.name} if obj else None


# --- Rows -----------------------------------------------------------------------------------

def supplier_row(s, purchase_value=None):
    return {
        "id": s.id, "supplier_code": s.supplier_code, "name": s.name, "company_name": s.company_name,
        "contact_person": s.contact_person, "phone": s.phone, "email": s.email, "address": s.address,
        "city": s.city, "state": s.state, "gstin": s.gstin, "payment_terms": s.payment_terms, "credit_days": s.credit_days,
        "status": s.get_status_display(), "created_at": s.created_at, "purchase_value": num(purchase_value),
    }


def material_row(m):
    return {
        "id": m.id, "material_code": m.material_code, "name": m.name, "category": m.category,
        "category_label": m.get_category_display(), "unit": m.unit, "current_stock": num(m.current_stock),
        "minimum_stock": num(m.minimum_stock), "reorder_level": num(m.reorder_level), "supplier_id": m.supplier_id,
        "supplier": m.supplier.name if m.supplier else None, "purchase_price": num(m.purchase_price),
        "status": m.get_status_display(), "stock_status": m.stock_status,
    }


def movement_row(mv):
    return {"id": mv.id, "material": mv.material.name, "type": mv.type, "source": mv.get_source_display(),
            "quantity": num(mv.quantity), "unit": mv.material.unit, "date": mv.date, "reference": mv.reference or None,
            "note": mv.note or None}


def purchase_row(p, editable=True):
    untouched = not p.goods_receipts.exists() and not p.payments.exists() and not p.returns.exists()
    pay = p.payment_status
    return {
        "id": p.id, "purchase_number": p.purchase_number, "supplier_id": p.supplier_id, "supplier": p.supplier.name,
        "item_type": p.item_type, "material_id": p.material_id, "product_id": p.product_id, "item": p.item_name,
        "quantity": num(p.quantity), "unit": p.unit, "unit_price": num(p.unit_price), "discount_pct": num(p.discount_pct),
        "gst_pct": num(p.gst_pct), "subtotal": num(p.subtotal), "discount_amount": num(p.discount_amount),
        "gst_amount": num(p.gst_amount), "total_amount": num(p.total_amount), "purchase_date": p.purchase_date,
        "expected_receipt_date": p.expected_receipt_date, "payment_due_date": p.payment_due_date,
        "status": p.get_status_display(), "received_quantity": num(p.received_quantity),
        "pending_quantity": num(max(p.quantity - p.received_quantity, ZERO)), "paid_amount": num(p.paid_amount),
        "returned_amount": num(p.returned_amount), "balance": num(p.balance),
        "payment_status": PaySt(pay).label if pay else None, "notes": p.notes or None,
        "can_edit": editable and p.status != PSt.CANCELLED,
        "can_edit_all": editable and p.status == PSt.PENDING and untouched,
        "can_cancel": editable and p.status == PSt.PENDING and untouched,
        "can_delete": editable and p.status in (PSt.PENDING, PSt.CANCELLED) and untouched,
    }


def grn_row(g):
    p = g.purchase
    return {
        "id": g.id, "grn_number": g.grn_number, "purchase_id": p.id, "purchase_number": p.purchase_number,
        "supplier": p.supplier.name, "item": p.item_name, "received_date": g.received_date,
        "received_quantity": num(g.received_quantity), "damaged_quantity": num(g.damaged_quantity),
        "accepted_quantity": num(g.accepted_quantity), "unit": p.unit, "quality_status": g.get_quality_status_display(),
        "remarks": g.remarks or None,
    }


def return_row(r, editable=True):
    return {
        "id": r.id, "return_number": r.return_number, "purchase_id": r.purchase_id,
        "purchase_number": r.purchase.purchase_number if r.purchase else None, "supplier_id": r.supplier_id,
        "supplier": r.supplier.name, "item": r.item.name, "quantity": num(r.quantity), "unit": r.unit,
        "return_date": r.return_date, "reason": r.get_reason_display(), "amount": num(r.amount),
        "status": r.get_status_display(), "remarks": r.remarks or None,
        "can_update": editable and r.status == RSt.PENDING,
    }


def payment_row(pm, editable=True):
    return {
        "id": pm.id, "payment_number": pm.payment_number, "supplier_id": pm.supplier_id, "supplier": pm.supplier.name,
        "purchase_id": pm.purchase_id, "purchase_number": pm.purchase.purchase_number if pm.purchase else None,
        "amount": num(pm.amount), "payment_date": pm.payment_date, "payment_method": pm.get_payment_method_display(),
        "transaction_reference": pm.transaction_reference or None, "status": SPSt(pm.display_status).label,
        "notes": pm.notes or None, "can_mark_paid": editable and pm.status == SPSt.PENDING,
        "can_delete": editable and pm.status == SPSt.PENDING,
    }


# --- Shared query helpers -------------------------------------------------------------------

def purchases_qs():
    return Purchase.objects.select_related("supplier", "material", "product")


def payable_expr():
    return ExpressionWrapper(F("total_amount") - F("returned_amount"), output_field=MONEY)


def payment_status_q(value):
    """Filter for a purchase payment status (they are derived from amounts and the due date)."""
    paid = Q(paid_amount__gte=F("payable_amt"))
    overdue = ~paid & Q(payment_due_date__lt=periods.today())
    return {
        PaySt.PAID: paid,
        PaySt.OVERDUE: overdue,
        PaySt.PARTIALLY_PAID: ~paid & ~overdue & Q(paid_amount__gt=0),
        PaySt.PENDING: ~paid & ~overdue & Q(paid_amount=0),
    }[value]


def outstanding_total():
    return (Purchase.objects.exclude(status=PSt.CANCELLED).annotate(payable_amt=payable_expr())
            .aggregate(t=Sum(F("payable_amt") - F("paid_amount"), output_field=MONEY, filter=Q(paid_amount__lt=F("payable_amt"))))["t"] or ZERO)


def date_filter(view, qs, field):
    """?range=<key> or ?date_from / ?date_to on a DateField."""
    if view.param("range"):
        cur, _ = periods.resolve(view.param("range"))
        qs = qs.filter(**{f"{field}__range": (cur.start, cur.end)})
    errors = {}
    start = parsing.date(view.request.query_params, "date_from", errors, required=False, label="start date")
    end = parsing.date(view.request.query_params, "date_to", errors, required=False, label="end date")
    if errors:
        raise ValidationError(errors)
    if start:
        qs = qs.filter(**{f"{field}__gte": start})
    if end:
        qs = qs.filter(**{f"{field}__lte": end})
    return qs


def ordering(view, allowed, default):
    value = view.param("ordering") or default
    if value.lstrip("-") not in allowed:
        raise ValidationError({"ordering": [f"Sort by one of: {', '.join(allowed)} (prefix - for descending)."]})
    return value


class PurchaseView(ModuleAPIView):
    module = "purchase"

    @property
    def editable(self):
        return can_write(self.request.user, self.write_module or "purchase")


# --- Overview, trend, options -----------------------------------------------------------------

def supplier_performance(since):
    """Per supplier: purchases, value, on-time receipt % (first GRN by the expected date) and accepted %."""
    purchases = Purchase.objects.exclude(status=PSt.CANCELLED).filter(purchase_date__gte=since)
    rows = {}
    for r in purchases.values("supplier_id", "supplier__name").annotate(n=Count("id"), value=Sum("total_amount")):
        rows[r["supplier_id"]] = {"supplier_id": r["supplier_id"], "supplier": r["supplier__name"], "purchases": r["n"],
                                  "purchase_value": num(r["value"]), "on_time_pct": None, "accepted_pct": None,
                                  "damaged_pct": None}
    timed = (purchases.exclude(expected_receipt_date=None).annotate(first=Min("goods_receipts__received_date"))
             .exclude(first=None).values("supplier_id", "first", "expected_receipt_date"))
    on_time = {}
    for t in timed:
        hits = on_time.setdefault(t["supplier_id"], [0, 0])
        hits[0] += t["first"] <= t["expected_receipt_date"]
        hits[1] += 1
    for sid, (ok, n) in on_time.items():
        rows[sid]["on_time_pct"] = ratio_pct(ok, n)
    grns = (GoodsReceipt.objects.filter(purchase__in=purchases).values("purchase__supplier_id")
            .annotate(rec=Sum("received_quantity"), acc=Sum("accepted_quantity"), dmg=Sum("damaged_quantity")))
    for g in grns:
        row = rows[g["purchase__supplier_id"]]
        row["accepted_pct"] = ratio_pct(g["acc"], g["rec"])
        row["damaged_pct"] = ratio_pct(g["dmg"], g["rec"])
    return sorted(rows.values(), key=lambda r: -(r["purchase_value"] or 0))


def low_stock_materials():
    out = []
    for m in RawMaterial.objects.filter(status=RawMaterial.Status.ACTIVE).select_related("supplier"):
        if m.stock_status != "In Stock":
            out.append({"id": m.id, "material": m.name, "current_stock": num(m.current_stock), "reorder_level": num(m.reorder_level),
                        "unit": m.unit, "status": m.stock_status, "supplier": m.supplier.name if m.supplier else None})
    return sorted(out, key=lambda r: (r["current_stock"] or 0) - (r["reorder_level"] or 0))


class OverviewView(PurchaseView):
    def get(self, request):
        cur, prev = periods.resolve(self.param("range"))
        live = Purchase.objects.exclude(status=PSt.CANCELLED)

        def totals(p):
            qs = live.filter(purchase_date__range=(p.start, p.end))
            agg = qs.aggregate(n=Count("id"), v=Sum("total_amount"))
            returns = PurchaseReturn.objects.exclude(status=RSt.CANCELLED).filter(return_date__range=(p.start, p.end))
            return {"count": agg["n"], "value": agg["v"] or ZERO, "received": qs.filter(status=PSt.RECEIVED).count(),
                    "returns": returns.count()}

        now, before = totals(cur), totals(prev)
        top = (live.filter(purchase_date__range=(cur.start, cur.end))
               .values("material__name", "product__name", "unit")
               .annotate(qty=Sum("quantity"), value=Sum("total_amount"), n=Count("id")).order_by("-value")[:5])
        recent = purchases_qs().prefetch_related("goods_receipts", "payments", "returns")[:5]
        return Response({
            "kpis": {
                "total_purchases": kpi(now["count"], before["count"]),
                "purchase_value": kpi(now["value"], before["value"]),
                "pending_purchases": kpi(live.filter(status__in=Purchase.OPEN).count(), compare=False),
                "received_purchases": kpi(now["received"], before["received"]),
                "purchase_returns": kpi(now["returns"], before["returns"]),
                "supplier_count": kpi(Supplier.objects.filter(status=Supplier.Status.ACTIVE).count(), compare=False),
                "outstanding_payments": kpi(outstanding_total(), compare=False),
            },
            "top_materials": [{"item": r["material__name"] or r["product__name"], "quantity": num(r["qty"]), "unit": r["unit"],
                               "value": num(r["value"]), "purchases": r["n"]} for r in top],
            "supplier_performance": supplier_performance(periods.today() - timedelta(days=180))[:8],
            "low_stock": low_stock_materials()[:8],
            "recent_purchases": [purchase_row(p, False) for p in recent],
            "insights": insights.block("purchase"),
        })


class TrendView(PurchaseView):
    def get(self, request):
        cur, _ = periods.resolve(self.param("range"))
        granularity = periods.parse_choice(self.param("granularity"), ["daily", "weekly", "monthly"], "granularity", "daily")
        daily = dict(Purchase.objects.exclude(status=PSt.CANCELLED).filter(purchase_date__range=(cur.start, cur.end))
                     .values_list("purchase_date").annotate(t=Sum("total_amount")))
        if not daily:
            return Response([])
        if granularity == "monthly":
            buckets = [(s, e, label) for s, e, label in periods.last_n_months(12, cur.end) if e >= cur.start]
        else:
            step, buckets, day = (1 if granularity == "daily" else 7), [], cur.start
            while day <= cur.end:
                last = min(day + timedelta(days=step - 1), cur.end)
                buckets.append((day, last, day.strftime("%d %b") if step == 1 else f"{day:%d %b}–{last:%d %b}"))
                day = last + timedelta(days=1)
        return Response([{"label": label, "value": num(sum((v for d, v in daily.items() if s <= d <= e), ZERO))}
                         for s, e, label in buckets])


class OptionsView(PurchaseView):
    def get(self, request):
        open_purchases = (purchases_qs().exclude(status=PSt.CANCELLED).annotate(payable_amt=payable_expr())
                          .filter(Q(status__in=Purchase.OPEN) | Q(paid_amount__lt=F("payable_amt")) | Q(received_quantity__gt=0))
                          .order_by("-purchase_date", "-id")[:500])
        return Response({
            "suppliers": [{"id": s.id, "name": s.name, "credit_days": s.credit_days}
                          for s in Supplier.objects.filter(status=Supplier.Status.ACTIVE)],
            "materials": [{"id": m.id, "name": m.name, "unit": m.unit, "purchase_price": num(m.purchase_price), "supplier_id": m.supplier_id}
                          for m in RawMaterial.objects.filter(status=RawMaterial.Status.ACTIVE)],
            "products": [{"id": p.id, "name": p.name, "unit": "kg"} for p in Product.objects.filter(is_active=True)],
            "purchases": [{"id": p.id, "purchase_number": p.purchase_number, "supplier_id": p.supplier_id, "supplier": p.supplier.name,
                           "item": p.item_name, "unit": p.unit, "status": p.get_status_display(),
                           "pending_quantity": num(max(p.quantity - p.received_quantity, ZERO)),
                           "received_quantity": num(p.received_quantity), "balance": num(p.balance)} for p in open_purchases],
            "units": choices(Unit),
            "categories": choices(RawMaterial.Category),
            "supplier_statuses": label_choices(Supplier.Status),
            "material_statuses": label_choices(RawMaterial.Status),
            "purchase_statuses": label_choices(PSt),
            "payment_statuses": label_choices(PaySt),
            "quality_statuses": label_choices(QSt),
            "return_reasons": label_choices(PurchaseReturn.Reason),
            "return_statuses": label_choices(RSt),
            "payment_methods": label_choices(SupplierPayment.Method),
            "supplier_payment_statuses": label_choices(SPSt),
        })


# --- Suppliers ------------------------------------------------------------------------------

class SupplierSerializer(serializers.ModelSerializer):
    status = serializers.CharField(required=False)

    class Meta:
        model = Supplier
        fields = ["name", "company_name", "contact_person", "phone", "email", "address", "city", "state", "gstin",
                  "payment_terms", "credit_days", "status"]

    def to_internal_value(self, data):
        data = {k: (v.strip() if isinstance(v, str) else v) for k, v in data.items()}
        if data.get("phone"):
            data["phone"] = data["phone"].replace(" ", "").replace("-", "")
        if data.get("gstin"):
            data["gstin"] = data["gstin"].upper()
        if data.get("credit_days") == "":
            data["credit_days"] = None
        return super().to_internal_value(data)

    def validate_name(self, value):
        qs = Supplier.objects.filter(name__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(f"Supplier {value} already exists.")
        return value

    def validate_status(self, value):
        return resolve_choice(Supplier.Status, value, "status")


class SuppliersView(PurchaseView):
    def get(self, request):
        qs = Supplier.objects.annotate(value=Sum("purchases__total_amount", filter=~Q(purchases__status=PSt.CANCELLED)))
        q = self.param("search")
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(company_name__icontains=q) | Q(contact_person__icontains=q) |
                           Q(city__icontains=q) | Q(gstin__icontains=q) | Q(supplier_code__icontains=q) | Q(phone__icontains=q))
        st = resolve_choice(Supplier.Status, self.param("status"), "status")
        if st:
            qs = qs.filter(status=st)
        for field in ("city", "state"):
            if self.param(field):
                qs = qs.filter(**{f"{field}__iexact": self.param(field)})
        qs = qs.order_by(ordering(self, ["name", "city", "state", "created_at", "value"], "name"), "id")
        return self.paginated(qs, lambda s: supplier_row(s, s.value))

    def post(self, request):
        ser = SupplierSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        supplier = ser.save(created_by=request.user)
        audit.record(request, "Added supplier", f"{supplier.supplier_code} {supplier.name}")
        return Response(supplier_row(supplier), status=status.HTTP_201_CREATED)


class SupplierDetailView(PurchaseView):
    def get(self, request, pk):
        s = get_object_or_404(Supplier, pk=pk)
        live = s.purchases.exclude(status=PSt.CANCELLED).annotate(payable_amt=payable_expr())
        row = supplier_row(s, live.aggregate(t=Sum("total_amount"))["t"])
        row["outstanding"] = num(live.filter(paid_amount__lt=F("payable_amt")).aggregate(
            t=Sum(F("payable_amt") - F("paid_amount"), output_field=MONEY))["t"] or ZERO)
        row["recent_purchases"] = [purchase_row(p, False) for p in purchases_qs().filter(supplier=s).prefetch_related(
            "goods_receipts", "payments", "returns")[:10]]
        return Response(row)

    def patch(self, request, pk):
        s = get_object_or_404(Supplier, pk=pk)
        ser = SupplierSerializer(s, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        s = ser.save()
        audit.record(request, "Updated supplier", f"{s.supplier_code} {s.name}")
        return Response(supplier_row(s))

    def delete(self, request, pk):
        s = get_object_or_404(Supplier, pk=pk)
        if s.purchases.exists() or s.payments.exists() or s.returns.exists():
            return Response({"detail": f"{s.name} has purchase records, so it can't be deleted. Set it to Inactive instead."},
                            status=status.HTTP_409_CONFLICT)
        audit.record(request, "Deleted supplier", f"{s.supplier_code} {s.name}")
        s.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# --- Raw materials ----------------------------------------------------------------------------

class MaterialSerializer(serializers.ModelSerializer):
    status = serializers.CharField(required=False)
    supplier_id = serializers.PrimaryKeyRelatedField(source="supplier", queryset=Supplier.objects.all(), required=False, allow_null=True)

    class Meta:
        model = RawMaterial
        fields = ["name", "category", "unit", "minimum_stock", "reorder_level", "supplier_id", "purchase_price", "status"]

    def to_internal_value(self, data):
        data = {k: (v.strip() if isinstance(v, str) else v) for k, v in data.items()}
        for key in ("supplier_id", "purchase_price"):
            if data.get(key) == "":
                data[key] = None
        for key, enum in (("category", RawMaterial.Category), ("unit", Unit)):
            if data.get(key):
                try:
                    data[key] = resolve_choice(enum, data[key], key)
                except ValidationError as exc:
                    raise serializers.ValidationError(exc.detail)
        return super().to_internal_value(data)

    def validate_name(self, value):
        qs = RawMaterial.objects.filter(name__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(f"Material {value} already exists.")
        return value

    def validate_status(self, value):
        return resolve_choice(RawMaterial.Status, value, "status")

    def validate_unit(self, value):
        if self.instance and value != self.instance.unit and (self.instance.movements.exists() or self.instance.purchases.exists()):
            raise serializers.ValidationError("The unit can't change once stock or purchases are recorded in it.")
        return value

    def validate(self, attrs):
        minimum = attrs.get("minimum_stock", self.instance.minimum_stock if self.instance else ZERO)
        reorder = attrs.get("reorder_level", self.instance.reorder_level if self.instance else ZERO)
        if reorder < minimum:
            raise serializers.ValidationError({"reorder_level": ["The reorder level can't be below the minimum stock."]})
        return attrs


class MaterialsView(PurchaseView):
    def get(self, request):
        qs = RawMaterial.objects.select_related("supplier")
        q = self.param("search")
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(material_code__icontains=q) | Q(supplier__name__icontains=q))
        category = resolve_choice(RawMaterial.Category, self.param("category"), "category")
        if category:
            qs = qs.filter(category=category)
        st = resolve_choice(RawMaterial.Status, self.param("status"), "status")
        if st:
            qs = qs.filter(status=st)
        supplier = self.int_param("supplier")
        if supplier:
            qs = qs.filter(supplier_id=supplier)
        stock = self.param("stock_status")
        if stock:
            filters = {"out": Q(current_stock__lte=0), "critical": Q(current_stock__gt=0, current_stock__lte=F("minimum_stock")),
                       "reorder": Q(current_stock__gt=F("minimum_stock"), current_stock__lte=F("reorder_level")),
                       "in_stock": Q(current_stock__gt=F("reorder_level")), "low": Q(current_stock__lte=F("reorder_level"))}
            key = stock.lower().replace(" ", "_").replace("out_of_stock", "out")
            if key not in filters:
                raise ValidationError({"stock_status": ["Use one of: in_stock, low, reorder, critical, out."]})
            qs = qs.filter(filters[key])
        qs = qs.order_by(ordering(self, ["name", "category", "current_stock", "purchase_price"], "name"), "id")
        return self.paginated(qs, material_row)

    def post(self, request):
        errors = {}
        opening = parsing.decimal(request.data, "opening_stock", errors, places=3, maximum=MAX_QTY, required=False)
        ser = MaterialSerializer(data=request.data)
        if not ser.is_valid():
            errors.update(ser.errors)
        if errors:
            raise ValidationError(errors)
        with transaction.atomic():
            material = ser.save()
            if opening:
                services.move_material(material, "in", opening, source=MaterialMovement.Source.OPENING, note="Opening stock",
                                       user=request.user)
        audit.record(request, "Added raw material", f"{material.material_code} {material.name}")
        return Response(material_row(material), status=status.HTTP_201_CREATED)


class MaterialDetailView(PurchaseView):
    def get(self, request, pk):
        m = get_object_or_404(RawMaterial.objects.select_related("supplier"), pk=pk)
        row = material_row(m)
        row["movements"] = [movement_row(mv) for mv in m.movements.select_related("material")[:20]]
        row["price_history"] = [{"purchase_number": p.purchase_number, "date": p.purchase_date, "supplier": p.supplier.name,
                                 "unit_price": num(p.unit_price)}
                                for p in m.purchases.exclude(status=PSt.CANCELLED).select_related("supplier")[:20]]
        return Response(row)

    def patch(self, request, pk):
        m = get_object_or_404(RawMaterial, pk=pk)
        ser = MaterialSerializer(m, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        m = ser.save()
        audit.record(request, "Updated raw material", f"{m.material_code} {m.name}")
        return Response(material_row(m))

    def delete(self, request, pk):
        m = get_object_or_404(RawMaterial, pk=pk)
        if m.movements.exists() or m.purchases.exists() or m.returns.exists():
            return Response({"detail": f"{m.name} has stock or purchase records, so it can't be deleted. Set it to Inactive instead."},
                            status=status.HTTP_409_CONFLICT)
        audit.record(request, "Deleted raw material", f"{m.material_code} {m.name}")
        m.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MaterialMovementsView(PurchaseView):
    """Stock used in processing or corrected by hand. Receipts and returns come from GRNs and purchase returns."""

    write_module = "material_stock"

    def get(self, request):
        qs = MaterialMovement.objects.select_related("material")
        material = self.int_param("material")
        if material:
            qs = qs.filter(material_id=material)
        return self.paginated(date_filter(self, qs, "date"), movement_row)

    def post(self, request):
        d, errors = request.data, {}
        material = parsing.record(d, "material_id", RawMaterial.objects.filter(status=RawMaterial.Status.ACTIVE), errors,
                                  message="Choose an active material.")
        kind = parsing.choice(d, "type", MaterialMovement.Type, errors, message="Choose stock in or out.")
        qty = parsing.decimal(d, "quantity", errors, places=3, positive=True, maximum=MAX_QTY)
        day = parsing.date(d, "date", errors, required=False) or periods.today()
        if day > periods.today():
            errors["date"] = ["The date can't be in the future."]
        if errors:
            raise ValidationError(errors)
        source = MaterialMovement.Source.USAGE if kind == "out" and d.get("source") != "adjustment" else MaterialMovement.Source.ADJUSTMENT
        mv = services.move_material(material, kind, qty, source=source, date=day, reference=parsing.text(d, "reference", 50),
                                    note=parsing.text(d, "note", 255), user=request.user)
        audit.record(request, f"Recorded material {mv.get_source_display().lower()}", material.name)
        return Response(movement_row(mv), status=status.HTTP_201_CREATED)


# --- Purchase transactions --------------------------------------------------------------------

def read_item(d, errors, item_type_key="item_type"):
    """(material, product, unit) from item_type + material_id / product_id."""
    item_type = str(d.get(item_type_key) or ("product" if d.get("product_id") not in (None, "") else "material")).lower()
    if item_type not in ("material", "product"):
        errors[item_type_key] = ["Choose material or product."]
        return None, None, None
    if item_type == "material":
        m = parsing.record(d, "material_id", RawMaterial.objects.filter(status=RawMaterial.Status.ACTIVE), errors,
                           message="Choose an active raw material.")
        return m, None, m.unit if m else None
    p = parsing.record(d, "product_id", Product.objects.filter(is_active=True), errors, message="Choose an active product.")
    return None, p, Unit.KG if p else None


def read_amounts(d, errors, defaults=None):
    defaults = defaults or {}
    return {
        "quantity": parsing.decimal(d, "quantity", errors, places=3, positive=True, maximum=MAX_QTY,
                                    default=defaults.get("quantity"), message="Enter a quantity greater than 0 (up to 3 decimals)."),
        "unit_price": parsing.decimal(d, "unit_price", errors, places=2, maximum=MAX_PRICE, default=defaults.get("unit_price"),
                                      message="Enter a unit price of 0 or more (up to 2 decimals)."),
        "discount_pct": parsing.decimal(d, "discount_pct", errors, maximum=Decimal("100"), default=defaults.get("discount_pct", ZERO),
                                        message="Enter a discount between 0 and 100%."),
        "gst_pct": parsing.decimal(d, "gst_pct", errors, maximum=Decimal("100"), default=defaults.get("gst_pct", ZERO),
                                   message="Enter a GST rate between 0 and 100%."),
    }


class PurchasesView(PurchaseView):
    def get(self, request):
        qs = purchases_qs().prefetch_related("goods_receipts", "payments", "returns")
        q = self.param("search")
        if q:
            qs = qs.filter(Q(purchase_number__icontains=q) | Q(supplier__name__icontains=q) | Q(material__name__icontains=q) |
                           Q(product__name__icontains=q) | Q(notes__icontains=q))
        st = resolve_choice(PSt, self.param("status"), "status")
        if st:
            qs = qs.filter(status=st)
        pay = resolve_choice(PaySt, self.param("payment_status"), "payment_status")
        if pay:
            qs = qs.exclude(status=PSt.CANCELLED).annotate(payable_amt=payable_expr()).filter(payment_status_q(pay))
        for key in ("supplier", "material", "product"):
            value = self.int_param(key)
            if value:
                qs = qs.filter(**{f"{key}_id": value})
        qs = date_filter(self, qs, "purchase_date")
        qs = qs.order_by(ordering(self, ["purchase_date", "total_amount", "purchase_number"], "-purchase_date"), "-id")
        editable = self.editable
        return self.paginated(qs, lambda p: purchase_row(p, editable))

    def post(self, request):
        d, errors = request.data, {}
        supplier = parsing.record(d, "supplier_id", Supplier.objects.filter(status=Supplier.Status.ACTIVE), errors,
                                  message="Choose an active supplier.")
        material, product, unit = read_item(d, errors)
        amounts = read_amounts(d, errors, {"unit_price": material.purchase_price if material else None,
                                           "gst_pct": BillingSettings.load().default_purchase_gst_pct or ZERO})
        purchase_date = parsing.date(d, "purchase_date", errors, label="purchase date")
        expected = parsing.date(d, "expected_receipt_date", errors, required=False, label="expected receipt date")
        due = parsing.date(d, "payment_due_date", errors, required=False, label="payment due date")
        if purchase_date and purchase_date > periods.today():
            errors["purchase_date"] = ["The purchase date can't be in the future."]
        if purchase_date and expected and expected < purchase_date:
            errors["expected_receipt_date"] = ["The expected receipt date can't be before the purchase date."]
        if purchase_date and due and due < purchase_date:
            errors["payment_due_date"] = ["The payment due date can't be before the purchase date."]
        if errors:
            raise ValidationError(errors)
        purchase = Purchase.objects.create(
            supplier=supplier, material=material, product=product, unit=unit, purchase_date=purchase_date,
            expected_receipt_date=expected, payment_due_date=due or services.default_due_date(supplier, purchase_date),
            notes=parsing.text(d, "notes", 500), created_by=request.user, **amounts)
        audit.record(request, "Recorded purchase", purchase.purchase_number)
        services.notify_price_increase(purchase)
        return Response(purchase_row(purchase), status=status.HTTP_201_CREATED)


class PurchaseDetailView(PurchaseView):
    def get(self, request, pk):
        p = get_object_or_404(purchases_qs(), pk=pk)
        row = purchase_row(p, self.editable)
        row["goods_receipts"] = [grn_row(g) for g in p.goods_receipts.select_related("purchase__supplier", "purchase__material",
                                                                                      "purchase__product")]
        row["returns"] = [return_row(r, False) for r in p.returns.select_related("supplier", "material", "product", "purchase")]
        row["payments"] = [payment_row(pm, False) for pm in p.payments.select_related("supplier", "purchase")]
        return Response(row)

    def patch(self, request, pk):
        d, errors = request.data, {}
        with transaction.atomic():
            p = get_object_or_404(Purchase.objects.select_for_update().select_related("supplier", "material", "product"), pk=pk)
            if p.status == PSt.CANCELLED:
                raise ValidationError({"detail": "A cancelled purchase can't be edited."})
            full = p.status == PSt.PENDING and not (p.goods_receipts.exists() or p.payments.exists() or p.returns.exists())
            locked = {"supplier_id", "item_type", "material_id", "product_id", "quantity", "unit_price", "discount_pct", "gst_pct",
                      "purchase_date"} & set(d)
            if locked and not full:
                raise ValidationError({k: ["Can't change after goods, payments or returns are recorded."] for k in locked})
            if full:
                if "supplier_id" in d:
                    p.supplier = parsing.record(d, "supplier_id", Supplier.objects.filter(status=Supplier.Status.ACTIVE), errors,
                                                message="Choose an active supplier.") or p.supplier
                if {"item_type", "material_id", "product_id"} & set(d):
                    material, product, unit = read_item(d, errors)
                    if material or product:
                        p.material, p.product, p.unit = material, product, unit
                for key, value in read_amounts(d, errors, {"quantity": p.quantity, "unit_price": p.unit_price,
                                                           "discount_pct": p.discount_pct, "gst_pct": p.gst_pct}).items():
                    if value is not None:
                        setattr(p, key, value)
                if "purchase_date" in d:
                    day = parsing.date(d, "purchase_date", errors, label="purchase date")
                    if day and day > periods.today():
                        errors["purchase_date"] = ["The purchase date can't be in the future."]
                    elif day:
                        p.purchase_date = day
            for key, label in (("expected_receipt_date", "expected receipt date"), ("payment_due_date", "payment due date")):
                if key in d:
                    value = parsing.date(d, key, errors, required=False, label=label)
                    if value and value < p.purchase_date:
                        errors[key] = [f"The {label} can't be before the purchase date."]
                    elif key not in errors:
                        setattr(p, key, value)
            if "notes" in d:
                p.notes = parsing.text(d, "notes", 500)
            if errors:
                raise ValidationError(errors)
            p.save()
        audit.record(request, "Updated purchase", p.purchase_number)
        p = get_object_or_404(purchases_qs(), pk=pk)
        return Response(purchase_row(p, True))

    def delete(self, request, pk):
        with transaction.atomic():
            p = get_object_or_404(Purchase.objects.select_for_update(), pk=pk)
            if p.goods_receipts.exists() or p.payments.exists() or p.returns.exists():
                return Response({"detail": "This purchase has goods receipts, payments or returns, so it can't be deleted."},
                                status=status.HTTP_409_CONFLICT)
            number = p.purchase_number
            p.delete()
        audit.record(request, "Deleted purchase", number)
        return Response(status=status.HTTP_204_NO_CONTENT)


class CancelPurchaseView(PurchaseView):
    def post(self, request, pk):
        with transaction.atomic():
            p = get_object_or_404(Purchase.objects.select_for_update(), pk=pk)
            if p.status != PSt.PENDING:
                raise ValidationError({"detail": f"A {p.get_status_display().lower()} purchase can't be cancelled."})
            if p.goods_receipts.exists() or p.payments.exists() or p.returns.exists():
                raise ValidationError({"detail": "This purchase has goods receipts, payments or returns, so it can't be cancelled."})
            p.status = PSt.CANCELLED
            p.save(update_fields=["status", "updated_at"])
        audit.record(request, "Cancelled purchase", p.purchase_number)
        return Response(purchase_row(get_object_or_404(purchases_qs(), pk=pk), True))


# --- Goods receipts ---------------------------------------------------------------------------

def grns_qs():
    return GoodsReceipt.objects.select_related("purchase__supplier", "purchase__material", "purchase__product")


class GoodsReceiptsView(PurchaseView):
    def get(self, request):
        qs = grns_qs()
        q = self.param("search")
        if q:
            qs = qs.filter(Q(grn_number__icontains=q) | Q(purchase__purchase_number__icontains=q) |
                           Q(purchase__supplier__name__icontains=q) | Q(purchase__material__name__icontains=q) |
                           Q(purchase__product__name__icontains=q))
        qs_status = resolve_choice(QSt, self.param("quality_status"), "quality_status")
        if qs_status:
            qs = qs.filter(quality_status=qs_status)
        for key, field in (("supplier", "purchase__supplier_id"), ("purchase", "purchase_id")):
            value = self.int_param(key)
            if value:
                qs = qs.filter(**{field: value})
        return self.paginated(date_filter(self, qs, "received_date"), grn_row)

    def post(self, request):
        d, errors = request.data, {}
        purchase = parsing.record(d, "purchase_id", Purchase.objects.filter(status__in=Purchase.OPEN), errors,
                                  message="Choose a purchase that is still to be received.")
        received_date = parsing.date(d, "received_date", errors, label="received date")
        if received_date and received_date > periods.today():
            errors["received_date"] = ["The received date can't be in the future."]
        received = parsing.decimal(d, "received_quantity", errors, places=3, positive=True, maximum=MAX_QTY,
                                   message="Enter the quantity received (greater than 0).")
        damaged = parsing.decimal(d, "damaged_quantity", errors, places=3, maximum=MAX_QTY, default=ZERO,
                                  message="Enter the damaged quantity (0 or more).")
        accepted = parsing.decimal(d, "accepted_quantity", errors, places=3, maximum=MAX_QTY, required=False,
                                   message="Enter the accepted quantity (0 or more).")
        quality = parsing.choice(d, "quality_status", QSt, errors, default=QSt.PENDING)
        if received is not None and damaged is not None:
            if damaged > received:
                errors["damaged_quantity"] = ["The damaged quantity can't be more than the quantity received."]
            elif accepted is None and "accepted_quantity" not in errors:
                accepted = received - damaged
            elif accepted is not None and accepted > received - damaged:
                errors["accepted_quantity"] = ["The accepted quantity can't be more than received minus damaged."]
        if errors:
            raise ValidationError(errors)
        grn, purchase = services.receive_goods(purchase, received_date=received_date, received_quantity=received,
                                               damaged_quantity=damaged, accepted_quantity=accepted, quality_status=quality,
                                               remarks=parsing.text(d, "remarks", 500), user=request.user)
        audit.record(request, "Recorded goods receipt", f"{grn.grn_number} for {purchase.purchase_number}")
        return Response(grn_row(grns_qs().get(pk=grn.pk)), status=status.HTTP_201_CREATED)


class GoodsReceiptDetailView(PurchaseView):
    def get(self, request, pk):
        g = get_object_or_404(grns_qs(), pk=pk)
        row = grn_row(g)
        row["quality_tests"] = [{"id": t.id, "test_date": t.test_date, "result": t.get_result_display(), "parameters": t.parameters}
                                for t in g.quality_tests.all()]
        return Response(row)


# --- Purchase returns -------------------------------------------------------------------------

def returns_qs():
    return PurchaseReturn.objects.select_related("supplier", "material", "product", "purchase")


class ReturnsView(PurchaseView):
    def get(self, request):
        qs = returns_qs()
        q = self.param("search")
        if q:
            qs = qs.filter(Q(return_number__icontains=q) | Q(supplier__name__icontains=q) | Q(material__name__icontains=q) |
                           Q(product__name__icontains=q) | Q(purchase__purchase_number__icontains=q))
        st = resolve_choice(RSt, self.param("status"), "status")
        if st:
            qs = qs.filter(status=st)
        reason = resolve_choice(PurchaseReturn.Reason, self.param("reason"), "reason")
        if reason:
            qs = qs.filter(reason=reason)
        supplier = self.int_param("supplier")
        if supplier:
            qs = qs.filter(supplier_id=supplier)
        editable = self.editable
        return self.paginated(date_filter(self, qs, "return_date"), lambda r: return_row(r, editable))

    def post(self, request):
        d, errors = request.data, {}
        purchase = parsing.record(d, "purchase_id", Purchase.objects.exclude(status=PSt.CANCELLED).select_related(
            "supplier", "material", "product"), errors, required=False, message="Choose a purchase.")
        if purchase:
            supplier, material, product, unit = purchase.supplier, purchase.material, purchase.product, purchase.unit
        else:
            supplier = parsing.record(d, "supplier_id", Supplier.objects.all(), errors, message="Choose a supplier.")
            material, product, unit = read_item(d, errors)
        qty = parsing.decimal(d, "quantity", errors, places=3, positive=True, maximum=MAX_QTY,
                              message="Enter a quantity greater than 0 (up to 3 decimals).")
        return_date = parsing.date(d, "return_date", errors, label="return date")
        if return_date and return_date > periods.today():
            errors["return_date"] = ["The return date can't be in the future."]
        reason = parsing.choice(d, "reason", PurchaseReturn.Reason, errors, message="Choose a reason.")
        amount = parsing.decimal(d, "amount", errors, maximum=MAX_PRICE, required=purchase is None,
                                 message="Enter the return amount (0 or more).")
        if errors:
            raise ValidationError(errors)
        if amount is None:  # value of the returned goods at the purchase's effective price (after discount, with GST)
            amount = (purchase.total_amount / purchase.quantity * qty).quantize(Decimal("0.01"))
        ret = services.create_return(purchase=purchase, supplier=supplier, material=material, product=product, quantity=qty,
                                     unit=unit, return_date=return_date, reason=reason, amount=amount,
                                     remarks=parsing.text(d, "remarks", 500), user=request.user)
        audit.record(request, "Recorded purchase return", ret.return_number)
        return Response(return_row(returns_qs().get(pk=ret.pk)), status=status.HTTP_201_CREATED)


class ReturnDetailView(PurchaseView):
    def get(self, request, pk):
        return Response(return_row(get_object_or_404(returns_qs(), pk=pk), self.editable))

    def patch(self, request, pk):
        errors = {}
        new_status = parsing.choice(request.data, "status", RSt, errors, message="Choose Completed or Cancelled.")
        if new_status == RSt.PENDING:
            errors["status"] = ["Choose Completed or Cancelled."]
        if errors:
            raise ValidationError(errors)
        ret = services.set_return_status(get_object_or_404(PurchaseReturn, pk=pk), new_status, request.user)
        audit.record(request, f"Marked purchase return {RSt(new_status).label.lower()}", ret.return_number)
        return Response(return_row(returns_qs().get(pk=pk), True))


# --- Supplier payments ------------------------------------------------------------------------

def payments_qs():
    return SupplierPayment.objects.select_related("supplier", "purchase")


class PaymentsView(PurchaseView):
    write_module = "supplier_payments"

    def get(self, request):
        qs = payments_qs()
        q = self.param("search")
        if q:
            qs = qs.filter(Q(payment_number__icontains=q) | Q(supplier__name__icontains=q) | Q(transaction_reference__icontains=q) |
                           Q(purchase__purchase_number__icontains=q))
        st = resolve_choice(SPSt, self.param("status"), "status")
        if st == SPSt.OVERDUE:
            qs = qs.filter(status=SPSt.PENDING, payment_date__lt=periods.today())
        elif st == SPSt.PENDING:
            qs = qs.filter(status=SPSt.PENDING, payment_date__gte=periods.today())
        elif st:
            qs = qs.filter(status=st)
        method = resolve_choice(SupplierPayment.Method, self.param("payment_method"), "payment_method")
        if method:
            qs = qs.filter(payment_method=method)
        for key in ("supplier", "purchase"):
            value = self.int_param(key)
            if value:
                qs = qs.filter(**{f"{key}_id": value})
        editable = self.editable
        return self.paginated(date_filter(self, qs, "payment_date"), lambda pm: payment_row(pm, editable))

    def post(self, request):
        d, errors = request.data, {}
        purchase = parsing.record(d, "purchase_id", Purchase.objects.exclude(status=PSt.CANCELLED).select_related("supplier"),
                                  errors, required=False, message="Choose a purchase.")
        supplier = purchase.supplier if purchase else parsing.record(d, "supplier_id", Supplier.objects.all(), errors,
                                                                     message="Choose a supplier.")
        if purchase and d.get("supplier_id") not in (None, "") and str(d.get("supplier_id")) != str(purchase.supplier_id):
            errors["purchase_id"] = ["This purchase belongs to another supplier."]
        amount = parsing.decimal(d, "amount", errors, positive=True, maximum=MAX_PRICE, message="Enter an amount greater than 0.")
        payment_date = parsing.date(d, "payment_date", errors, label="payment date")
        method = parsing.choice(d, "payment_method", SupplierPayment.Method, errors, message="Choose the payment method.")
        raw_status = str(d.get("status") or "paid").strip().lower()
        if raw_status not in ("paid", "pending"):
            errors["status"] = ["Choose Paid (payment made) or Pending (scheduled)."]
        paid = raw_status == "paid"
        if paid and payment_date and payment_date > periods.today():
            errors["payment_date"] = ["A payment that has been made can't be dated in the future."]
        if errors:
            raise ValidationError(errors)
        payment = services.record_payment(supplier=supplier, purchase=purchase, amount=amount, payment_date=payment_date,
                                          method=method, reference=parsing.text(d, "transaction_reference", 80),
                                          notes=parsing.text(d, "notes", 500), paid=paid, user=request.user)
        audit.record(request, "Recorded supplier payment" if paid else "Scheduled supplier payment", payment.payment_number)
        return Response(payment_row(payments_qs().get(pk=payment.pk)), status=status.HTTP_201_CREATED)


class PaymentDetailView(PurchaseView):
    write_module = "supplier_payments"

    def get(self, request, pk):
        return Response(payment_row(get_object_or_404(payments_qs(), pk=pk), self.editable))

    def delete(self, request, pk):
        with transaction.atomic():
            pm = get_object_or_404(SupplierPayment.objects.select_for_update(), pk=pk)
            if pm.status != SPSt.PENDING:
                return Response({"detail": "A payment that has been made can't be deleted."}, status=status.HTTP_409_CONFLICT)
            number = pm.payment_number
            pm.delete()
        audit.record(request, "Deleted scheduled supplier payment", number)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MarkPaymentPaidView(PurchaseView):
    write_module = "supplier_payments"

    def post(self, request, pk):
        errors = {}
        day = parsing.date(request.data, "payment_date", errors, required=False, label="payment date")
        if day and day > periods.today():
            errors["payment_date"] = ["A payment that has been made can't be dated in the future."]
        if errors:
            raise ValidationError(errors)
        pm = services.mark_payment_made(get_object_or_404(SupplierPayment, pk=pk), payment_date=day or periods.today(),
                                        reference=parsing.text(request.data, "transaction_reference", 80), user=request.user)
        audit.record(request, "Recorded supplier payment", pm.payment_number)
        return Response(payment_row(payments_qs().get(pk=pk), True))
