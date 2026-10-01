from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models

from apps.core.numbering import save_with_number as _numbered
from apps.inventory.models import Product
from apps.purchase.models import Purchase, RawMaterial, Supplier, Unit


class Shipment(models.Model):
    """
    Inbound delivery from a supplier, tracked for logistics (dispatch, ETA, delays). Stock is
    added by the goods receipt in Purchase, not by the shipment.
    """

    class Status(models.TextChoices):
        IN_TRANSIT = "in_transit", "In Transit"
        DELAYED = "delayed", "Delayed"
        DELIVERED = "delivered", "Delivered"

    shipment_number = models.CharField(max_length=20, unique=True, editable=False)
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="shipments")
    purchase = models.ForeignKey(Purchase, null=True, blank=True, on_delete=models.SET_NULL, related_name="shipments")
    material = models.ForeignKey(RawMaterial, null=True, blank=True, on_delete=models.PROTECT, related_name="shipments")
    product = models.ForeignKey(Product, null=True, blank=True, on_delete=models.PROTECT, related_name="shipments")
    quantity = models.DecimalField(max_digits=12, decimal_places=3, validators=[MinValueValidator(Decimal("0.001"))])
    unit = models.CharField(max_length=4, choices=Unit.choices, default=Unit.KG)
    destination = models.CharField(max_length=120)
    dispatched_on = models.DateField()
    eta = models.DateField()
    delivered_on = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.IN_TRANSIT, db_index=True)
    quality_passed = models.BooleanField(null=True, blank=True, help_text="Inward quality check result, if done")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-dispatched_on", "-id"]
        constraints = [
            models.CheckConstraint(condition=models.Q(material__isnull=False, product__isnull=True) |
                                   models.Q(material__isnull=True, product__isnull=False), name="shipment_one_item"),
        ]

    def __str__(self):
        return self.shipment_number or f"Shipment {self.pk}"

    @property
    def item(self):
        return self.material or self.product

    @property
    def on_time(self):
        return self.delivered_on <= self.eta if self.delivered_on else None

    def save(self, *args, **kwargs):
        if not self.shipment_number:
            return _numbered(self, "shipment_number", "SH", self.dispatched_on, super().save, args, kwargs)
        super().save(*args, **kwargs)
