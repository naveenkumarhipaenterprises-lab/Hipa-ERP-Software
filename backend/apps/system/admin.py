from django.contrib import admin

from .models import AuditLog, BackupRun, BackupSettings, CompanySettings, Notification, NotificationPreference


@admin.register(CompanySettings, BackupSettings)
class SingletonAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return not self.model.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ("key", "enabled", "updated_at")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "title", "type", "read")
    list_filter = ("type", "read", "key")
    search_fields = ("title", "message", "user__email")


class ReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(AuditLog)
class AuditLogAdmin(ReadOnlyAdmin):
    list_display = ("created_at", "user", "action", "target", "ip")
    search_fields = ("action", "target", "user__email")


@admin.register(BackupRun)
class BackupRunAdmin(ReadOnlyAdmin):
    list_display = ("started_at", "status", "file_name", "size_bytes", "triggered_by")
