from django.urls import path

from . import views

urlpatterns = [
    path("overview/", views.OverviewView.as_view()),
    path("trend/", views.TrendView.as_view()),
    path("options/", views.OptionsView.as_view()),
    path("suppliers/", views.SuppliersView.as_view()),
    path("suppliers/<int:pk>/", views.SupplierDetailView.as_view()),
    path("raw-materials/", views.MaterialsView.as_view()),
    path("raw-materials/<int:pk>/", views.MaterialDetailView.as_view()),
    path("material-movements/", views.MaterialMovementsView.as_view()),
    path("purchases/", views.PurchasesView.as_view()),
    path("purchases/<int:pk>/", views.PurchaseDetailView.as_view()),
    path("purchases/<int:pk>/cancel/", views.CancelPurchaseView.as_view()),
    path("goods-receipts/", views.GoodsReceiptsView.as_view()),
    path("goods-receipts/<int:pk>/", views.GoodsReceiptDetailView.as_view()),
    path("returns/", views.ReturnsView.as_view()),
    path("returns/<int:pk>/", views.ReturnDetailView.as_view()),
    path("payments/", views.PaymentsView.as_view()),
    path("payments/<int:pk>/", views.PaymentDetailView.as_view()),
    path("payments/<int:pk>/mark-paid/", views.MarkPaymentPaidView.as_view()),
]
