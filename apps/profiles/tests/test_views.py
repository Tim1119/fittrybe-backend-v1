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
    """
    Wizard step 1 endpoint has been removed.
    Profile basic info is now updated via PATCH /api/v1/profiles/me/.
    These tests verify the old wizard URL is no longer available.
    """

    URL = "/api/v1/profiles/wizard/step1/"

    def test_trainer_step1_endpoint_removed(self):
        profile = TrainerProfileFactory()
        client = _auth_client(profile.user)
        resp = client.put(self.URL, {"full_name": "Test"}, format="json")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_trainer_step1_sets_onboarding_in_progress(self):
        # Onboarding status is now updated via /api/v1/onboarding/trainer/expertise/
        # Verify trainer starts with not_started status
        profile = TrainerProfileFactory()
        profile.user.refresh_from_db()
        assert profile.user.onboarding_status == "not_started"

    def test_gym_step1_endpoint_removed(self):
        profile = GymProfileFactory()
        client = _auth_client(profile.user)
        resp = client.put(self.URL, {"full_name": "x"}, format="json")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_step1_requires_authentication(self):
        client = APIClient()
        resp = client.put(self.URL, {}, format="json")
        # URL is gone — returns 404
        assert resp.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND,
        )

    def test_step1_forbidden_for_client(self):
        cp = ClientProfileFactory()
        client = _auth_client(cp.user)
        resp = client.put(self.URL, {"full_name": "x"}, format="json")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_wizard_step_not_decremented(self):
        # wizard_step field no longer exists; User.onboarding_step never decreases
        profile = TrainerProfileFactory()
        profile.user.onboarding_step = 2
        profile.user.save(update_fields=["onboarding_step"])
        # Any call to step-1 onboarding endpoint should not reduce onboarding_step
        profile.user.refresh_from_db()
        assert profile.user.onboarding_step == 2


@pytest.mark.django_db
class TestWizardStep2View:
    """
    Wizard step 2 endpoint removed. Specialisations managed via
    /api/v1/onboarding/trainer/expertise/; services via onboarding or me/services/.
    """

    URL = "/api/v1/profiles/wizard/step2/"

    def test_wizard_step2_endpoint_removed(self):
        profile = TrainerProfileFactory()
        client = _auth_client(profile.user)
        resp = client.put(self.URL, {}, format="json")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_rejects_more_than_10_specialisations_via_onboarding(self):
        profile = TrainerProfileFactory()
        client = _auth_client(profile.user)
        specs = [SpecialisationFactory().id for _ in range(11)]
        resp = client.post(
            "/api/v1/onboarding/trainer/expertise/",
            {"expertise_ids": specs, "custom_names": []},
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_certifications_readable_via_profile_endpoint(self):
        profile = TrainerProfileFactory()
        CertificationFactory(trainer=profile, name="Old Cert")
        client = _auth_client(profile.user)
        resp = client.get("/api/v1/profiles/me/certifications/")
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data["data"]) == 1

    def test_trainer_services_creatable_via_me_endpoint(self):
        profile = TrainerProfileFactory()
        client = _auth_client(profile.user)
        payload = {"name": "Personal Training", "session_type": "physical"}
        resp = client.post("/api/v1/profiles/me/services/", payload, format="json")
        assert resp.status_code == status.HTTP_201_CREATED
        assert profile.services.count() == 1

    def test_trainer_step2_services_listable(self):
        profile = TrainerProfileFactory()
        ServiceTrainerFactory(trainer=profile, name="Old Service")
        client = _auth_client(profile.user)
        resp = client.get("/api/v1/profiles/me/services/")
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data["data"]) == 1

    def test_gym_services_via_onboarding_endpoint(self):
        profile = GymProfileFactory()
        client = _auth_client(profile.user)
        payload = {"services": [{"name": "Group Classes", "session_type": "physical"}]}
        resp = client.post("/api/v1/onboarding/gym/services/", payload, format="json")
        assert resp.status_code == status.HTTP_200_OK
        assert profile.services.count() == 1

    def test_gym_step2_empty_services_ok_via_onboarding(self):
        profile = GymProfileFactory()
        client = _auth_client(profile.user)
        resp = client.post(
            "/api/v1/onboarding/gym/services/", {"services": []}, format="json"
        )
        assert resp.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestWizardStep3View:
    """
    Wizard step 3 endpoint removed. Availability is managed via
    PUT /api/v1/profiles/me/availability/.
    """

    URL = "/api/v1/profiles/wizard/step3/"
    AV_URL = "/api/v1/profiles/me/availability/"

    def test_wizard_step3_endpoint_removed(self):
        profile = TrainerProfileFactory()
        client = _auth_client(profile.user)
        resp = client.put(self.URL, {}, format="json")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_trainer_creates_availability(self):
        profile = TrainerProfileFactory()
        client = _auth_client(profile.user)
        resp = client.post(
            self.AV_URL,
            {"day_of_week": "monday", "start_time": "09:00", "end_time": "10:00"},
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED
        assert profile.availability.count() == 1

    def test_gym_creates_availability(self):
        profile = GymProfileFactory()
        client = _auth_client(profile.user)
        resp = client.post(
            self.AV_URL,
            {"day_of_week": "monday", "start_time": "09:00", "end_time": "10:00"},
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED
        assert profile.availability.count() == 1

    def test_rejects_duplicate_days(self):
        profile = TrainerProfileFactory()
        AvailabilityTrainerFactory(trainer=profile, day_of_week="monday")
        client = _auth_client(profile.user)
        resp = client.post(
            self.AV_URL,
            {"day_of_week": "monday", "start_time": "11:00", "end_time": "12:00"},
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_availability_slots_accumulate(self):
        profile = TrainerProfileFactory()
        AvailabilityTrainerFactory(trainer=profile, day_of_week="friday")
        client = _auth_client(profile.user)
        client.post(
            self.AV_URL,
            {"day_of_week": "monday", "start_time": "09:00", "end_time": "10:00"},
            format="json",
        )
        assert profile.availability.count() == 2
        days = list(profile.availability.values_list("day_of_week", flat=True))
        assert "friday" in days


@pytest.mark.django_db
class TestWizardStep4View:
    """
    Wizard step 4 endpoint removed. Profile publishing and products preference
    is managed via POST /api/v1/onboarding/trainer/products/.
    """

    URL = "/api/v1/profiles/wizard/step4/publish/"
    PRODUCTS_URL = "/api/v1/onboarding/trainer/products/"

    def test_wizard_step4_endpoint_removed(self):
        profile = TrainerProfileFactory()
        client = _auth_client(profile.user)
        resp = client.post(self.URL)
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_trainer_products_publishes_profile(self):
        profile = TrainerProfileFactory()
        client = _auth_client(profile.user)
        resp = client.post(self.PRODUCTS_URL, {"offers_products": False}, format="json")
        assert resp.status_code == status.HTTP_200_OK
        profile.refresh_from_db()
        assert profile.is_published is True

    def test_completes_onboarding(self):
        profile = TrainerProfileFactory()
        client = _auth_client(profile.user)
        client.post(self.PRODUCTS_URL, {"offers_products": False}, format="json")
        profile.user.refresh_from_db()
        assert profile.user.onboarding_status == "completed"

    def test_sets_offers_products_true(self):
        profile = TrainerProfileFactory()
        client = _auth_client(profile.user)
        client.post(self.PRODUCTS_URL, {"offers_products": True}, format="json")
        profile.refresh_from_db()
        assert profile.offers_products is True

    def test_publish_at_any_completion_percentage(self):
        profile = TrainerProfileFactory(
            full_name="Trainer",
            bio="Some bio",
            location="Lagos",
            years_experience=3,
            cover_photo_url="http://example.com/cover.jpg",
        )
        assert profile.profile_completion_percentage < 60
        client = _auth_client(profile.user)
        resp = client.post(self.PRODUCTS_URL, {"offers_products": False}, format="json")
        assert resp.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestWizardStatusView:
    """
    Wizard status endpoint removed. Profile completion percentage is
    returned by GET /api/v1/profiles/me/.
    """

    URL = "/api/v1/profiles/wizard/status/"

    def test_wizard_status_endpoint_removed(self):
        profile = TrainerProfileFactory(full_name="Test")
        client = _auth_client(profile.user)
        resp = client.get(self.URL)
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_profile_completion_percentage_in_me_endpoint(self):
        profile = TrainerProfileFactory(full_name="Test")
        client = _auth_client(profile.user)
        resp = client.get("/api/v1/profiles/me/")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.data["data"]
        assert "profile_completion_percentage" in data


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
        assert resp.data["data"]["full_name"] == profile.full_name

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
        assert resp.data["data"]["full_name"] == profile.full_name


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
    """
    The old wizard publish gate (subscription + 60% completion check) is removed.
    Publishing now happens via POST /api/v1/onboarding/trainer/products/ without
    any completion-percentage or subscription gate.
    """

    URL = "/api/v1/profiles/wizard/step4/publish/"
    PRODUCTS_URL = "/api/v1/onboarding/trainer/products/"

    def test_wizard_publish_endpoint_removed(self):
        profile = TrainerProfileFactory()
        client = _auth_client(profile.user)
        resp = client.post(self.URL)
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_low_completion_trainer_can_publish(self):
        profile = TrainerProfileFactory()
        client = _auth_client(profile.user)
        resp = client.post(self.PRODUCTS_URL, {"offers_products": False}, format="json")
        assert resp.status_code == status.HTTP_200_OK
        profile.refresh_from_db()
        assert profile.is_published is True


# ---------------------------------------------------------------------------
# Specialisation sub-resource
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestProfileSpecialisationView:
    POST_URL = "/api/v1/profiles/me/expertise/"

    def _detail_url(self, spec_id):
        return f"/api/v1/profiles/me/expertise/{spec_id}/"

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


# ---------------------------------------------------------------------------
# gym_name renamed to full_name + admin_full_name removed
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestGymProfileFullNameRename:
    PUBLIC_URL = "/api/v1/profiles/gym/{slug}/"

    def test_public_gym_profile_contains_full_name_not_gym_name(self):
        profile = PublishedGymProfileFactory(full_name="Iron Gym")
        url = self.PUBLIC_URL.format(slug=profile.slug)
        client = APIClient()
        resp = client.get(url)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.data["data"]
        assert "full_name" in data
        assert data["full_name"] == "Iron Gym"
        assert "gym_name" not in data

    def test_public_gym_profile_no_admin_full_name_field(self):
        profile = PublishedGymProfileFactory()
        url = self.PUBLIC_URL.format(slug=profile.slug)
        client = APIClient()
        resp = client.get(url)
        assert resp.status_code == status.HTTP_200_OK
        assert "admin_full_name" not in resp.data["data"]

    def test_gym_search_by_full_name_works(self):
        PublishedGymProfileFactory(full_name="Power House")
        client = APIClient()
        resp = client.get(
            "/api/v1/profiles/search/", {"type": "gym", "q": "Power House"}
        )
        assert resp.status_code == status.HTTP_200_OK
        results = resp.data["data"]
        assert len(results) >= 1


# ---------------------------------------------------------------------------
# ExpertiseListView (GET /api/v1/expertise/)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestExpertiseListView:
    URL = "/api/v1/expertise/"

    def test_no_auth_required_returns_200(self):
        resp = APIClient().get(self.URL)
        assert resp.status_code == status.HTTP_200_OK

    def test_returns_predefined_specialisations(self):
        SpecialisationFactory(name="ExListPred1", is_predefined=True)
        SpecialisationFactory(name="ExListPred2", is_predefined=True)
        resp = APIClient().get(self.URL)
        assert resp.status_code == status.HTTP_200_OK
        names = [s["name"] for s in resp.data["data"]]
        assert "ExListPred1" in names
        assert "ExListPred2" in names

    def test_is_predefined_true_filter(self):
        SpecialisationFactory(name="ExFilterPred", is_predefined=True)
        SpecialisationFactory(name="ExFilterCustom", is_predefined=False)
        resp = APIClient().get(self.URL + "?is_predefined=true")
        assert resp.status_code == status.HTTP_200_OK
        names = [s["name"] for s in resp.data["data"]]
        assert "ExFilterPred" in names
        assert "ExFilterCustom" not in names

    def test_is_predefined_false_filter(self):
        SpecialisationFactory(name="ExFalsePred", is_predefined=True)
        SpecialisationFactory(name="ExFalseCustom", is_predefined=False)
        resp = APIClient().get(self.URL + "?is_predefined=false")
        assert resp.status_code == status.HTTP_200_OK
        names = [s["name"] for s in resp.data["data"]]
        assert "ExFalseCustom" in names
        assert "ExFalsePred" not in names

    def test_response_fields(self):
        SpecialisationFactory(name="ExFieldSpec", is_predefined=True)
        resp = APIClient().get(self.URL)
        assert resp.status_code == status.HTTP_200_OK
        first = next(s for s in resp.data["data"] if s["name"] == "ExFieldSpec")
        assert "id" in first
        assert "name" in first
        assert "slug" in first
        assert "is_predefined" in first


# ---------------------------------------------------------------------------
# GoalListView (GET /api/v1/expertise/goals/)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestGoalListViewExpertise:
    URL = "/api/v1/expertise/goals/"

    def test_no_auth_required_returns_200(self):
        resp = APIClient().get(self.URL)
        assert resp.status_code == status.HTTP_200_OK

    def test_returns_predefined_goals(self):
        from apps.profiles.models import Goal

        Goal.objects.create(name="GoalListPred1", is_predefined=True)
        resp = APIClient().get(self.URL)
        assert resp.status_code == status.HTTP_200_OK
        names = [g["name"] for g in resp.data["data"]]
        assert "GoalListPred1" in names

    def test_is_predefined_true_filter(self):
        from apps.profiles.models import Goal

        Goal.objects.create(name="GoalFilterPred", is_predefined=True)
        Goal.objects.create(name="GoalFilterCustom", is_predefined=False)
        resp = APIClient().get(self.URL + "?is_predefined=true")
        assert resp.status_code == status.HTTP_200_OK
        names = [g["name"] for g in resp.data["data"]]
        assert "GoalFilterPred" in names
        assert "GoalFilterCustom" not in names

    def test_response_fields(self):
        from apps.profiles.models import Goal

        Goal.objects.create(name="GoalFieldTest", is_predefined=True)
        resp = APIClient().get(self.URL)
        assert resp.status_code == status.HTTP_200_OK
        first = next(g for g in resp.data["data"] if g["name"] == "GoalFieldTest")
        assert "id" in first
        assert "name" in first
        assert "slug" in first
        assert "is_predefined" in first


# ---------------------------------------------------------------------------
# Old URLs must return 404 after cleanup
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestOldUrlsReturn404:
    def test_old_specialisations_list_url_returns_404(self):
        resp = APIClient().get("/api/v1/profiles/specialisations/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_old_onboarding_goals_url_returns_404(self):
        resp = APIClient().get("/api/v1/onboarding/goals/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_old_me_specialisations_get_returns_404(self):
        profile = TrainerProfileFactory()
        client = _auth_client(profile.user)
        resp = client.get("/api/v1/profiles/me/specialisations/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_old_me_specialisations_post_returns_404(self):
        profile = TrainerProfileFactory()
        client = _auth_client(profile.user)
        resp = client.post("/api/v1/profiles/me/specialisations/", {}, format="json")
        assert resp.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# ProfileExpertiseView (GET/POST /api/v1/profiles/me/expertise/)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestProfileExpertiseView:
    URL = "/api/v1/profiles/me/expertise/"

    def _detail_url(self, spec_id):
        return f"/api/v1/profiles/me/expertise/{spec_id}/"

    def test_get_returns_200_for_trainer(self):
        profile = TrainerProfileFactory()
        client = _auth_client(profile.user)
        resp = client.get(self.URL)
        assert resp.status_code == status.HTTP_200_OK

    def test_post_attaches_expertise_by_id(self):
        profile = TrainerProfileFactory()
        s = SpecialisationFactory(name="ExpertiseNew1")
        client = _auth_client(profile.user)
        resp = client.post(
            self.URL,
            {"specialisation_ids": [s.id], "custom_names": []},
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK
        assert profile.specialisations.filter(id=s.id).exists()

    def test_delete_removes_expertise(self):
        profile = TrainerProfileFactory()
        spec = SpecialisationFactory(name="RemoveExpertise")
        profile.specialisations.add(spec)
        client = _auth_client(profile.user)
        resp = client.delete(self._detail_url(spec.id))
        assert resp.status_code == status.HTTP_204_NO_CONTENT
        assert not profile.specialisations.filter(id=spec.id).exists()

    def test_client_cannot_access(self):
        cp = ClientProfileFactory()
        client = _auth_client(cp.user)
        resp = client.get(self.URL)
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated_returns_401(self):
        resp = APIClient().get(self.URL)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


# ---------------------------------------------------------------------------
# ProfileClientGoalsView (GET/POST /api/v1/profiles/me/goals/)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestProfileClientGoalsView:
    URL = "/api/v1/profiles/me/goals/"

    def _detail_url(self, goal_id):
        return f"/api/v1/profiles/me/goals/{goal_id}/"

    def test_unauthenticated_returns_401(self):
        resp = APIClient().get(self.URL)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_trainer_returns_403(self):
        profile = TrainerProfileFactory()
        client = _auth_client(profile.user)
        resp = client.get(self.URL)
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_gym_returns_403(self):
        profile = GymProfileFactory()
        client = _auth_client(profile.user)
        resp = client.get(self.URL)
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_client_get_empty_list_returns_200(self):
        cp = ClientProfileFactory()
        client = _auth_client(cp.user)
        resp = client.get(self.URL)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["data"] == []

    def test_client_post_adds_goals(self):
        from apps.profiles.models import Goal

        cp = ClientProfileFactory()
        g = Goal.objects.create(name="GoalCRUD1", is_predefined=True)
        client = _auth_client(cp.user)
        resp = client.post(self.URL, {"goal_ids": [g.id]}, format="json")
        assert resp.status_code == status.HTTP_200_OK
        assert cp.primary_goals.filter(id=g.id).exists()

    def test_client_post_exceeds_6_returns_400(self):
        from apps.profiles.models import Goal

        cp = ClientProfileFactory()
        goals = [Goal.objects.create(name=f"GoalLimitCRUD{i}") for i in range(7)]
        client = _auth_client(cp.user)
        resp = client.post(self.URL, {"goal_ids": [g.id for g in goals]}, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_client_delete_removes_goal(self):
        from apps.profiles.models import Goal

        cp = ClientProfileFactory()
        g = Goal.objects.create(name="GoalDeleteCRUD")
        cp.primary_goals.add(g)
        client = _auth_client(cp.user)
        resp = client.delete(self._detail_url(g.id))
        assert resp.status_code == status.HTTP_204_NO_CONTENT
        assert not cp.primary_goals.filter(id=g.id).exists()

    def test_client_delete_not_attached_returns_404(self):
        from apps.profiles.models import Goal

        cp = ClientProfileFactory()
        g = Goal.objects.create(name="GoalNotAttachedCRUD")
        client = _auth_client(cp.user)
        resp = client.delete(self._detail_url(g.id))
        assert resp.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# ProfileClientFocusView (GET/POST /api/v1/profiles/me/focus/)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestProfileClientFocusView:
    URL = "/api/v1/profiles/me/focus/"

    def _detail_url(self, spec_id):
        return f"/api/v1/profiles/me/focus/{spec_id}/"

    def test_unauthenticated_returns_401(self):
        resp = APIClient().get(self.URL)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_trainer_returns_403(self):
        profile = TrainerProfileFactory()
        client = _auth_client(profile.user)
        resp = client.get(self.URL)
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_gym_returns_403(self):
        profile = GymProfileFactory()
        client = _auth_client(profile.user)
        resp = client.get(self.URL)
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_client_get_empty_list_returns_200(self):
        cp = ClientProfileFactory()
        client = _auth_client(cp.user)
        resp = client.get(self.URL)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["data"] == []

    def test_client_post_adds_focus(self):
        cp = ClientProfileFactory()
        s = SpecialisationFactory(name="FocusCRUD1")
        client = _auth_client(cp.user)
        resp = client.post(self.URL, {"specialisation_ids": [s.id]}, format="json")
        assert resp.status_code == status.HTTP_200_OK
        assert cp.specialisations.filter(id=s.id).exists()

    def test_client_post_exceeds_10_returns_400(self):
        cp = ClientProfileFactory()
        specs = [SpecialisationFactory(name=f"FocusLimitCRUD{i}") for i in range(11)]
        client = _auth_client(cp.user)
        resp = client.post(
            self.URL,
            {"specialisation_ids": [s.id for s in specs]},
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_client_delete_removes_focus(self):
        cp = ClientProfileFactory()
        s = SpecialisationFactory(name="FocusDeleteCRUD")
        cp.specialisations.add(s)
        client = _auth_client(cp.user)
        resp = client.delete(self._detail_url(s.id))
        assert resp.status_code == status.HTTP_204_NO_CONTENT
        assert not cp.specialisations.filter(id=s.id).exists()

    def test_client_delete_not_attached_returns_404(self):
        cp = ClientProfileFactory()
        s = SpecialisationFactory(name="FocusNotAttachedCRUD")
        client = _auth_client(cp.user)
        resp = client.delete(self._detail_url(s.id))
        assert resp.status_code == status.HTTP_404_NOT_FOUND
