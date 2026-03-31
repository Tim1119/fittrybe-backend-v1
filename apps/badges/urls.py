from django.urls import path

from apps.badges.views import (
    BadgeAssignmentListView,
    BadgeAssignView,
    BadgeDetailView,
    BadgeLeaderboardView,
    BadgeListCreateView,
    ClientBadgeListView,
    WeeklyRecognitionPostView,
)

urlpatterns = [
    path("", BadgeListCreateView.as_view()),
    path("leaderboard/", BadgeLeaderboardView.as_view()),
    path("assignments/", BadgeAssignmentListView.as_view()),
    path("recognition-post/", WeeklyRecognitionPostView.as_view()),
    path("<int:pk>/", BadgeDetailView.as_view()),
    path("clients/<int:client_id>/assign/", BadgeAssignView.as_view()),
    path("clients/<int:client_id>/", ClientBadgeListView.as_view()),
]
