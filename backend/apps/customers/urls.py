from django.urls import path

from . import views

urlpatterns = [
    path("", views.CustomerListView.as_view()),
    path("<int:pk>/", views.CustomerDetailView.as_view()),
    path("overview/", views.OverviewView.as_view()),
    path("growth/", views.GrowthView.as_view()),
    path("options/", views.OptionsView.as_view()),
    path("export/", views.ExportView.as_view()),
    path("import/template/", views.ImportTemplateView.as_view()),
    path("import/", views.ImportView.as_view()),
    path("offers/", views.OfferView.as_view()),
]
