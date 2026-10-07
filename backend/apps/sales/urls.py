from django.urls import path

from . import document_views as docs
from . import views

urlpatterns = [
    path("overview/", views.OverviewView.as_view()),
    path("trend/", views.TrendView.as_view()),
    path("options/", views.OptionsView.as_view()),
    path("orders/", views.OrdersView.as_view()),
    path("orders/<int:pk>/", views.OrderDetailView.as_view()),
    path("orders/<int:pk>/status/", views.OrderStatusView.as_view()),
    path("orders/<int:pk>/cancel/", views.CancelOrderView.as_view()),
    path("orders/<int:pk>/convert-to-invoice/", views.OrderToInvoiceView.as_view()),
    path("quotations/", docs.QuotationsView.as_view()),
    path("quotations/<int:pk>/", docs.QuotationDetailView.as_view()),
    path("quotations/<int:pk>/status/", docs.QuotationStatusView.as_view()),
    path("quotations/<int:pk>/pdf/", docs.QuotationPDFView.as_view()),
    path("quotations/<int:pk>/convert-to-order/", docs.QuotationToOrderView.as_view()),
    path("quotations/<int:pk>/convert-to-invoice/", docs.QuotationToInvoiceView.as_view()),
    path("invoices/", docs.InvoicesView.as_view()),
    path("invoices/<int:pk>/", docs.InvoiceDetailView.as_view()),
    path("invoices/<int:pk>/cancel/", docs.CancelInvoiceView.as_view()),
    path("invoices/<int:pk>/pdf/", docs.InvoicePDFView.as_view()),
    path("payments/", docs.PaymentsView.as_view()),
    path("payments/<int:pk>/cancel/", docs.CancelPaymentView.as_view()),
    path("returns/", docs.ReturnsView.as_view()),
    path("returns/<int:pk>/", docs.ReturnDetailView.as_view()),
]
