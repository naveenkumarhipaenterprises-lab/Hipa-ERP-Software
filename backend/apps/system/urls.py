from django.urls import path

from . import views

settings_urls = [
    path("options/", views.OptionsView.as_view()),
    path("general/", views.GeneralSettingsView.as_view()),
    path("company/", views.CompanySettingsView.as_view()),
    path("billing/", views.BillingSettingsView.as_view()),
    path("users/", views.UsersView.as_view()),
    path("users/<int:pk>/", views.UserDetailView.as_view()),
    path("users/<int:pk>/password/", views.UserPasswordView.as_view()),
    path("notifications/", views.NotificationPreferencesView.as_view()),
    path("backup/", views.BackupView.as_view()),
    path("backup/run/", views.RunBackupView.as_view()),
    path("integrations/", views.IntegrationsView.as_view()),
    path("integrations/<slug:key>/<str:action>/", views.IntegrationActionView.as_view()),
    path("security/", views.SecurityView.as_view()),
    path("security/login-activity/", views.LoginActivityView.as_view()),
    path("audit-logs/", views.AuditLogsView.as_view()),
]

notification_urls = [
    path("", views.NotificationsView.as_view()),
    path("<int:pk>/read/", views.NotificationReadView.as_view()),
    path("mark-all-read/", views.NotificationsReadAllView.as_view()),
]
