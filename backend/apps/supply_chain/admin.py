from django import forms
from django.contrib import admin, messages
from rest_framework.exceptions import ValidationError

from services import notifications

from .models import MaterialMovement, PurchaseOrder, RawMaterial, Shipment, Supplier
from .services import move_material, record_delivery


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ("name", "city", "contact_person", "phone", "is_active")
    list_filter = ("is_active", "city")
    search_fields = ("name", "city", "contact_person")


@admin.register(RawMaterial)
class RawMaterialAdmin(admin.ModelAdmin):
    list_display = ("name", "stock_kg", "reorder_level_kg", "is_active")
    readonly_fields = ("stock_kg",)
    search_fields = ("name",)


class MaterialMovementForm(forms.ModelForm):
    class Meta:
        model = MaterialMovement
        fields = ("material", "type", "quantity_kg", "date", "reference", "note")

    def clean(self):
        data = super().clean()
        material, qty = data.get("material"), data.get("quantity_kg")
        if data.get("type") == MaterialMovement.Type.OUT and material and qty and qty > material.stock_kg:
            raise forms.ValidationError(f"Only {material.stock_kg.normalize():f} kg of {material.name} is in stock.")
        return data


@admin.register(MaterialMovement)
class MaterialMovementAdmin(admin.ModelAdmin):
    """Add movements here to record material used in production or other receipts; stock updates automatically."""

    form = MaterialMovementForm
    list_display = ("date", "material", "type", "quantity_kg", "reference", "created_by")
    list_filter = ("type", "material")
    fields = ("material", "type", "quantity_kg", "date", "reference", "note")

    def has_change_permission(self, request, obj=None):
        return obj is None

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        try:
            move_material(obj.material, obj.type, obj.quantity_kg, date=obj.date, reference=obj.reference,
                          note=obj.note, user=request.user)
        except ValidationError as exc:
            messages.error(request, str(exc.detail.get("quantity_kg", exc.detail)))


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ("po_number", "order_date", "supplier", "material", "quantity_kg", "rate_per_kg", "expected_delivery", "status")
    list_filter = ("status", "supplier")
    search_fields = ("po_number", "supplier__name", "material__name")
    readonly_fields = ("po_number", "created_by", "created_at")


@admin.register(Shipment)
class ShipmentAdmin(admin.ModelAdmin):
    """Marking a shipment Delivered adds its quantity to raw-material stock (once)."""

    list_display = ("shipment_number", "supplier", "material", "quantity_kg", "eta", "status", "delivered_on", "quality_passed")
    list_filter = ("status", "supplier")
    search_fields = ("shipment_number", "supplier__name", "destination")
    readonly_fields = ("shipment_number", "stock_recorded", "created_at")

    def get_readonly_fields(self, request, obj=None):
        ro = list(self.readonly_fields)
        if obj and obj.stock_recorded:
            ro += ["material", "quantity_kg", "status"]
        return ro

    def save_model(self, request, obj, form, change):
        was_delayed = change and form.initial.get("status") == Shipment.Status.DELAYED
        super().save_model(request, obj, form, change)
        if obj.status == Shipment.Status.DELIVERED:
            record_delivery(obj, request.user)
        elif obj.status == Shipment.Status.DELAYED and not was_delayed:
            notifications.notify("shipment_delays", f"Shipment {obj.shipment_number} delayed",
                                 f"{obj.supplier.name}, was expected {obj.eta:%d %b %Y}", type="error", link="/supply-chain")
