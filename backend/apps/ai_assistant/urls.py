from django.urls import path

from . import views

urlpatterns = [
    path("status/", views.StatusView.as_view()),
    path("home/", views.HomeView.as_view()),
    path("chat/", views.ChatView.as_view()),
    path("conversations/<int:pk>/", views.ConversationView.as_view()),
]
