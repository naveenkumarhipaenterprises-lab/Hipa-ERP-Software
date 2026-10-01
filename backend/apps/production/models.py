from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from apps.core.numbering import save_with_number
from apps.inventory.models import Product


class ProductionLine(models.Model):
    name = models.CharField(max_length=80, unique=True)
    capacity_kg_per_day = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0"))])
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class ProductionBatch(models.Model):
    class Stage(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        CLEANING = "cleaning", "Cleaning"
        GRINDING = "grinding", "Grinding"
        PACKAGING = "packaging", "Packaging"
        COMPLETED = "completed", "Completed"
        HOLD = "hold", "Hold"

    OPEN_STAGES = (Stage.SCHEDULED, Stage.CLEANING, Stage.GRINDING, Stage.PACKAGING, Stage.HOLD)

    batch_number = models.CharField(max_length=20, unique=True, editable=False)
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="batches")
    line = models.ForeignKey(ProductionLine, on_delete=models.PROTECT, related_name="batches")
    quantity_kg = models.DecimalField(max_digits=12, decimal_places=3, validators=[MinValueValidator(Decimal("0.001"))])
    start_date = models.DateField(db_index=True)
    due_date = models.DateField()
    stage = models.CharField(max_length=10, choices=Stage.choices, default=Stage.SCHEDULED, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    stock_recorded = models.BooleanField(default=False, editable=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start_date", "-id"]
        verbose_name_plural = "production batches"
        constraints = [
            models.CheckConstraint(condition=models.Q(due_date__gte=models.F("start_date")), name="batch_due_after_start"),
            models.CheckConstraint(condition=models.Q(quantity_kg__gt=0), name="batch_quantity_positive"),
        ]

    def __str__(self):
        return self.batch_number or f"Batch {self.pk}"

    def save(self, *args, **kwargs):
        if not self.batch_number:
            return save_with_number(self, "batch_number", "B", self.start_date, super().save, args, kwargs)
        super().save(*args, **kwargs)
