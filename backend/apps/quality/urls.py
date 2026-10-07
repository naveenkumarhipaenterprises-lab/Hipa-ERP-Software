from django.urls import path

from . import views

urlpatterns = [
    path("overview/", views.OverviewView.as_view()),
    path("trend/", views.TrendView.as_view()),
    path("options/", views.OptionsView.as_view()),
    path("tests/", views.TestsView.as_view()),
    path("standards/", views.StandardsView.as_view()),
    path("audits/", views.AuditsView.as_view()),
    path("audits/<int:pk>/status/", views.AuditStatusView.as_view()),
    path("report/", views.ReportView.as_view()),
]
