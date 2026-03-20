from django.urls import path

from apps.profiles.views import (
    CoverPhotoUploadView,
    MyProfileView,
    ProfilePhotoUploadView,
    ProfileSearchView,
    PublicGymProfileView,
    PublicTrainerProfileView,
    SpecialisationListView,
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
    path("photo/", ProfilePhotoUploadView.as_view(), name="photo-upload"),
    path("cover/", CoverPhotoUploadView.as_view(), name="cover-upload"),
    path("specialisations/", SpecialisationListView.as_view(), name="specialisations"),
    path("search/", ProfileSearchView.as_view(), name="search"),
    path(
        "trainer/<slug:slug>/",
        PublicTrainerProfileView.as_view(),
        name="trainer-public",
    ),
    path("gym/<slug:slug>/", PublicGymProfileView.as_view(), name="gym-public"),
]
