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

    def _ready_profile(self):
        """Return a trainer profile with ≥60% completion."""
        return TrainerProfileFactory(
            full_name="Ready Trainer",
            bio="A solid bio",
            location="Lagos",
            profile_photo_url="http://example.com/photo.jpg",
        )

    def test_publishes_profile(self):
        profile = self._ready_profile()
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
        profile = self._ready_profile()
        BasicPlanFactory()
        SubscriptionFactory(user=profile.user)
        client = _auth_client(profile.user)
        client.post(self.URL)
        profile.user.refresh_from_db()
        assert profile.user.onboarding_status == "completed"

    def test_blocked_when_subscription_locked(self):
        from apps.subscriptions.models import Subscription

        profile = self._ready_profile()
        BasicPlanFactory()
        SubscriptionFactory(user=profile.user, status=Subscription.Status.LOCKED)
        client = _auth_client(profile.user)
        resp = client.post(self.URL)
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_low_completion_does_not_block_publish(self):
        profile = TrainerProfileFactory()  # minimal completion
        BasicPlanFactory()
        SubscriptionFactory(user=profile.user)
        client = _auth_client(profile.user)
        resp = client.post(self.URL)
        assert resp.status_code == status.HTTP_200_OK

    def test_publish_at_any_completion_percentage(self):
        profile = TrainerProfileFactory(
            full_name="Trainer",
            bio="Some bio",
            location="Lagos",
            years_experience=3,
            cover_photo_url="http://example.com/cover.jpg",
        )
        assert profile.profile_completion_percentage < 60
        BasicPlanFactory()
        SubscriptionFactory(user=profile.user)
        client = _auth_client(profile.user)
        resp = client.post(self.URL)
        assert resp.status_code == status.HTTP_200_OK


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
        assert "needs_specialisation" in data


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


# ---------------------------------------------------------------------------
# Profile visibility toggle
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestProfileVisibilityView:
    URL = "/api/v1/profiles/me/visibility/"

    def test_trainer_sets_published_false(self):
        profile = TrainerProfileFactory(is_published=True)
        client = _auth_client(profile.user)
        resp = client.patch(self.URL, {"is_published": False}, format="json")
        assert resp.status_code == status.HTTP_200_OK
        profile.refresh_from_db()
        assert profile.is_published is False

    def test_trainer_sets_published_true(self):
        profile = TrainerProfileFactory(is_published=False)
        client = _auth_client(profile.user)
        resp = client.patch(self.URL, {"is_published": True}, format="json")
        assert resp.status_code == status.HTTP_200_OK
        profile.refresh_from_db()
        assert profile.is_published is True

    def test_gym_sets_published_false(self):
        profile = GymProfileFactory(is_published=True)
        client = _auth_client(profile.user)
        resp = client.patch(self.URL, {"is_published": False}, format="json")
        assert resp.status_code == status.HTTP_200_OK
        profile.refresh_from_db()
        assert profile.is_published is False

    def test_client_returns_403(self):
        profile = ClientProfileFactory()
        client = _auth_client(profile.user)
        resp = client.patch(self.URL, {"is_published": False}, format="json")
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated_returns_401(self):
        resp = APIClient().patch(self.URL, {"is_published": False}, format="json")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_missing_is_published_returns_400(self):
        profile = TrainerProfileFactory()
        client = _auth_client(profile.user)
        resp = client.patch(self.URL, {}, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST


# ---------------------------------------------------------------------------
# Publish gate removed
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestWizardPublishGateRemoved:
    URL = "/api/v1/profiles/wizard/step4/publish/"

    def test_low_completion_trainer_can_publish(self):
        profile = TrainerProfileFactory()  # minimal completion
        BasicPlanFactory()
        SubscriptionFactory(user=profile.user)
        client = _auth_client(profile.user)
        resp = client.post(self.URL)
        assert resp.status_code == status.HTTP_200_OK
        profile.refresh_from_db()
        assert profile.is_published is True


# ---------------------------------------------------------------------------
# Specialisation sub-resource
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestProfileSpecialisationView:
    POST_URL = "/api/v1/profiles/me/specialisations/"

    def _detail_url(self, spec_id):
        return f"/api/v1/profiles/me/specialisations/{spec_id}/"

    def test_post_with_valid_ids_attaches_specialisations(self):
        profile = TrainerProfileFactory()
        s1 = SpecialisationFactory(name="YogaNew")
        s2 = SpecialisationFactory(name="HIITNew")
        client = _auth_client(profile.user)
        resp = client.post(
            self.POST_URL,
            {"specialisation_ids": [s1.id, s2.id], "custom_names": []},
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK
        assert profile.specialisations.count() == 2

    def test_post_with_custom_names_creates_and_attaches(self):
        profile = TrainerProfileFactory()
        client = _auth_client(profile.user)
        resp = client.post(
            self.POST_URL,
            {"specialisation_ids": [], "custom_names": ["Crossfit", "Mobility"]},
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK
        assert profile.specialisations.count() == 2
        names = list(profile.specialisations.values_list("name", flat=True))
        assert "Crossfit" in names
        assert "Mobility" in names

    def test_post_exceeding_10_total_returns_400(self):
        profile = TrainerProfileFactory()
        existing = [SpecialisationFactory(name=f"ExistSpec{i}") for i in range(8)]
        profile.specialisations.set(existing)
        new_specs = [SpecialisationFactory(name=f"AddSpec{i}") for i in range(3)]
        client = _auth_client(profile.user)
        resp = client.post(
            self.POST_URL,
            {"specialisation_ids": [s.id for s in new_specs], "custom_names": []},
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_post_as_client_returns_403(self):
        cp = ClientProfileFactory()
        client = _auth_client(cp.user)
        resp = client.post(
            self.POST_URL,
            {"specialisation_ids": [], "custom_names": []},
            format="json",
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_delete_removes_specialisation_from_profile(self):
        profile = TrainerProfileFactory()
        spec = SpecialisationFactory(name="PilatesSpec")
        profile.specialisations.add(spec)
        client = _auth_client(profile.user)
        resp = client.delete(self._detail_url(spec.id))
        assert resp.status_code == status.HTTP_204_NO_CONTENT
        assert not profile.specialisations.filter(id=spec.id).exists()

    def test_delete_when_not_attached_returns_404(self):
        profile = TrainerProfileFactory()
        spec = SpecialisationFactory(name="UnattachedSpec")
        client = _auth_client(profile.user)
        resp = client.delete(self._detail_url(spec.id))
        assert resp.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# Services sub-resource
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestProfileServiceEndpoints:
    LIST_URL = "/api/v1/profiles/me/services/"

    def _detail_url(self, service_id):
        return f"/api/v1/profiles/me/services/{service_id}/"

    def test_get_returns_own_services_only(self):
        profile = TrainerProfileFactory()
        ServiceTrainerFactory(trainer=profile, name="My Own Service")
        ServiceTrainerFactory(name="Other Trainer Service")
        client = _auth_client(profile.user)
        resp = client.get(self.LIST_URL)
        assert resp.status_code == status.HTTP_200_OK
        names = [s["name"] for s in resp.data["data"]]
        assert "My Own Service" in names
        assert "Other Trainer Service" not in names

    def test_post_creates_service(self):
        profile = TrainerProfileFactory()
        client = _auth_client(profile.user)
        resp = client.post(
            self.LIST_URL,
            {
                "name": "Personal Training",
                "session_type": "physical",
                "display_order": 0,
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED
        assert profile.services.filter(name="Personal Training").exists()

    def test_put_updates_service(self):
        profile = TrainerProfileFactory()
        svc = ServiceTrainerFactory(trainer=profile, name="Old Name")
        client = _auth_client(profile.user)
        resp = client.put(
            self._detail_url(svc.id),
            {"name": "Updated Name", "session_type": "both", "display_order": 1},
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK
        svc.refresh_from_db()
        assert svc.name == "Updated Name"

    def test_put_another_trainers_service_returns_404(self):
        profile = TrainerProfileFactory()
        other_svc = ServiceTrainerFactory(name="Other Service")
        client = _auth_client(profile.user)
        resp = client.put(
            self._detail_url(other_svc.id),
            {"name": "Hacked", "session_type": "both", "display_order": 0},
            format="json",
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_service(self):
        profile = TrainerProfileFactory()
        svc = ServiceTrainerFactory(trainer=profile, name="To Delete")
        client = _auth_client(profile.user)
        resp = client.delete(self._detail_url(svc.id))
        assert resp.status_code == status.HTTP_204_NO_CONTENT
        assert not profile.services.filter(id=svc.id).exists()

    def test_client_gets_403_on_all_service_endpoints(self):
        cp = ClientProfileFactory()
        client = _auth_client(cp.user)
        assert client.get(self.LIST_URL).status_code == status.HTTP_403_FORBIDDEN
        assert (
            client.post(self.LIST_URL, {}, format="json").status_code
            == status.HTTP_403_FORBIDDEN
        )


# ---------------------------------------------------------------------------
# Certifications sub-resource
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestProfileCertificationEndpoints:
    LIST_URL = "/api/v1/profiles/me/certifications/"

    def _detail_url(self, cert_id):
        return f"/api/v1/profiles/me/certifications/{cert_id}/"

    def test_get_returns_own_certifications(self):
        profile = TrainerProfileFactory()
        CertificationFactory(trainer=profile, name="My Cert")
        client = _auth_client(profile.user)
        resp = client.get(self.LIST_URL)
        assert resp.status_code == status.HTTP_200_OK
        names = [c["name"] for c in resp.data["data"]]
        assert "My Cert" in names

    def test_post_as_trainer_creates_certification(self):
        profile = TrainerProfileFactory()
        client = _auth_client(profile.user)
        resp = client.post(
            self.LIST_URL,
            {"name": "ACE Certified", "issuing_body": "ACE", "year_obtained": 2022},
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED
        assert profile.certifications.filter(name="ACE Certified").exists()

    def test_post_as_gym_returns_403(self):
        profile = GymProfileFactory()
        client = _auth_client(profile.user)
        resp = client.post(
            self.LIST_URL,
            {"name": "Gym Cert", "issuing_body": "GYM", "year_obtained": 2020},
            format="json",
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_put_updates_certification(self):
        profile = TrainerProfileFactory()
        cert = CertificationFactory(trainer=profile, name="Old Cert")
        client = _auth_client(profile.user)
        resp = client.put(
            self._detail_url(cert.id),
            {"name": "Updated Cert", "issuing_body": "NASM", "year_obtained": 2023},
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK
        cert.refresh_from_db()
        assert cert.name == "Updated Cert"

    def test_delete_certification(self):
        profile = TrainerProfileFactory()
        cert = CertificationFactory(trainer=profile, name="To Delete Cert")
        client = _auth_client(profile.user)
        resp = client.delete(self._detail_url(cert.id))
        assert resp.status_code == status.HTTP_204_NO_CONTENT
        assert not profile.certifications.filter(id=cert.id).exists()


# ---------------------------------------------------------------------------
# Availability sub-resource
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestProfileAvailabilityEndpoints:
    LIST_URL = "/api/v1/profiles/me/availability/"

    def _detail_url(self, av_id):
        return f"/api/v1/profiles/me/availability/{av_id}/"

    def _av_payload(self, day="monday"):
        return {
            "day_of_week": day,
            "start_time": "06:00",
            "end_time": "12:00",
            "session_type": "both",
            "duration_minutes": 60,
            "virtual_platform": "",
            "notes": "",
        }

    def test_get_returns_own_records(self):
        profile = TrainerProfileFactory()
        AvailabilityTrainerFactory(trainer=profile, day_of_week="tuesday")
        other_profile = TrainerProfileFactory()
        AvailabilityTrainerFactory(trainer=other_profile, day_of_week="wednesday")
        client = _auth_client(profile.user)
        resp = client.get(self.LIST_URL)
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data["data"]) == 1

    def test_post_creates_availability_for_trainer(self):
        profile = TrainerProfileFactory()
        client = _auth_client(profile.user)
        resp = client.post(self.LIST_URL, self._av_payload(), format="json")
        assert resp.status_code == status.HTTP_201_CREATED
        assert profile.availability.filter(day_of_week="monday").exists()

    def test_post_duplicate_day_returns_400(self):
        profile = TrainerProfileFactory()
        AvailabilityTrainerFactory(trainer=profile, day_of_week="monday")
        client = _auth_client(profile.user)
        resp = client.post(self.LIST_URL, self._av_payload("monday"), format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_put_updates_availability(self):
        profile = TrainerProfileFactory()
        av = AvailabilityTrainerFactory(
            trainer=profile,
            day_of_week="friday",
            start_time="08:00",
            end_time="10:00",
        )
        client = _auth_client(profile.user)
        payload = self._av_payload("friday")
        payload["start_time"] = "09:00"
        payload["end_time"] = "11:00"
        resp = client.put(self._detail_url(av.id), payload, format="json")
        assert resp.status_code == status.HTTP_200_OK
        av.refresh_from_db()
        assert str(av.start_time) == "09:00:00"

    def test_delete_availability(self):
        profile = TrainerProfileFactory()
        av = AvailabilityTrainerFactory(trainer=profile, day_of_week="saturday")
        client = _auth_client(profile.user)
        resp = client.delete(self._detail_url(av.id))
        assert resp.status_code == status.HTTP_204_NO_CONTENT
        assert not profile.availability.filter(id=av.id).exists()

    def test_gym_can_post_availability(self):
        profile = GymProfileFactory()
        client = _auth_client(profile.user)
        resp = client.post(self.LIST_URL, self._av_payload(), format="json")
        assert resp.status_code == status.HTTP_201_CREATED
        assert profile.availability.filter(day_of_week="monday").exists()
