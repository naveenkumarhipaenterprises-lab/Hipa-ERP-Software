from django.urls import path

from . import views

# Suppliers and purchases are managed in the Purchase module (/api/v1/purchase/)
urlpatterns = [
    path("overview/", views.OverviewView.as_view()),
    path("supplier-performance/", views.SupplierPerformanceView.as_view()),
    path("options/", views.OptionsView.as_view()),
    path("shipments/", views.ShipmentsView.as_view()),
    path("shipments/<int:pk>/", views.ShipmentDetailView.as_view()),
    path("shipments/<int:pk>/status/", views.ShipmentStatusView.as_view()),
    path("shipments/<int:pk>/purchase/", views.ShipmentPurchaseView.as_view()),
    # Customer deliveries: keyed by the sales order id
    path("customer-deliveries/", views.CustomerDeliveriesView.as_view()),
    path("customer-deliveries/<int:pk>/", views.CustomerDeliveryDetailView.as_view()),
    path("customer-deliveries/<int:pk>/dispatch/", views.CustomerDeliveryDispatchView.as_view()),
    path("customer-deliveries/<int:pk>/confirm/", views.CustomerDeliveryConfirmView.as_view()),
]
