from django.urls import path

from .views import (
    AddonActivateView,
    AddonStatusView,
    MealEntryCreateView,
    MealEntryDeleteView,
    NutritionLogDetailView,
    NutritionLogListCreateView,
    PersonalRecordsView,
    WorkoutLogDetailView,
    WorkoutLogListCreateView,
)

urlpatterns = [
    # Addon management
    path("addon/status/", AddonStatusView.as_view(), name="tracker-addon-status"),
    path("addon/activate/", AddonActivateView.as_view(), name="tracker-addon-activate"),
    # Exercise logs — records/ must come before <uuid:pk>/
    path(
        "exercise/records/",
        PersonalRecordsView.as_view(),
        name="tracker-personal-records",
    ),
    path("exercise/", WorkoutLogListCreateView.as_view(), name="tracker-workout-list"),
    path(
        "exercise/<uuid:pk>/",
        WorkoutLogDetailView.as_view(),
        name="tracker-workout-detail",
    ),
    # Nutrition logs
    path(
        "nutrition/",
        NutritionLogListCreateView.as_view(),
        name="tracker-nutrition-list",
    ),
    path(
        "nutrition/<uuid:pk>/",
        NutritionLogDetailView.as_view(),
        name="tracker-nutrition-detail",
    ),
    path(
        "nutrition/<uuid:log_pk>/meals/",
        MealEntryCreateView.as_view(),
        name="tracker-meal-create",
    ),
    path(
        "nutrition/<uuid:log_pk>/meals/<uuid:meal_pk>/",
        MealEntryDeleteView.as_view(),
        name="tracker-meal-delete",
    ),
]
