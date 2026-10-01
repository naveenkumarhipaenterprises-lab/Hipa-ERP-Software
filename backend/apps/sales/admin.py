from django.contrib import admin

from .models import SalesOrder, SalesOrderItem


class SalesOrderItemInline(admin.TabularInline):
    model = SalesOrderItem
    extra = 0
    readonly_fields = ("product", "quantity_kg", "unit_price", "amount")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False  # items (and their stock movements) are created through the app


@admin.register(SalesOrder)
class SalesOrderAdmin(admin.ModelAdmin):
    """Orders are created in the app (so stock is deducted). Here staff update delivery status."""

    list_display = ("order_number", "order_date", "customer", "total_amount", "status")
    list_filter = ("status",)
    search_fields = ("order_number", "customer__name")
    readonly_fields = ("order_number", "customer", "order_date", "total_amount", "created_by", "created_at")
    fields = ("order_number", "customer", "order_date", "status", "total_amount", "notes", "created_by", "created_at")
    inlines = [SalesOrderItemInline]

    def has_add_permission(self, request):
        return False

    def get_readonly_fields(self, request, obj=None):
        # Cancelling returns stock, so it is only done from the app's Cancel button
        ro = list(self.readonly_fields)
        if obj and obj.status == SalesOrder.Status.CANCELLED:
            ro.append("status")
        return ro

    def formfield_for_choice_field(self, db_field, request, **kwargs):
        if db_field.name == "status":
            kwargs["choices"] = [c for c in SalesOrder.Status.choices if c[0] != SalesOrder.Status.CANCELLED]
        return super().formfield_for_choice_field(db_field, request, **kwargs)
