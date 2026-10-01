from django.contrib import admin

from services import notifications

from .models import Shipment
from .services import record_delivery


@admin.register(Shipment)
class ShipmentAdmin(admin.ModelAdmin):
    """Inbound shipments. Received goods are booked into stock with a goods receipt in Purchase."""

    list_display = ("shipment_number", "supplier", "purchase", "material", "product", "quantity", "unit", "eta", "status",
                    "delivered_on", "quality_passed")
    list_filter = ("status", "supplier")
    search_fields = ("shipment_number", "supplier__name", "destination", "purchase__purchase_number")
    readonly_fields = ("shipment_number", "created_at")

    def save_model(self, request, obj, form, change):
        was_delayed = change and form.initial.get("status") == Shipment.Status.DELAYED
        super().save_model(request, obj, form, change)
        if obj.status == Shipment.Status.DELIVERED:
            record_delivery(obj)
        elif obj.status == Shipment.Status.DELAYED and not was_delayed:
            notifications.notify("shipment_delays", f"Shipment {obj.shipment_number} delayed",
                                 f"{obj.supplier.name}, was expected {obj.eta:%d %b %Y}", type="error", link="/supply-chain")
