"""
Tests for onboarding step tracking endpoints (new role-specific flows).

The old PATCH /api/v1/onboarding/step/ and POST /api/v1/onboarding/complete/
endpoints have been removed. Onboarding is now tracked via User.onboarding_step
and managed by the role-specific endpoints in apps/profiles/onboarding_views.py.

These tests verify that onboarding_step and onboarding_status are updated
correctly through the new endpoints.
"""

import pytest
from rest_framework.test import APIClient

from apps.accounts.tests.factories import ClientFactory, TrainerFactory
from apps.profiles.tests.factories import TrainerProfileFactory

TRAINER_EXPERTISE_URL = "/api/v1/onboarding/trainer/expertise/"
TRAINER_PRODUCTS_URL = "/api/v1/onboarding/trainer/products/"


@pytest.fixture
def api_client():
    return APIClient()


@pytest.mark.django_db
class TestOnboardingStepTracking:

    def test_step1_sets_user_onboarding_step(self, api_client):
        from apps.profiles.tests.factories import SpecialisationFactory

        trainer = TrainerFactory()
        TrainerProfileFactory(user=trainer)
        s1 = SpecialisationFactory(name="Running")
        api_client.force_authenticate(user=trainer)

        resp = api_client.post(
            TRAINER_EXPERTISE_URL,
            {"expertise_ids": [s1.id], "custom_names": []},
            format="json",
        )

        assert resp.status_code == 200
        trainer.refresh_from_db()
        assert trainer.onboarding_step == 1

    def test_step_never_decreases(self, api_client):
        from apps.profiles.tests.factories import SpecialisationFactory

        trainer = TrainerFactory()
        TrainerProfileFactory(user=trainer)
        trainer.onboarding_step = 2
        trainer.save(update_fields=["onboarding_step"])
        s1 = SpecialisationFactory(name="HIIT Advanced")
        api_client.force_authenticate(user=trainer)

        # POST to step 1 endpoint — should stay at 2
        api_client.post(
            TRAINER_EXPERTISE_URL,
            {"expertise_ids": [s1.id], "custom_names": []},
            format="json",
        )

        trainer.refresh_from_db()
        assert trainer.onboarding_step == 2

    def test_idempotent_same_step_twice(self, api_client):
        from apps.profiles.tests.factories import SpecialisationFactory

        trainer = TrainerFactory()
        TrainerProfileFactory(user=trainer)
        s1 = SpecialisationFactory(name="Boxing Pro")
        api_client.force_authenticate(user=trainer)

        api_client.post(
            TRAINER_EXPERTISE_URL,
            {"expertise_ids": [s1.id], "custom_names": []},
            format="json",
        )
        resp = api_client.post(
            TRAINER_EXPERTISE_URL,
            {"expertise_ids": [], "custom_names": []},
            format="json",
        )

        assert resp.status_code == 200
        trainer.refresh_from_db()
        assert trainer.onboarding_step == 1

    def test_sets_onboarding_status_in_progress(self, api_client):
        from apps.profiles.tests.factories import SpecialisationFactory

        trainer = TrainerFactory()
        TrainerProfileFactory(user=trainer)
        s1 = SpecialisationFactory(name="Yoga Pro")
        api_client.force_authenticate(user=trainer)

        api_client.post(
            TRAINER_EXPERTISE_URL,
            {"expertise_ids": [s1.id], "custom_names": []},
            format="json",
        )

        trainer.refresh_from_db()
        assert trainer.onboarding_status == "in_progress"

    def test_client_cannot_call_trainer_endpoint(self, api_client):
        from apps.profiles.tests.factories import ClientProfileFactory

        client = ClientFactory()
        ClientProfileFactory(user=client)
        api_client.force_authenticate(user=client)

        resp = api_client.post(
            TRAINER_EXPERTISE_URL,
            {"expertise_ids": [], "custom_names": []},
            format="json",
        )

        assert resp.status_code == 403


@pytest.mark.django_db
class TestOnboardingComplete:

    def test_step2_sets_onboarding_status_completed(self, api_client):
        trainer = TrainerFactory()
        TrainerProfileFactory(user=trainer)
        api_client.force_authenticate(user=trainer)

        resp = api_client.post(
            TRAINER_PRODUCTS_URL, {"offers_products": False}, format="json"
        )

        assert resp.status_code == 200
        trainer.refresh_from_db()
        assert trainer.onboarding_status == "completed"

    def test_step2_sets_onboarding_completed_at(self, api_client):
        trainer = TrainerFactory()
        TrainerProfileFactory(user=trainer)
        api_client.force_authenticate(user=trainer)

        api_client.post(TRAINER_PRODUCTS_URL, {"offers_products": True}, format="json")

        trainer.refresh_from_db()
        assert trainer.onboarding_completed_at is not None

    def test_step2_sets_onboarding_step_2(self, api_client):
        trainer = TrainerFactory()
        TrainerProfileFactory(user=trainer)
        api_client.force_authenticate(user=trainer)

        resp = api_client.post(
            TRAINER_PRODUCTS_URL, {"offers_products": True}, format="json"
        )

        assert resp.status_code == 200
        trainer.refresh_from_db()
        assert trainer.onboarding_step == 2

    def test_client_cannot_call_trainer_products_endpoint(self, api_client):
        from apps.profiles.tests.factories import ClientProfileFactory

        client = ClientFactory()
        ClientProfileFactory(user=client)
        api_client.force_authenticate(user=client)

        resp = api_client.post(
            TRAINER_PRODUCTS_URL, {"offers_products": True}, format="json"
        )

        assert resp.status_code == 403
