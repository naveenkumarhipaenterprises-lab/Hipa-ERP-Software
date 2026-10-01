from django.contrib import admin

from .models import GoodsReceipt, MaterialMovement, Purchase, PurchaseReturn, RawMaterial, Supplier, SupplierPayment


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ("supplier_code", "name", "city", "state", "contact_person", "phone", "gstin", "status")
    list_filter = ("status", "state", "city")
    search_fields = ("supplier_code", "name", "company_name", "city", "contact_person", "gstin")
    readonly_fields = ("supplier_code", "created_by", "created_at", "updated_at")


@admin.register(RawMaterial)
class RawMaterialAdmin(admin.ModelAdmin):
    list_display = ("material_code", "name", "category", "unit", "current_stock", "reorder_level", "supplier", "status")
    list_filter = ("category", "status")
    search_fields = ("material_code", "name")
    readonly_fields = ("material_code", "current_stock")


class ReadOnlyAdmin(admin.ModelAdmin):
    """Stock and money records change only through the app, which keeps stock and balances in step."""

    def get_readonly_fields(self, request, obj=None):
        return [f.name for f in self.model._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(MaterialMovement)
class MaterialMovementAdmin(ReadOnlyAdmin):
    list_display = ("date", "material", "type", "source", "quantity", "reference", "created_by")
    list_filter = ("type", "source", "material")


@admin.register(Purchase)
class PurchaseAdmin(ReadOnlyAdmin):
    list_display = ("purchase_number", "purchase_date", "supplier", "material", "product", "quantity", "unit", "total_amount", "status")
    list_filter = ("status", "supplier")
    search_fields = ("purchase_number", "supplier__name", "material__name", "product__name")


@admin.register(GoodsReceipt)
class GoodsReceiptAdmin(ReadOnlyAdmin):
    list_display = ("grn_number", "received_date", "purchase", "received_quantity", "damaged_quantity", "accepted_quantity", "quality_status")
    list_filter = ("quality_status",)
    search_fields = ("grn_number", "purchase__purchase_number")


@admin.register(PurchaseReturn)
class PurchaseReturnAdmin(ReadOnlyAdmin):
    list_display = ("return_number", "return_date", "supplier", "material", "product", "quantity", "amount", "status")
    list_filter = ("status", "reason")
    search_fields = ("return_number", "supplier__name")


@admin.register(SupplierPayment)
class SupplierPaymentAdmin(ReadOnlyAdmin):
    list_display = ("payment_number", "payment_date", "supplier", "purchase", "amount", "payment_method", "status")
    list_filter = ("status", "payment_method")
    search_fields = ("payment_number", "supplier__name", "transaction_reference")
