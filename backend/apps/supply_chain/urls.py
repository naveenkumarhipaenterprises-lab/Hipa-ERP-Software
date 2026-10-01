from django.urls import path

from . import views

urlpatterns = [
    path("overview/", views.OverviewView.as_view()),
    path("supplier-performance/", views.SupplierPerformanceView.as_view()),
    path("options/", views.OptionsView.as_view()),
    path("shipments/", views.ShipmentsView.as_view()),
    path("suppliers/", views.SuppliersView.as_view()),
    path("purchase-orders/", views.PurchaseOrdersView.as_view()),
]
