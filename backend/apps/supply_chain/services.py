from datetime import timedelta
from decimal import Decimal

from django.db.models import Sum

from apps.core.periods import today
from apps.purchase.models import MaterialMovement

from .models import Shipment


def record_delivery(shipment):
    """Called when a shipment is marked delivered: stamps the delivery date. Stock comes in through the goods receipt."""
    if shipment.status == Shipment.Status.DELIVERED and not shipment.delivered_on:
        shipment.delivered_on = today()
        shipment.save(update_fields=["delivered_on"])


def monthly_usage(material, days=30):
    since = today() - timedelta(days=days)
    return (material.movements.filter(type=MaterialMovement.Type.OUT, source=MaterialMovement.Source.USAGE, date__gt=since)
            .aggregate(q=Sum("quantity"))["q"] or Decimal("0"))
