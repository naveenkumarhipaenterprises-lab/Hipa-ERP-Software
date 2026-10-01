from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from apps.core.numbering import save_with_number
from apps.customers.models import Customer
from apps.inventory.models import Product


class SalesOrder(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        IN_TRANSIT = "in_transit", "In Transit"
        DELIVERED = "delivered", "Delivered"
        CANCELLED = "cancelled", "Cancelled"

    CANCELLABLE = (Status.PENDING, Status.PROCESSING)

    order_number = models.CharField(max_length=20, unique=True, editable=False)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="orders")
    order_date = models.DateField(db_index=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING, db_index=True)
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"), editable=False)
    notes = models.CharField(max_length=500, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-order_date", "-id"]

    def __str__(self):
        return self.order_number or f"Order {self.pk}"

    def save(self, *args, **kwargs):
        if not self.order_number:
            return save_with_number(self, "order_number", "SO", self.order_date, super().save, args, kwargs)
        super().save(*args, **kwargs)

    def recalculate_total(self):
        self.total_amount = sum((i.amount for i in self.items.all()), Decimal("0"))
        self.save(update_fields=["total_amount", "updated_at"])


class SalesOrderItem(models.Model):
    order = models.ForeignKey(SalesOrder, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="order_items")
    quantity_kg = models.DecimalField(max_digits=12, decimal_places=3, validators=[MinValueValidator(Decimal("0.001"))])
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0"))])
    amount = models.DecimalField(max_digits=14, decimal_places=2, editable=False)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity_kg__gt=0), name="order_item_quantity_positive"),
            models.UniqueConstraint(fields=["order", "product"], name="unique_product_per_order"),
        ]

    def save(self, *args, **kwargs):
        self.amount = (self.quantity_kg * self.unit_price).quantize(Decimal("0.01"))
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product} × {self.quantity_kg} kg"
