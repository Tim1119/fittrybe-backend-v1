from django.urls import path

from apps.profiles.views import ExpertiseListView, GoalListView

urlpatterns = [
    path("", ExpertiseListView.as_view(), name="expertise-list"),
    path("goals/", GoalListView.as_view(), name="goals-list"),
]
