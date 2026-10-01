from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

ZERO = Decimal("0")


class Product(models.Model):
    """A finished masala product. Its stock is the running total of its StockMovements."""

    class StockStatus(models.TextChoices):
        IN_STOCK = "in_stock", "In Stock"
        LOW = "low", "Low Stock"
        CRITICAL = "critical", "Critical"
        OUT = "out", "Out of Stock"

    name = models.CharField(max_length=120, unique=True)
    price_per_kg = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(ZERO)])
    min_stock_kg = models.DecimalField(max_digits=12, decimal_places=3, default=ZERO, validators=[MinValueValidator(ZERO)])
    reorder_level_kg = models.DecimalField(max_digits=12, decimal_places=3, default=ZERO, validators=[MinValueValidator(ZERO)])
    stock_kg = models.DecimalField(max_digits=12, decimal_places=3, default=ZERO, editable=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(condition=models.Q(stock_kg__gte=0), name="product_stock_not_negative"),
            models.CheckConstraint(condition=models.Q(reorder_level_kg__gte=models.F("min_stock_kg")), name="reorder_at_or_above_min"),
        ]

    def __str__(self):
        return self.name

    @property
    def stock_status(self):
        if self.stock_kg <= 0:
            return self.StockStatus.OUT
        if self.stock_kg <= self.min_stock_kg:
            return self.StockStatus.CRITICAL
        if self.stock_kg <= self.reorder_level_kg:
            return self.StockStatus.LOW
        return self.StockStatus.IN_STOCK

    @property
    def stock_value(self):
        return self.stock_kg * self.price_per_kg


class StockMovement(models.Model):
    class Type(models.TextChoices):
        IN = "in", "Stock In"
        OUT = "out", "Stock Out"

    class Source(models.TextChoices):
        OPENING = "opening", "Opening stock"
        MANUAL = "manual", "Manual entry"
        SALE = "sale", "Sales order"
        SALE_CANCEL = "sale_cancel", "Cancelled order"
        PURCHASE = "purchase", "Goods receipt"
        PURCHASE_RETURN = "purchase_return", "Purchase return"
        RETURN_CANCEL = "return_cancel", "Cancelled purchase return"

    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="movements")
    type = models.CharField(max_length=3, choices=Type.choices)
    quantity_kg = models.DecimalField(max_digits=12, decimal_places=3, validators=[MinValueValidator(Decimal("0.001"))])
    source = models.CharField(max_length=15, choices=Source.choices, default=Source.MANUAL)
    reference = models.CharField(max_length=50, blank=True)
    note = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [models.CheckConstraint(condition=models.Q(quantity_kg__gt=0), name="movement_quantity_positive")]

    def __str__(self):
        return f"{self.get_type_display()} {self.quantity_kg} kg {self.product}"
