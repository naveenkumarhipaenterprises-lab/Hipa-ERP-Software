from django.contrib import admin

from .models import Product, StockMovement


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "stock_kg", "min_stock_kg", "reorder_level_kg", "price_per_kg", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("name",)
    readonly_fields = ("stock_kg",)  # changes only through stock movements


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    """Read-only: movements are recorded through the app so product stock stays in step."""

    list_display = ("created_at", "product", "type", "quantity_kg", "source", "reference", "created_by")
    list_filter = ("type", "source", "product")
    search_fields = ("product__name", "reference", "note")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
