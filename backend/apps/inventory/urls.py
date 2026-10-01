from django.urls import path

from . import views

urlpatterns = [
    path("overview/", views.OverviewView.as_view()),
    path("options/", views.OptionsView.as_view()),
    path("items/", views.ItemsView.as_view()),
    path("items/export/", views.ItemsExportView.as_view()),
    path("items/<int:pk>/", views.ItemDetailView.as_view()),
    path("movements/", views.MovementsView.as_view()),
]
