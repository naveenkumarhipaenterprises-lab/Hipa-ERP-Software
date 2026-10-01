from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import LoginActivity, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "name", "email", "role", "is_active", "last_login")
    list_filter = ("role", "is_active", "is_superuser")
    search_fields = ("username", "name", "email")
    ordering = ("name",)
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Profile", {"fields": ("name", "email", "role")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",),
                "fields": ("username", "name", "email", "role", "password1", "password2")}),
    )


@admin.register(LoginActivity)
class LoginActivityAdmin(admin.ModelAdmin):
    list_display = ("created_at", "username_attempted", "user", "success", "ip")
    list_filter = ("success",)
    search_fields = ("username_attempted", "ip")
    readonly_fields = [f.name for f in LoginActivity._meta.fields]

    def has_add_permission(self, request):
        return False
