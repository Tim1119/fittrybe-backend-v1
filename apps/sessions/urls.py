from django.urls import path

from apps.sessions.views import (
    SessionDetailView,
    SessionListCreateView,
    SessionStatsView,
    UpcomingSessionsView,
)

urlpatterns = [
    path("", SessionListCreateView.as_view()),
    path("upcoming/", UpcomingSessionsView.as_view()),
    path("stats/", SessionStatsView.as_view()),
    path("<int:pk>/", SessionDetailView.as_view()),
]
