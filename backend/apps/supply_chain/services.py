from datetime import timedelta

from django.db.models import Sum

from apps.core.periods import today
from apps.purchase.models import MaterialMovement

from .models import Shipment


def record_delivery(shipment):
    """Called when a shipment is marked delivered: stamps the delivery date. Stock comes in through the goods receipt."""
    if shipment.status == Shipment.Status.DELIVERED and not shipment.delivered_on:
        shipment.delivered_on = today()
        shipment.save(update_fields=["delivered_on"])


def monthly_usage_by_material(days=30):
    """{material_id: quantity used in the last `days`} for every material, in one query."""
    since = today() - timedelta(days=days)
    return dict(MaterialMovement.objects.filter(type=MaterialMovement.Type.OUT, source=MaterialMovement.Source.USAGE, date__gt=since)
                .values("material_id").annotate(q=Sum("quantity")).order_by().values_list("material_id", "q"))
