from django.urls import path

from apps.profiles.views import (
    CoverPhotoUploadView,
    GymReviewListCreateView,
    GymReviewRespondView,
    GymTrainerAcceptView,
    GymTrainerCreateListView,
    GymTrainerDetailView,
    MyProfileView,
    ProfileAvailabilityDetailView,
    ProfileAvailabilityListCreateView,
    ProfileCertificationDetailView,
    ProfileCertificationListCreateView,
    ProfilePhotoUploadView,
    ProfileSearchView,
    ProfileServiceDetailView,
    ProfileServiceListCreateView,
    ProfileSpecialisationDetailView,
    ProfileSpecialisationView,
    ProfileVisibilityView,
    PublicGymProfileView,
    PublicTrainerProfileView,
    SpecialisationListView,
    TrainerReviewListCreateView,
    TrainerReviewRespondView,
    WizardStatusView,
    WizardStep1View,
    WizardStep2View,
    WizardStep3View,
    WizardStep4View,
)

app_name = "profiles"

urlpatterns = [
    path("wizard/step1/", WizardStep1View.as_view(), name="wizard-step1"),
    path("wizard/step2/", WizardStep2View.as_view(), name="wizard-step2"),
    path("wizard/step3/", WizardStep3View.as_view(), name="wizard-step3"),
    path("wizard/step4/publish/", WizardStep4View.as_view(), name="wizard-step4"),
    path("wizard/status/", WizardStatusView.as_view(), name="wizard-status"),
    path("me/", MyProfileView.as_view(), name="my-profile"),
    path("me/visibility/", ProfileVisibilityView.as_view(), name="profile-visibility"),
    # Specialisations
    path(
        "me/specialisations/",
        ProfileSpecialisationView.as_view(),
        name="my-specialisations",
    ),
    path(
        "me/specialisations/<int:specialisation_id>/",
        ProfileSpecialisationDetailView.as_view(),
        name="my-specialisation-detail",
    ),
    # Services
    path(
        "me/services/",
        ProfileServiceListCreateView.as_view(),
        name="my-services",
    ),
    path(
        "me/services/<int:service_id>/",
        ProfileServiceDetailView.as_view(),
        name="my-service-detail",
    ),
    # Certifications
    path(
        "me/certifications/",
        ProfileCertificationListCreateView.as_view(),
        name="my-certifications",
    ),
    path(
        "me/certifications/<int:cert_id>/",
        ProfileCertificationDetailView.as_view(),
        name="my-certification-detail",
    ),
    # Availability
    path(
        "me/availability/",
        ProfileAvailabilityListCreateView.as_view(),
        name="my-availability",
    ),
    path(
        "me/availability/<int:availability_id>/",
        ProfileAvailabilityDetailView.as_view(),
        name="my-availability-detail",
    ),
    path("photo/", ProfilePhotoUploadView.as_view(), name="photo-upload"),
    path("cover/", CoverPhotoUploadView.as_view(), name="cover-upload"),
    path("specialisations/", SpecialisationListView.as_view(), name="specialisations"),
    path("search/", ProfileSearchView.as_view(), name="search"),
    path(
        "trainer/<slug:slug>/",
        PublicTrainerProfileView.as_view(),
        name="trainer-public",
    ),
    # Gym trainer management (must come before gym/<slug:slug>/ to avoid shadowing)
    path(
        "gym/trainers/",
        GymTrainerCreateListView.as_view(),
        name="gym-trainers",
    ),
    path(
        "gym/trainers/<int:pk>/",
        GymTrainerDetailView.as_view(),
        name="gym-trainer-detail",
    ),
    path(
        "gym/trainers/accept/",
        GymTrainerAcceptView.as_view(),
        name="gym-trainer-accept",
    ),
    path("gym/<slug:slug>/", PublicGymProfileView.as_view(), name="gym-public"),
    # Reviews
    path(
        "trainer/<slug:slug>/reviews/",
        TrainerReviewListCreateView.as_view(),
        name="trainer-reviews",
    ),
    path(
        "trainer/<slug:slug>/reviews/<int:review_id>/respond/",
        TrainerReviewRespondView.as_view(),
        name="trainer-review-respond",
    ),
    path(
        "gym/<slug:slug>/reviews/",
        GymReviewListCreateView.as_view(),
        name="gym-reviews",
    ),
    path(
        "gym/<slug:slug>/reviews/<int:review_id>/respond/",
        GymReviewRespondView.as_view(),
        name="gym-review-respond",
    ),
]
