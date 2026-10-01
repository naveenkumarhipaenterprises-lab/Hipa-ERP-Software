from decimal import Decimal, InvalidOperation

from django.db import IntegrityError, transaction
from django.db.models import DecimalField, ExpressionWrapper, F, Q, Sum
from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.ai_assistant import insights
from apps.core import periods
from apps.core.files import csv_response
from apps.core.metrics import kpi, label_choices, num, resolve_choice
from apps.core.views import ModuleAPIView
from services import audit

from .models import Product, StockMovement
from .services import move_stock

S = Product.StockStatus
STATUS_FILTERS = {
    S.OUT: Q(stock_kg__lte=0),
    S.CRITICAL: Q(stock_kg__gt=0, stock_kg__lte=F("min_stock_kg")),
    S.LOW: Q(stock_kg__gt=F("min_stock_kg"), stock_kg__lte=F("reorder_level_kg")),
    S.IN_STOCK: Q(stock_kg__gt=F("reorder_level_kg")),
}
VALUE = ExpressionWrapper(F("stock_kg") * F("price_per_kg"), output_field=DecimalField(max_digits=20, decimal_places=2))


def item_row(p):
    return {
        "id": p.id,
        "product": p.name,
        "stock_kg": num(p.stock_kg),
        "min_stock_kg": num(p.min_stock_kg),
        "reorder_level_kg": num(p.reorder_level_kg),
        "price_per_kg": num(p.price_per_kg),
        "stock_value": num(p.stock_value.quantize(Decimal("0.01"))),
        "status": S(p.stock_status).label,
        "updated_at": p.updated_at,
    }


def movement_row(m):
    note = m.note or (f"{m.get_source_display()} {m.reference}".strip() if m.source != StockMovement.Source.MANUAL else "")
    return {"id": m.id, "type": m.type, "product": m.product.name, "quantity_kg": num(m.quantity_kg),
            "created_at": m.created_at, "note": note or None}


def stock_on(day, products):
    """Total stock at the end of `day`: today's stock minus everything that moved after it."""
    from datetime import datetime, time

    from django.utils import timezone

    after = timezone.make_aware(datetime.combine(day, time.max))
    current = products.aggregate(t=Sum("stock_kg"))["t"] or Decimal("0")
    moved = StockMovement.objects.filter(product__in=products, created_at__gt=after)
    net_in = moved.filter(type="in").aggregate(t=Sum("quantity_kg"))["t"] or Decimal("0")
    net_out = moved.filter(type="out").aggregate(t=Sum("quantity_kg"))["t"] or Decimal("0")
    return current - net_in + net_out


class InventoryView(ModuleAPIView):
    module = "inventory"


class OverviewView(InventoryView):
    def get(self, request):
        cur, prev = periods.resolve(self.param("range"))
        products = Product.objects.filter(is_active=True)
        stock_now = stock_on(cur.end, products) if products.exists() else Decimal("0")
        stock_prev = stock_on(prev.end, products) if products.exists() else Decimal("0")
        low = [p for p in products if p.stock_status != S.IN_STOCK]
        counts = {}
        for p in products:
            counts[S(p.stock_status).label] = counts.get(S(p.stock_status).label, 0) + 1
        moves = (StockMovement.objects.select_related("product")
                 .filter(created_at__range=periods.moments(cur.start, cur.end))[:8])
        return Response({
            "kpis": {
                "total_stock_kg": kpi(stock_now, stock_prev),
                "low_stock_items": kpi(len(low), compare=False),
                "stock_value": kpi(products.aggregate(v=Sum(VALUE))["v"] or 0, compare=False),
                "active_products": kpi(products.count(), compare=False),
            },
            "stock_levels": [{"product": p.name, "stock_kg": num(p.stock_kg)} for p in products],
            "status_counts": [{"status": label, "count": counts[label]} for _v, label in S.choices if label in counts],
            "low_stock": [
                {"id": p.id, "product": p.name, "stock_kg": num(p.stock_kg), "reorder_level_kg": num(p.reorder_level_kg),
                 "severity": "critical" if p.stock_status in (S.CRITICAL, S.OUT) else "low"}
                for p in sorted(low, key=lambda p: p.stock_kg - p.reorder_level_kg)
            ],
            "movements": [movement_row(m) for m in moves],
            "insights": insights.block("inventory"),
        })


class OptionsView(InventoryView):
    def get(self, request):
        return Response({
            "items": [{"id": p.id, "name": p.name, "stock_kg": num(p.stock_kg)} for p in Product.objects.filter(is_active=True)],
            "statuses": label_choices(S),
        })


def filtered_items(params):
    qs = Product.objects.filter(is_active=True)
    q = (params.get("search") or "").strip()
    if q:
        qs = qs.filter(name__icontains=q)
    st = resolve_choice(S, params.get("status"), "status")
    if st:
        qs = qs.filter(STATUS_FILTERS[st])
    return qs.order_by("name")


class CreateItemSerializer(serializers.Serializer):
    product_name = serializers.CharField(max_length=120)
    opening_stock_kg = serializers.DecimalField(max_digits=12, decimal_places=3, min_value=Decimal("0"), default=Decimal("0"))
    price_per_kg = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("0"))
    min_stock_kg = serializers.DecimalField(max_digits=12, decimal_places=3, min_value=Decimal("0"), default=Decimal("0"))
    reorder_level_kg = serializers.DecimalField(max_digits=12, decimal_places=3, min_value=Decimal("0"), default=Decimal("0"))

    def validate_product_name(self, value):
        value = value.strip()
        if Product.objects.filter(name__iexact=value).exists():
            raise serializers.ValidationError(f"{value} already exists.")
        return value

    def validate(self, attrs):
        if attrs["reorder_level_kg"] < attrs["min_stock_kg"]:
            raise serializers.ValidationError({"reorder_level_kg": ["Reorder level can't be below the minimum stock."]})
        return attrs


class ItemsView(InventoryView):
    def get(self, request):
        return self.paginated(filtered_items(request.query_params), item_row)

    def post(self, request):
        ser = CreateItemSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        v = ser.validated_data
        try:
            with transaction.atomic():
                product = Product.objects.create(name=v["product_name"], price_per_kg=v["price_per_kg"],
                                                 min_stock_kg=v["min_stock_kg"], reorder_level_kg=v["reorder_level_kg"])
                if v["opening_stock_kg"] > 0:
                    move_stock(product, "in", v["opening_stock_kg"], source=StockMovement.Source.OPENING, user=request.user)
        except IntegrityError:
            raise ValidationError({"product_name": [f"{v['product_name']} already exists."]})
        audit.record(request, "Added inventory item", product.name)
        product.refresh_from_db()
        return Response(item_row(product), status=status.HTTP_201_CREATED)


class ItemsExportView(InventoryView):
    def get(self, request):
        rows = ([p.name, num(p.stock_kg), num(p.min_stock_kg), num(p.reorder_level_kg), num(p.price_per_kg),
                 num(p.stock_value.quantize(Decimal("0.01"))), S(p.stock_status).label, p.updated_at.date()]
                for p in filtered_items(request.query_params))
        header = ["Product", "Stock (kg)", "Min stock (kg)", "Reorder level (kg)", "Price per kg (INR)", "Stock value (INR)", "Status", "Last updated"]
        return csv_response(f"hipa-inventory-{periods.today():%Y%m%d}.csv", header, rows)


class MovementsView(InventoryView):
    def get(self, request):
        qs = StockMovement.objects.select_related("product")
        item = self.int_param("item")
        if item:
            qs = qs.filter(product_id=item)
        return self.paginated(qs, movement_row)

    def post(self, request):
        errors = {}
        product = Product.objects.filter(pk=request.data.get("item_id"), is_active=True).first() if str(request.data.get("item_id", "")).isdigit() else None
        if not product:
            errors["item_id"] = ["Choose a product."]
        type_ = request.data.get("type")
        if type_ not in ("in", "out"):
            errors["type"] = ["Choose Stock In or Stock Out."]
        try:
            qty = Decimal(str(request.data.get("quantity_kg")))
            if qty <= 0 or qty.as_tuple().exponent < -3:
                raise InvalidOperation
        except (InvalidOperation, ValueError, TypeError):
            errors["quantity_kg"] = ["Enter a quantity greater than 0 (up to 3 decimals)."]
        if errors:
            raise ValidationError(errors)
        note = str(request.data.get("note") or "").strip()[:255]
        movement = move_stock(product, type_, qty, note=note, user=request.user)
        audit.record(request, f"Recorded stock {'in' if type_ == 'in' else 'out'}", f"{product.name} {qty} kg")
        return Response(movement_row(movement), status=status.HTTP_201_CREATED)


class ItemDetailView(InventoryView):
    def get(self, request, pk):
        return Response(item_row(get_object_or_404(Product, pk=pk)))
