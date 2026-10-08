"""HIPA MASALA API. Every endpoint lives under /api/v1/; the Django admin is at /admin/."""
from django.contrib import admin
from django.urls import include, path

from apps.accounts.admin_login import throttle_failed_logins
from apps.system.urls import notification_urls, settings_urls

admin.site.site_header = "HIPA MASALA administration"
admin.site.site_title = "HIPA MASALA admin"
admin.site.login = throttle_failed_logins(admin.site.login)

api_v1 = [
    path("auth/", include("apps.accounts.urls")),
    path("dashboard/", include("apps.dashboard.urls")),
    path("sales/", include("apps.sales.urls")),
    path("inventory/", include("apps.inventory.urls")),
    path("purchase/", include("apps.purchase.urls")),
    path("marketing/", include("apps.marketing.urls")),
    path("customers/", include("apps.customers.urls")),
    path("supply-chain/", include("apps.supply_chain.urls")),
    path("quality/", include("apps.quality.urls")),
    path("attendance/", include("apps.attendance.urls")),
    path("ai/", include("apps.ai_assistant.urls")),
    path("reports/", include("apps.reports.urls")),
    path("settings/", include(settings_urls)),
    path("notifications/", include(notification_urls)),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include(api_v1)),
]
