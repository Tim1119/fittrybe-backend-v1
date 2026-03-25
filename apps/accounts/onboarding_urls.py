from django.urls import path

from . import views

urlpatterns = [
    path("step/", views.OnboardingStepView.as_view(), name="onboarding-step"),
    path(
        "complete/",
        views.OnboardingCompleteView.as_view(),
        name="onboarding-complete-v2",
    ),
]
