"""
Tests for onboarding step tracking endpoints.

PATCH /api/v1/onboarding/step/   — record wizard progress
POST  /api/v1/onboarding/complete/ — mark onboarding finished (step 5)
"""

import pytest
from rest_framework.test import APIClient

from apps.accounts.tests.factories import ClientFactory, TrainerFactory
from apps.profiles.tests.factories import TrainerProfileFactory

STEP_URL = "/api/v1/onboarding/step/"
COMPLETE_URL = "/api/v1/onboarding/complete/"


@pytest.fixture
def api_client():
    return APIClient()


@pytest.mark.django_db
class TestOnboardingStepView:

    def test_step1_sets_wizard_step(self, api_client):
        trainer = TrainerFactory()
        profile = TrainerProfileFactory(user=trainer, wizard_step=0)
        api_client.force_authenticate(user=trainer)

        resp = api_client.patch(STEP_URL, {"step": 1}, format="json")

        assert resp.status_code == 200
        profile.refresh_from_db()
        assert profile.wizard_step == 1

    def test_step2_sets_wizard_step(self, api_client):
        trainer = TrainerFactory()
        profile = TrainerProfileFactory(user=trainer, wizard_step=1)
        api_client.force_authenticate(user=trainer)

        resp = api_client.patch(STEP_URL, {"step": 2}, format="json")

        assert resp.status_code == 200
        profile.refresh_from_db()
        assert profile.wizard_step == 2

    def test_idempotent_same_step_twice(self, api_client):
        trainer = TrainerFactory()
        profile = TrainerProfileFactory(user=trainer, wizard_step=0)
        api_client.force_authenticate(user=trainer)

        api_client.patch(STEP_URL, {"step": 1}, format="json")
        resp = api_client.patch(STEP_URL, {"step": 1}, format="json")

        assert resp.status_code == 200
        profile.refresh_from_db()
        assert profile.wizard_step == 1

    def test_never_decreases_wizard_step(self, api_client):
        trainer = TrainerFactory()
        profile = TrainerProfileFactory(user=trainer, wizard_step=3)
        api_client.force_authenticate(user=trainer)

        resp = api_client.patch(STEP_URL, {"step": 1}, format="json")

        assert resp.status_code == 200
        profile.refresh_from_db()
        assert profile.wizard_step == 3

    def test_sets_onboarding_status_in_progress(self, api_client):
        trainer = TrainerFactory()
        TrainerProfileFactory(user=trainer, wizard_step=0)
        api_client.force_authenticate(user=trainer)

        resp = api_client.patch(STEP_URL, {"step": 1}, format="json")

        assert resp.status_code == 200
        trainer.refresh_from_db()
        assert trainer.onboarding_status == "in_progress"

    def test_invalid_step_returns_400(self, api_client):
        trainer = TrainerFactory()
        TrainerProfileFactory(user=trainer)
        api_client.force_authenticate(user=trainer)

        resp = api_client.patch(STEP_URL, {"step": 6}, format="json")

        assert resp.status_code == 400

    def test_client_cannot_call_step_endpoint(self, api_client):
        client = ClientFactory()
        api_client.force_authenticate(user=client)

        resp = api_client.patch(STEP_URL, {"step": 1}, format="json")

        assert resp.status_code == 403


@pytest.mark.django_db
class TestOnboardingCompleteView:

    def test_sets_wizard_step_5(self, api_client):
        trainer = TrainerFactory()
        profile = TrainerProfileFactory(user=trainer, wizard_step=4)
        api_client.force_authenticate(user=trainer)

        resp = api_client.post(COMPLETE_URL)

        assert resp.status_code == 200
        profile.refresh_from_db()
        assert profile.wizard_step == 5

    def test_sets_onboarding_status_completed(self, api_client):
        trainer = TrainerFactory()
        TrainerProfileFactory(user=trainer, wizard_step=4)
        api_client.force_authenticate(user=trainer)

        resp = api_client.post(COMPLETE_URL)

        assert resp.status_code == 200
        trainer.refresh_from_db()
        assert trainer.onboarding_status == "completed"

    def test_sets_onboarding_completed_at(self, api_client):
        trainer = TrainerFactory()
        TrainerProfileFactory(user=trainer, wizard_step=4)
        api_client.force_authenticate(user=trainer)

        resp = api_client.post(COMPLETE_URL)

        assert resp.status_code == 200
        trainer.refresh_from_db()
        assert trainer.onboarding_completed_at is not None

    def test_client_cannot_call_complete_endpoint(self, api_client):
        client = ClientFactory()
        api_client.force_authenticate(user=client)

        resp = api_client.post(COMPLETE_URL)

        assert resp.status_code == 403
