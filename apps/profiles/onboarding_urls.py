from django.urls import path

from apps.profiles import onboarding_views

urlpatterns = [
    # Trainer
    path(
        "trainer/expertise/",
        onboarding_views.TrainerExpertiseView.as_view(),
        name="trainer-expertise",
    ),
    path(
        "trainer/products/",
        onboarding_views.TrainerProductsView.as_view(),
        name="trainer-products",
    ),
    # Gym
    path(
        "gym/services/", onboarding_views.GymServicesView.as_view(), name="gym-services"
    ),
    path(
        "gym/products/", onboarding_views.GymProductsView.as_view(), name="gym-products"
    ),
    # Client
    path("client/goal/", onboarding_views.ClientGoalView.as_view(), name="client-goal"),
    path(
        "client/goal/<int:goal_id>/",
        onboarding_views.ClientGoalDetailView.as_view(),
        name="client-goal-detail",
    ),
    path(
        "client/focus/", onboarding_views.ClientFocusView.as_view(), name="client-focus"
    ),
    path(
        "client/focus/<int:specialisation_id>/",
        onboarding_views.ClientFocusDetailView.as_view(),
        name="client-focus-detail",
    ),
]
