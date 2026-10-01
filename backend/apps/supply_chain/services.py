from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from rest_framework.exceptions import ValidationError

from apps.core.periods import today

from .models import MaterialMovement, PurchaseOrder, RawMaterial, Shipment


@transaction.atomic
def move_material(material, type, quantity_kg, *, date=None, reference="", note="", user=None):
    quantity_kg = Decimal(str(quantity_kg))
    locked = RawMaterial.objects.select_for_update().get(pk=material.pk)
    if type == MaterialMovement.Type.OUT:
        if quantity_kg > locked.stock_kg:
            raise ValidationError({"quantity_kg": [f"Only {locked.stock_kg.normalize():f} kg of {locked.name} is in stock."]})
        locked.stock_kg -= quantity_kg
    else:
        locked.stock_kg += quantity_kg
    locked.save(update_fields=["stock_kg"])
    material.stock_kg = locked.stock_kg
    return MaterialMovement.objects.create(material=locked, type=type, quantity_kg=quantity_kg, date=date or today(),
                                           reference=reference[:50], note=note[:255], created_by=user)


@transaction.atomic
def record_delivery(shipment, user=None):
    """Called when a shipment is marked delivered: adds its material to stock once and closes the PO."""
    shipment = Shipment.objects.select_for_update().get(pk=shipment.pk)
    if shipment.status != Shipment.Status.DELIVERED or shipment.stock_recorded:
        return
    if not shipment.delivered_on:
        shipment.delivered_on = today()
    move_material(shipment.material, MaterialMovement.Type.IN, shipment.quantity_kg, date=shipment.delivered_on,
                  reference=shipment.shipment_number, note=f"Delivered by {shipment.supplier.name}", user=user)
    shipment.stock_recorded = True
    shipment.save(update_fields=["delivered_on", "stock_recorded"])
    po = shipment.purchase_order
    if po and po.status in PurchaseOrder.OPEN:
        delivered = po.shipments.filter(status=Shipment.Status.DELIVERED).aggregate(q=Sum("quantity_kg"))["q"] or 0
        if delivered >= po.quantity_kg:
            po.status = PurchaseOrder.Status.RECEIVED
            po.save(update_fields=["status"])


def monthly_usage(material, days=30):
    since = today() - timedelta(days=days)
    return material.movements.filter(type=MaterialMovement.Type.OUT, date__gt=since).aggregate(q=Sum("quantity_kg"))["q"] or Decimal("0")
