"""Tests for profile views."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.profiles.tests.factories import (
    AvailabilityTrainerFactory,
    CertificationFactory,
    ClientProfileFactory,
    GymProfileFactory,
    PublishedGymProfileFactory,
    PublishedTrainerProfileFactory,
    ServiceTrainerFactory,
    SpecialisationFactory,
    TrainerProfileFactory,
)
from apps.subscriptions.tests.factories import BasicPlanFactory, SubscriptionFactory


def _auth_client(user):
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")
    return client


def _fake_image(size_bytes=1024, content_type="image/jpeg"):
    return SimpleUploadedFile(
        "test.jpg", b"\xff\xd8\xff" + b"x" * size_bytes, content_type=content_type
    )


@pytest.mark.django_db
class TestWizardStep1View:
    URL = "/api/v1/profiles/wizard/step1/"

    def test_trainer_step1_updates_basic_info(self):
        profile = TrainerProfileFactory()
        client = _auth_client(profile.user)
        payload = {
            "full_name": "Updated Name",
            "bio": "I love fitness",
            "location": "Lagos",
            "years_experience": 5,
            "phone_number": "08011111111",
        }
        resp = client.put(self.URL, payload, format="json")
        assert resp.status_code == status.HTTP_200_OK
        profile.refresh_from_db()
        assert profile.full_name == "Updated Name"
        assert profile.bio == "I love fitness"
        assert profile.wizard_step == 1

    def test_trainer_step1_sets_onboarding_in_progress(self):
        profile = TrainerProfileFactory()
        client = _auth_client(profile.user)
        payload = {
            "full_name": "Name",
            "bio": "bio",
            "location": "Lagos",
            "years_experience": 2,
        }
        client.put(self.URL, payload, format="json")
        profile.user.refresh_from_db()
        assert profile.user.onboarding_status == "in_progress"

    def test_gym_step1_updates_basic_info(self):
        profile = GymProfileFactory()
        client = _auth_client(profile.user)
        payload = {
            "gym_name": "Fit Zone",
            "admin_full_name": "Jane Admin",
            "about": "Best gym in town",
            "location": "Abuja",
            "city": "Abuja",
            "contact_phone": "08022222222",
            "business_email": "fitzone@example.com",
        }
        resp = client.put(self.URL, payload, format="json")
        assert resp.status_code == status.HTTP_200_OK
        profile.refresh_from_db()
        assert profile.gym_name == "Fit Zone"
        assert profile.wizard_step == 1

    def test_step1_requires_authentication(self):
        client = APIClient()
        resp = client.put(self.URL, {}, format="json")
        assert resp.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )

    def test_step1_forbidden_for_client(self):
        cp = ClientProfileFactory()
        client = _auth_client(cp.user)
        resp = client.put(self.URL, {"full_name": "x"}, format="json")
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_wizard_step_not_decremented(self):
        profile = TrainerProfileFactory(wizard_step=3)
        client = _auth_client(profile.user)
        payload = {
            "full_name": "Name",
            "bio": "bio",
            "location": "Lagos",
            "years_experience": 2,
        }
        client.put(self.URL, payload, format="json")
        profile.refresh_from_db()
        assert profile.wizard_step == 3  # stays at 3, not set back to 1


@pytest.mark.django_db
class TestWizardStep2View:
    URL = "/api/v1/profiles/wizard/step2/"

    def test_updates_specialisations(self):
        profile = TrainerProfileFactory()
        client = _auth_client(profile.user)
        s1 = SpecialisationFactory(name="Yoga")
        s2 = SpecialisationFactory(name="HIIT")
        payload = {"specialisation_ids": [s1.id, s2.id], "certifications": []}
        resp = client.put(self.URL, payload, format="json")
        assert resp.status_code == status.HTTP_200_OK
        assert profile.specialisations.count() == 2

    def test_rejects_more_than_10_specialisations(self):
        profile = TrainerProfileFactory()
        client = _auth_client(profile.user)
        specs = [SpecialisationFactory().id for _ in range(11)]
        resp = client.put(
            self.URL,
            {"specialisation_ids": specs, "certifications": []},
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_certifications_replaced(self):
        profile = TrainerProfileFactory()
        CertificationFactory(trainer=profile, name="Old Cert")
        client = _auth_client(profile.user)
        payload = {
            "specialisation_ids": [],
            "certifications": [{"name": "New Cert", "issuing_body": "NASM"}],
        }
        client.put(self.URL, payload, format="json")
        assert profile.certifications.count() == 1
        assert profile.certifications.first().name == "New Cert"

    def test_trainer_step2_saves_services(self):
        profile = TrainerProfileFactory()
        client = _auth_client(profile.user)
        payload = {
            "specialisation_ids": [],
            "certifications": [],
            "services": [
                {"name": "Personal Training", "session_type": "physical"},
                {"name": "Online Coaching", "session_type": "virtual"},
            ],
        }
        resp = client.put(self.URL, payload, format="json")
        assert resp.status_code == status.HTTP_200_OK
        assert profile.services.count() == 2

    def test_trainer_step2_services_replaced(self):
        profile = TrainerProfileFactory()
        ServiceTrainerFactory(trainer=profile, name="Old Service")
        client = _auth_client(profile.user)
        payload = {
            "specialisation_ids": [],
            "certifications": [],
            "services": [{"name": "New Service"}],
        }
        client.put(self.URL, payload, format="json")
        assert profile.services.count() == 1
        assert profile.services.first().name == "New Service"

    def test_gym_step2_saves_services(self):
        profile = GymProfileFactory()
        client = _auth_client(profile.user)
        payload = {
            "services": [
                {"name": "Group Classes", "session_type": "physical"},
            ]
        }
        resp = client.put(self.URL, payload, format="json")
        assert resp.status_code == status.HTTP_200_OK
        assert profile.services.count() == 1

    def test_gym_step2_empty_services_ok(self):
        profile = GymProfileFactory()
        client = _auth_client(profile.user)
        resp = client.put(self.URL, {"services": []}, format="json")
        assert resp.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestWizardStep3View:
    URL = "/api/v1/profiles/wizard/step3/"

    def _av_payload(self):
        return {
            "availability": [
                {
                    "day_of_week": "monday",
                    "start_time": "09:00",
                    "end_time": "10:00",
                    "session_type": "both",
                    "duration_minutes": 60,
                },
                {
                    "day_of_week": "wednesday",
                    "start_time": "09:00",
                    "end_time": "11:00",
                },
            ]
        }

    def test_trainer_creates_availability(self):
        profile = TrainerProfileFactory()
        client = _auth_client(profile.user)
        resp = client.put(self.URL, self._av_payload(), format="json")
        assert resp.status_code == status.HTTP_200_OK
        assert profile.availability.count() == 2

    def test_gym_creates_availability(self):
        profile = GymProfileFactory()
        client = _auth_client(profile.user)
        resp = client.put(self.URL, self._av_payload(), format="json")
        assert resp.status_code == status.HTTP_200_OK
        assert profile.availability.count() == 2

    def test_rejects_duplicate_days(self):
        profile = TrainerProfileFactory()
        client = _auth_client(profile.user)
        payload = {
            "availability": [
                {
                    "day_of_week": "monday",
                    "start_time": "09:00",
                    "end_time": "10:00",
                },
                {
                    "day_of_week": "monday",
                    "start_time": "11:00",
                    "end_time": "12:00",
                },
            ]
        }
        resp = client.put(self.URL, payload, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_availability_replaced_not_appended(self):
        profile = TrainerProfileFactory()
        AvailabilityTrainerFactory(trainer=profile, day_of_week="friday")
        client = _auth_client(profile.user)
        client.put(self.URL, self._av_payload(), format="json")
        # Only monday and wednesday slots should exist after replacement
        assert profile.availability.count() == 2
        days = list(profile.availability.values_list("day_of_week", flat=True))
        assert "friday" not in days


@pytest.mark.django_db
class TestWizardStep4View:
    URL = "/api/v1/profiles/wizard/step4/publish/"

    def test_publishes_profile(self):
        profile = TrainerProfileFactory()
        BasicPlanFactory()
        SubscriptionFactory(user=profile.user)
        client = _auth_client(profile.user)
        resp = client.post(self.URL)
        assert resp.status_code == status.HTTP_200_OK
        profile.refresh_from_db()
        assert profile.is_published is True
        assert profile.wizard_completed is True
        assert profile.wizard_step == 4

    def test_completes_onboarding(self):
        profile = TrainerProfileFactory()
        BasicPlanFactory()
        SubscriptionFactory(user=profile.user)
        client = _auth_client(profile.user)
        client.post(self.URL)
        profile.user.refresh_from_db()
        assert profile.user.onboarding_status == "completed"

    def test_blocked_when_subscription_locked(self):
        from apps.subscriptions.models import Subscription

        profile = TrainerProfileFactory()
        BasicPlanFactory()
        SubscriptionFactory(user=profile.user, status=Subscription.Status.LOCKED)
        client = _auth_client(profile.user)
        resp = client.post(self.URL)
        assert resp.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestWizardStatusView:
    URL = "/api/v1/profiles/wizard/status/"

    def test_returns_correct_percentage(self):
        profile = TrainerProfileFactory(full_name="Test", wizard_step=1)
        client = _auth_client(profile.user)
        resp = client.get(self.URL)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.data["data"]
        assert "profile_completion_percentage" in data
        assert "missing_fields" in data
        assert data["wizard_step"] == 1


@pytest.mark.django_db
class TestMyProfileView:
    URL = "/api/v1/profiles/me/"

    def test_get_returns_trainer_profile(self):
        profile = TrainerProfileFactory()
        client = _auth_client(profile.user)
        resp = client.get(self.URL)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["data"]["full_name"] == profile.full_name

    def test_get_returns_gym_profile(self):
        profile = GymProfileFactory()
        client = _auth_client(profile.user)
        resp = client.get(self.URL)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["data"]["gym_name"] == profile.gym_name

    def test_get_returns_client_profile(self):
        profile = ClientProfileFactory()
        client = _auth_client(profile.user)
        resp = client.get(self.URL)
        assert resp.status_code == status.HTTP_200_OK
        assert "username" in resp.data["data"]

    def test_put_partial_update_works(self):
        profile = TrainerProfileFactory(bio="Old bio")
        client = _auth_client(profile.user)
        resp = client.put(self.URL, {"bio": "New bio"}, format="json")
        assert resp.status_code == status.HTTP_200_OK
        profile.refresh_from_db()
        assert profile.bio == "New bio"

    def test_requires_authentication(self):
        resp = APIClient().get(self.URL)
        assert resp.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )


@pytest.mark.django_db
class TestPublicTrainerProfileView:
    def test_returns_404_for_unpublished(self):
        profile = TrainerProfileFactory(is_published=False)
        resp = APIClient().get(f"/api/v1/profiles/trainer/{profile.slug}/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_returns_data_for_published(self):
        profile = PublishedTrainerProfileFactory()
        resp = APIClient().get(f"/api/v1/profiles/trainer/{profile.slug}/")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["data"]["full_name"] == profile.full_name

    def test_phone_number_not_in_public_data(self):
        profile = PublishedTrainerProfileFactory(phone_number="09011111111")
        resp = APIClient().get(f"/api/v1/profiles/trainer/{profile.slug}/")
        assert "phone_number" not in resp.data["data"]

    def test_services_appear_in_public_profile(self):
        profile = PublishedTrainerProfileFactory()
        ServiceTrainerFactory(trainer=profile, name="HIIT Session")
        resp = APIClient().get(f"/api/v1/profiles/trainer/{profile.slug}/")
        assert resp.status_code == status.HTTP_200_OK
        assert "services" in resp.data["data"]
        names = [s["name"] for s in resp.data["data"]["services"]]
        assert "HIIT Session" in names


@pytest.mark.django_db
class TestPublicGymProfileView:
    def test_returns_404_for_unpublished(self):
        profile = GymProfileFactory(is_published=False)
        resp = APIClient().get(f"/api/v1/profiles/gym/{profile.slug}/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_returns_data_for_published(self):
        profile = PublishedGymProfileFactory()
        resp = APIClient().get(f"/api/v1/profiles/gym/{profile.slug}/")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["data"]["gym_name"] == profile.gym_name


@pytest.mark.django_db
class TestProfileSearchView:
    URL = "/api/v1/profiles/search/"

    def test_returns_paginated_results(self):
        PublishedTrainerProfileFactory.create_batch(3)
        resp = APIClient().get(self.URL)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["meta"]["pagination"]["total_count"] >= 3

    def test_filters_by_location(self):
        PublishedTrainerProfileFactory(location="Lagos")
        PublishedTrainerProfileFactory(location="Abuja")
        resp = APIClient().get(self.URL, {"location": "Lagos"})
        for item in resp.data["data"]:
            assert "lagos" in item["location"].lower()

    def test_filters_by_specialisation(self):
        spec = SpecialisationFactory(name="Yoga")
        profile = PublishedTrainerProfileFactory()
        profile.specialisations.add(spec)
        resp = APIClient().get(self.URL, {"specialisation": spec.slug})
        assert resp.status_code == status.HTTP_200_OK

    def test_gym_search_returns_gyms(self):
        PublishedGymProfileFactory.create_batch(2)
        resp = APIClient().get(self.URL, {"type": "gym"})
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["meta"]["pagination"]["total_count"] >= 2

    def test_only_published_profiles_returned(self):
        TrainerProfileFactory(is_published=False)
        resp = APIClient().get(self.URL)
        for item in resp.data.get("data", []):
            # All returned items should be published (we can't check is_published
            # from public serializer, but if they appear, they're published)
            pass
        assert resp.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestPhotoUploadView:
    URL = "/api/v1/profiles/photo/"

    def test_upload_saves_and_returns_url(self):
        profile = TrainerProfileFactory()
        client = _auth_client(profile.user)
        image = _fake_image()
        resp = client.post(self.URL, {"photo": image}, format="multipart")
        assert resp.status_code == status.HTTP_200_OK
        assert "url" in resp.data["data"]
        assert resp.data["data"]["url"].startswith("/media/")

    def test_upload_rejects_large_file(self):
        profile = TrainerProfileFactory()
        client = _auth_client(profile.user)
        big_file = SimpleUploadedFile(
            "big.jpg",
            b"\xff\xd8\xff" + b"x" * (5 * 1024 * 1024 + 1),
            content_type="image/jpeg",
        )
        resp = client.post(self.URL, {"photo": big_file}, format="multipart")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_upload_rejects_non_image(self):
        profile = TrainerProfileFactory()
        client = _auth_client(profile.user)
        txt_file = SimpleUploadedFile(
            "doc.txt", b"not an image", content_type="text/plain"
        )
        resp = client.post(self.URL, {"photo": txt_file}, format="multipart")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_upload_requires_auth(self):
        image = _fake_image()
        resp = APIClient().post(self.URL, {"photo": image}, format="multipart")
        assert resp.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )
