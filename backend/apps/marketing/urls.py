from django.urls import path

from . import data_views, views

urlpatterns = [
    path("overview/", views.OverviewView.as_view()),
    path("performance/", views.PerformanceView.as_view()),
    path("audience/", views.AudienceView.as_view()),
    path("options/", views.OptionsView.as_view()),
    path("campaigns/", views.CampaignsView.as_view()),
    path("campaigns/<int:pk>/end/", views.EndCampaignView.as_view()),
    path("posts/", views.PostsView.as_view()),
    path("posts/<int:pk>/status/", views.PostStatusView.as_view()),
    # Numbers entered from each platform's analytics (feed the dashboard)
    path("metrics/", data_views.MetricsView.as_view()),
    path("metrics/<int:pk>/", data_views.MetricDetailView.as_view()),
    path("content/", data_views.ContentView.as_view()),
    path("content/<int:pk>/", data_views.ContentDetailView.as_view()),
    path("audience-segments/", data_views.SegmentsView.as_view()),
    path("audience-segments/<int:pk>/", data_views.SegmentDetailView.as_view()),
]
