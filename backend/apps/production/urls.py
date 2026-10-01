from django.urls import path

from . import views

urlpatterns = [
    path("plan/", views.PlanView.as_view()),
    path("plan/export/", views.PlanExportView.as_view()),
    path("options/", views.OptionsView.as_view()),
    path("batches/", views.BatchesView.as_view()),
    path("batches/<int:pk>/", views.BatchDetailView.as_view()),
]
