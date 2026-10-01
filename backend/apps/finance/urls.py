from django.urls import path

from . import views

urlpatterns = [
    path("overview/", views.OverviewView.as_view()),
    path("revenue-expenses/", views.RevenueExpensesView.as_view()),
    path("cash-flow/", views.CashFlowView.as_view()),
    path("options/", views.OptionsView.as_view()),
    path("transactions/", views.TransactionsView.as_view()),
    path("budget/", views.BudgetView.as_view()),
]
