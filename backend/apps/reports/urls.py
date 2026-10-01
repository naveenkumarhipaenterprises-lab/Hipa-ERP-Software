from django.urls import path

from . import views

urlpatterns = [
    path("", views.ReportListView.as_view()),
    path("overview/", views.OverviewView.as_view()),
    path("preview/", views.PreviewView.as_view()),
    path("export/", views.ExportView.as_view()),
    path("<int:pk>/download/", views.DownloadView.as_view()),
]
