from django.urls import path

from . import views

urlpatterns = [
    path("overview/", views.OverviewView.as_view()),
    path("performance/", views.PerformanceView.as_view()),
    path("audience/", views.AudienceView.as_view()),
    path("options/", views.OptionsView.as_view()),
    path("campaigns/", views.CampaignsView.as_view()),
    path("campaigns/<int:pk>/end/", views.EndCampaignView.as_view()),
    path("posts/", views.PostsView.as_view()),
    path("posts/<int:pk>/status/", views.PostStatusView.as_view()),
]
