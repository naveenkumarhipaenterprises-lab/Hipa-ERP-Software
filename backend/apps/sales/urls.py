from django.urls import path

from . import views

urlpatterns = [
    path("overview/", views.OverviewView.as_view()),
    path("trend/", views.TrendView.as_view()),
    path("options/", views.OptionsView.as_view()),
    path("orders/", views.OrdersView.as_view()),
    path("orders/<int:pk>/cancel/", views.CancelOrderView.as_view()),
]
