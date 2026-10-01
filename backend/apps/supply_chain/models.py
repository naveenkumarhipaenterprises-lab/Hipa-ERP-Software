from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from apps.core.numbering import save_with_number as _numbered
from apps.customers.models import phone_validator

ZERO = Decimal("0")


class Supplier(models.Model):
    name = models.CharField(max_length=150, unique=True)
    city = models.CharField(max_length=80)
    contact_person = models.CharField(max_length=120, blank=True)
    phone = models.CharField(max_length=20, blank=True, validators=[phone_validator])
    email = models.EmailField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class RawMaterial(models.Model):
    """Raw spices and packing material. Stock is the running total of MaterialMovements."""

    name = models.CharField(max_length=120, unique=True)
    stock_kg = models.DecimalField(max_digits=12, decimal_places=3, default=ZERO, editable=False)
    reorder_level_kg = models.DecimalField(max_digits=12, decimal_places=3, default=ZERO, validators=[MinValueValidator(ZERO)])
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        constraints = [models.CheckConstraint(condition=models.Q(stock_kg__gte=0), name="material_stock_not_negative")]

    def __str__(self):
        return self.name


class MaterialMovement(models.Model):
    class Type(models.TextChoices):
        IN = "in", "Received"
        OUT = "out", "Used"

    material = models.ForeignKey(RawMaterial, on_delete=models.PROTECT, related_name="movements")
    type = models.CharField(max_length=3, choices=Type.choices)
    quantity_kg = models.DecimalField(max_digits=12, decimal_places=3, validators=[MinValueValidator(Decimal("0.001"))])
    date = models.DateField(db_index=True)
    reference = models.CharField(max_length=50, blank=True)
    note = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-id"]
        constraints = [models.CheckConstraint(condition=models.Q(quantity_kg__gt=0), name="material_movement_positive")]

    def __str__(self):
        return f"{self.get_type_display()} {self.quantity_kg} kg {self.material}"


class PurchaseOrder(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        RECEIVED = "received", "Received"
        CANCELLED = "cancelled", "Cancelled"

    OPEN = (Status.PENDING, Status.APPROVED)

    po_number = models.CharField(max_length=20, unique=True, editable=False)
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="purchase_orders")
    material = models.ForeignKey(RawMaterial, on_delete=models.PROTECT, related_name="purchase_orders")
    quantity_kg = models.DecimalField(max_digits=12, decimal_places=3, validators=[MinValueValidator(Decimal("0.001"))])
    rate_per_kg = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(ZERO)])
    order_date = models.DateField(db_index=True)
    expected_delivery = models.DateField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)
    notes = models.CharField(max_length=500, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-order_date", "-id"]
        constraints = [
            models.CheckConstraint(condition=models.Q(expected_delivery__gte=models.F("order_date")), name="po_delivery_after_order"),
        ]

    def __str__(self):
        return self.po_number or f"PO {self.pk}"

    @property
    def amount(self):
        return self.quantity_kg * self.rate_per_kg if self.rate_per_kg is not None else None

    def save(self, *args, **kwargs):
        if not self.po_number:
            return _numbered(self, "po_number", "PO", self.order_date, super().save, args, kwargs)
        super().save(*args, **kwargs)


class Shipment(models.Model):
    """Inbound delivery from a supplier. Marking it delivered adds the material to stock once."""

    class Status(models.TextChoices):
        IN_TRANSIT = "in_transit", "In Transit"
        DELAYED = "delayed", "Delayed"
        DELIVERED = "delivered", "Delivered"

    shipment_number = models.CharField(max_length=20, unique=True, editable=False)
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="shipments")
    purchase_order = models.ForeignKey(PurchaseOrder, null=True, blank=True, on_delete=models.SET_NULL, related_name="shipments")
    material = models.ForeignKey(RawMaterial, on_delete=models.PROTECT, related_name="shipments")
    quantity_kg = models.DecimalField(max_digits=12, decimal_places=3, validators=[MinValueValidator(Decimal("0.001"))])
    destination = models.CharField(max_length=120)
    dispatched_on = models.DateField()
    eta = models.DateField()
    delivered_on = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.IN_TRANSIT, db_index=True)
    quality_passed = models.BooleanField(null=True, blank=True, help_text="Inward quality check result, if done")
    stock_recorded = models.BooleanField(default=False, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-dispatched_on", "-id"]

    def __str__(self):
        return self.shipment_number or f"Shipment {self.pk}"

    @property
    def on_time(self):
        return self.delivered_on <= self.eta if self.delivered_on else None

    def save(self, *args, **kwargs):
        if not self.shipment_number:
            return _numbered(self, "shipment_number", "SH", self.dispatched_on, super().save, args, kwargs)
        super().save(*args, **kwargs)
