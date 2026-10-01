from django.contrib import admin

from .models import Report


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("created_at", "name", "type", "format", "status", "created_by")
    list_filter = ("type", "format", "status")
    readonly_fields = [f.name for f in Report._meta.fields]

    def has_add_permission(self, request):
        return False
