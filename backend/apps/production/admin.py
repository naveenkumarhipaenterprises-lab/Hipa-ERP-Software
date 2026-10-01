from django.contrib import admin

from .models import ProductionBatch, ProductionLine


@admin.register(ProductionLine)
class ProductionLineAdmin(admin.ModelAdmin):
    list_display = ("name", "capacity_kg_per_day", "is_active")
    list_filter = ("is_active",)


@admin.register(ProductionBatch)
class ProductionBatchAdmin(admin.ModelAdmin):
    """Batches are scheduled and moved through stages in the app (completion adds stock)."""

    list_display = ("batch_number", "product", "quantity_kg", "line", "start_date", "due_date", "stage")
    list_filter = ("stage", "line", "product")
    search_fields = ("batch_number", "product__name")
    readonly_fields = [f.name for f in ProductionBatch._meta.fields]

    def has_add_permission(self, request):
        return False
