from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.core import periods
from apps.core.files import csv_response
from apps.core.metrics import choices, num
from apps.core.roles import can_write
from apps.core.views import ModuleAPIView
from apps.inventory.models import Product, StockMovement
from apps.inventory.services import move_stock
from apps.core.exceptions import load_analytics
from services import audit, notifications

from .models import ProductionBatch, ProductionLine

Stage = ProductionBatch.Stage
HORIZONS = ["30", "15", "7"]


def build_plan(horizon):
    return load_analytics("ml.planning", "build_plan")(horizon)


def batch_row(b, editable):
    return {
        "id": b.id,
        "batch_number": b.batch_number,
        "product": b.product.name,
        "quantity_kg": num(b.quantity_kg),
        "start_date": b.start_date,
        "due_date": b.due_date,
        "line": b.line.name,
        "stage": b.stage,
        "can_update": editable and b.stage != Stage.COMPLETED,
    }


class ProductionView(ModuleAPIView):
    module = "production"


class PlanView(ProductionView):
    def get(self, request):
        horizon = int(periods.parse_choice(self.param("horizon"), HORIZONS, "horizon", "30"))
        return Response(build_plan(horizon))


class PlanExportView(ProductionView):
    def get(self, request):
        horizon = int(periods.parse_choice(self.param("horizon"), HORIZONS, "horizon", "30"))
        plan = build_plan(horizon)
        header = ["Product", "Stock (kg)", "Forecast (kg)", "Safety stock (kg)", "Required (kg)", "Capacity (kg)", "Recommended (kg)", "Priority"]
        rows = ([r["product"], r["stock_kg"], r["forecast_kg"], r["safety_stock_kg"], r["required_kg"], r["capacity_kg"],
                 r["recommended_kg"], r["priority"]] for r in plan["rows"])
        return csv_response(f"hipa-production-plan-{horizon}d-{periods.today():%Y%m%d}.csv", header, rows)


class OptionsView(ProductionView):
    def get(self, request):
        return Response({
            "products": list(Product.objects.filter(is_active=True).values("id", "name")),
            "lines": list(ProductionLine.objects.filter(is_active=True).values("id", "name")),
            "stages": choices(Stage),
        })


def positive_kg(value, field):
    try:
        qty = Decimal(str(value))
        if qty <= 0 or qty.as_tuple().exponent < -3:
            raise InvalidOperation
        return qty
    except (InvalidOperation, ValueError, TypeError):
        raise ValidationError({field: ["Enter a quantity greater than 0 (up to 3 decimals)."]})


class BatchesView(ProductionView):
    def get(self, request):
        qs = ProductionBatch.objects.select_related("product", "line")
        stage = self.param("stage")
        if stage:
            if stage not in Stage.values:
                raise ValidationError({"stage": ["Unknown stage."]})
            qs = qs.filter(stage=stage)
        q = self.param("search")
        if q:
            qs = qs.filter(batch_number__icontains=q) | qs.filter(product__name__icontains=q)
        editable = can_write(request.user, "production")
        return self.paginated(qs.order_by("-start_date", "-id"), lambda b: batch_row(b, editable))

    def post(self, request):
        d = request.data
        errors = {}
        product = Product.objects.filter(pk=d.get("product_id"), is_active=True).first() if str(d.get("product_id", "")).isdigit() else None
        if not product:
            errors["product_id"] = ["Choose a product."]
        line = ProductionLine.objects.filter(pk=d.get("line_id"), is_active=True).first() if str(d.get("line_id", "")).isdigit() else None
        if not line:
            errors["line_id"] = ["Choose an active production line."]
        start = parse_date(str(d.get("start_date") or ""))
        due = parse_date(str(d.get("due_date") or ""))
        if not start:
            errors["start_date"] = ["Enter the start date (YYYY-MM-DD)."]
        if not due:
            errors["due_date"] = ["Enter the due date (YYYY-MM-DD)."]
        elif start and due < start:
            errors["due_date"] = ["The due date can't be before the start date."]
        try:
            qty = positive_kg(d.get("quantity_kg"), "quantity_kg")
        except ValidationError as exc:
            errors.update(exc.detail)
        if errors:
            raise ValidationError(errors)
        batch = ProductionBatch.objects.create(product=product, line=line, quantity_kg=qty, start_date=start,
                                               due_date=due, created_by=request.user)
        audit.record(request, "Scheduled production batch", batch.batch_number)
        notifications.notify("production_updates", f"Batch {batch.batch_number} scheduled",
                             f"{qty.normalize():f} kg {product.name} on {line.name}, due {due:%d %b %Y}", link="/production")
        return Response(batch_row(batch, True), status=status.HTTP_201_CREATED)


class BatchDetailView(ProductionView):
    def patch(self, request, pk):
        stage = request.data.get("stage")
        if stage not in Stage.values:
            raise ValidationError({"stage": ["Choose a valid stage."]})
        with transaction.atomic():
            batch = get_object_or_404(ProductionBatch.objects.select_for_update().select_related("product", "line"), pk=pk)
            if batch.stage == Stage.COMPLETED:
                raise ValidationError({"stage": ["This batch is already completed."]})
            batch.stage = stage
            if stage == Stage.COMPLETED:
                batch.completed_at = timezone.now()
                if not batch.stock_recorded:
                    move_stock(batch.product, "in", batch.quantity_kg, source=StockMovement.Source.PRODUCTION,
                               reference=batch.batch_number, user=request.user)
                    batch.stock_recorded = True
            batch.save()
        audit.record(request, f"Moved batch to {Stage(stage).label}", batch.batch_number)
        if stage == Stage.COMPLETED:
            notifications.notify("production_updates", f"Batch {batch.batch_number} completed",
                                 f"{batch.quantity_kg.normalize():f} kg {batch.product.name} added to stock", type="success", link="/production")
        return Response(batch_row(batch, True))
