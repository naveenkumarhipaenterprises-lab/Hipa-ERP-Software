from django.urls import path

from . import views

urlpatterns = [
    path("status/", views.StatusView.as_view()),
    path("check-in/", views.CheckInView.as_view()),
    path("check-out/", views.CheckOutView.as_view()),
    path("history/", views.HistoryView.as_view()),
    path("records/", views.RecordsView.as_view()),
    path("options/", views.OptionsView.as_view()),
    path("employees/", views.EmployeesView.as_view()),
    path("employees/<int:pk>/", views.EmployeeDetailView.as_view()),
    path("leave/", views.LeaveView.as_view()),
    path("leave/<int:pk>/", views.LeaveDetailView.as_view()),
    path("leave/<int:pk>/<str:action>/", views.LeaveActionView.as_view()),
    path("calendar/", views.CalendarView.as_view()),
    path("reports/", views.ReportView.as_view()),
    path("settings/", views.SettingsView.as_view()),
]
