from django.urls import path

from . import views

urlpatterns = [
    path("summary/", views.SummaryView.as_view()),
    path("sales-trend/", views.SalesTrendView.as_view()),
]
