"""
Tests for role-specific onboarding flows.
"""

import pytest
from rest_framework.test import APIClient

from apps.accounts.tests.factories import ClientFactory, GymFactory, TrainerFactory
from apps.profiles.tests.factories import (
    ClientProfileFactory,
    GymProfileFactory,
    SpecialisationFactory,
    TrainerProfileFactory,
)

TRAINER_EXPERTISE_URL = "/api/v1/onboarding/trainer/expertise/"
TRAINER_PRODUCTS_URL = "/api/v1/onboarding/trainer/products/"
GYM_SERVICES_URL = "/api/v1/onboarding/gym/services/"
GYM_PRODUCTS_URL = "/api/v1/onboarding/gym/products/"
CLIENT_GOAL_URL = "/api/v1/onboarding/client/goal/"
CLIENT_FOCUS_URL = "/api/v1/onboarding/client/focus/"
GOALS_LIST_URL = "/api/v1/onboarding/goals/"


@pytest.fixture
def api_client():
    return APIClient()


# ---------------------------------------------------------------------------
# Goals list (public)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestGoalListView:
    def test_returns_predefined_goals(self, api_client):
        resp = api_client.get(GOALS_LIST_URL)
        assert resp.status_code == 200
        data = resp.data["data"]
        assert len(data) == 6  # seeded in migration

    def test_no_auth_required(self, api_client):
        resp = api_client.get(GOALS_LIST_URL)
        assert resp.status_code == 200

    def test_response_has_expected_fields(self, api_client):
        resp = api_client.get(GOALS_LIST_URL)
        assert resp.status_code == 200
        first = resp.data["data"][0]
        assert "id" in first
        assert "name" in first
        assert "slug" in first
        assert "is_predefined" in first


# ---------------------------------------------------------------------------
# Trainer expertise
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTrainerExpertiseView:
    def test_unauthenticated_returns_401(self, api_client):
        resp = api_client.get(TRAINER_EXPERTISE_URL)
        assert resp.status_code == 401

    def test_unauthenticated_post_returns_401(self, api_client):
        resp = api_client.post(TRAINER_EXPERTISE_URL, {}, format="json")
        assert resp.status_code == 401

    def test_gym_user_returns_403(self, api_client):
        gym = GymFactory()
        GymProfileFactory(user=gym)
        api_client.force_authenticate(user=gym)
        resp = api_client.get(TRAINER_EXPERTISE_URL)
        assert resp.status_code == 403

    def test_client_user_returns_403(self, api_client):
        client = ClientFactory()
        ClientProfileFactory(user=client)
        api_client.force_authenticate(user=client)
        resp = api_client.get(TRAINER_EXPERTISE_URL)
        assert resp.status_code == 403

    def test_trainer_get_no_expertise_returns_empty_list(self, api_client):
        trainer = TrainerFactory()
        TrainerProfileFactory(user=trainer)
        api_client.force_authenticate(user=trainer)
        resp = api_client.get(TRAINER_EXPERTISE_URL)
        assert resp.status_code == 200
        assert resp.data["data"]["expertise"] == []

    def test_trainer_post_valid_expertise_ids(self, api_client):
        trainer = TrainerFactory()
        TrainerProfileFactory(user=trainer)
        s1 = SpecialisationFactory(name="Yoga")
        s2 = SpecialisationFactory(name="HIIT")
        api_client.force_authenticate(user=trainer)
        resp = api_client.post(
            TRAINER_EXPERTISE_URL,
            {"expertise_ids": [s1.id, s2.id], "custom_names": []},
            format="json",
        )
        assert resp.status_code == 200
        assert len(resp.data["data"]["expertise"]) == 2
        assert resp.data["data"]["onboarding_step"] == 1

    def test_trainer_post_sets_onboarding_step_1(self, api_client):
        trainer = TrainerFactory()
        TrainerProfileFactory(user=trainer)
        s1 = SpecialisationFactory(name="Pilates")
        api_client.force_authenticate(user=trainer)
        api_client.post(
            TRAINER_EXPERTISE_URL,
            {"expertise_ids": [s1.id], "custom_names": []},
            format="json",
        )
        trainer.refresh_from_db()
        assert trainer.onboarding_step == 1

    def test_trainer_post_custom_names_creates_specialisation(self, api_client):
        trainer = TrainerFactory()
        TrainerProfileFactory(user=trainer)
        api_client.force_authenticate(user=trainer)
        resp = api_client.post(
            TRAINER_EXPERTISE_URL,
            {"expertise_ids": [], "custom_names": ["Animal Flow"]},
            format="json",
        )
        assert resp.status_code == 200
        assert any(s["name"] == "Animal Flow" for s in resp.data["data"]["expertise"])

    def test_trainer_post_exceeding_10_returns_400(self, api_client):
        trainer = TrainerFactory()
        TrainerProfileFactory(user=trainer)
        specs = [SpecialisationFactory().id for _ in range(11)]
        api_client.force_authenticate(user=trainer)
        resp = api_client.post(
            TRAINER_EXPERTISE_URL,
            {"expertise_ids": specs, "custom_names": []},
            format="json",
        )
        assert resp.status_code == 400

    def test_trainer_get_after_post_returns_attached_expertise(self, api_client):
        trainer = TrainerFactory()
        TrainerProfileFactory(user=trainer)
        s1 = SpecialisationFactory(name="Boxing")
        api_client.force_authenticate(user=trainer)
        api_client.post(
            TRAINER_EXPERTISE_URL,
            {"expertise_ids": [s1.id], "custom_names": []},
            format="json",
        )
        resp = api_client.get(TRAINER_EXPERTISE_URL)
        assert resp.status_code == 200
        names = [s["name"] for s in resp.data["data"]["expertise"]]
        assert "Boxing" in names

    def test_trainer_post_sets_onboarding_status_in_progress(self, api_client):
        trainer = TrainerFactory()
        TrainerProfileFactory(user=trainer)
        s1 = SpecialisationFactory(name="Zumba")
        api_client.force_authenticate(user=trainer)
        api_client.post(
            TRAINER_EXPERTISE_URL,
            {"expertise_ids": [s1.id], "custom_names": []},
            format="json",
        )
        trainer.refresh_from_db()
        assert trainer.onboarding_status == "in_progress"


# ---------------------------------------------------------------------------
# Trainer products
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTrainerProductsView:
    def test_unauthenticated_returns_401(self, api_client):
        resp = api_client.post(TRAINER_PRODUCTS_URL, {}, format="json")
        assert resp.status_code == 401

    def test_gym_user_returns_403(self, api_client):
        gym = GymFactory()
        GymProfileFactory(user=gym)
        api_client.force_authenticate(user=gym)
        resp = api_client.post(
            TRAINER_PRODUCTS_URL, {"offers_products": True}, format="json"
        )
        assert resp.status_code == 403

    def test_client_user_returns_403(self, api_client):
        client = ClientFactory()
        ClientProfileFactory(user=client)
        api_client.force_authenticate(user=client)
        resp = api_client.post(
            TRAINER_PRODUCTS_URL, {"offers_products": True}, format="json"
        )
        assert resp.status_code == 403

    def test_trainer_post_offers_products_true(self, api_client):
        trainer = TrainerFactory()
        TrainerProfileFactory(user=trainer)
        api_client.force_authenticate(user=trainer)
        resp = api_client.post(
            TRAINER_PRODUCTS_URL, {"offers_products": True}, format="json"
        )
        assert resp.status_code == 200
        assert resp.data["data"]["offers_products"] is True
        assert resp.data["data"]["is_published"] is True
        assert resp.data["data"]["onboarding_step"] == 2

    def test_trainer_post_offers_products_false_still_publishes(self, api_client):
        trainer = TrainerFactory()
        TrainerProfileFactory(user=trainer)
        api_client.force_authenticate(user=trainer)
        resp = api_client.post(
            TRAINER_PRODUCTS_URL, {"offers_products": False}, format="json"
        )
        assert resp.status_code == 200
        assert resp.data["data"]["is_published"] is True

    def test_trainer_post_completes_onboarding(self, api_client):
        trainer = TrainerFactory()
        TrainerProfileFactory(user=trainer)
        api_client.force_authenticate(user=trainer)
        api_client.post(TRAINER_PRODUCTS_URL, {"offers_products": True}, format="json")
        trainer.refresh_from_db()
        assert trainer.onboarding_status == "completed"
        assert trainer.onboarding_step == 2

    def test_trainer_get_returns_current_offers_products(self, api_client):
        trainer = TrainerFactory()
        TrainerProfileFactory(user=trainer, offers_products=True)
        api_client.force_authenticate(user=trainer)
        resp = api_client.get(TRAINER_PRODUCTS_URL)
        assert resp.status_code == 200
        assert resp.data["data"]["offers_products"] is True


# ---------------------------------------------------------------------------
# Gym services
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestGymServicesView:
    def test_unauthenticated_returns_401(self, api_client):
        resp = api_client.get(GYM_SERVICES_URL)
        assert resp.status_code == 401

    def test_trainer_returns_403(self, api_client):
        trainer = TrainerFactory()
        TrainerProfileFactory(user=trainer)
        api_client.force_authenticate(user=trainer)
        resp = api_client.get(GYM_SERVICES_URL)
        assert resp.status_code == 403

    def test_client_returns_403(self, api_client):
        client = ClientFactory()
        ClientProfileFactory(user=client)
        api_client.force_authenticate(user=client)
        resp = api_client.get(GYM_SERVICES_URL)
        assert resp.status_code == 403

    def test_gym_post_creates_services(self, api_client):
        gym = GymFactory()
        GymProfileFactory(user=gym)
        api_client.force_authenticate(user=gym)
        payload = {
            "services": [
                {
                    "name": "Personal Training",
                    "description": "1-on-1",
                    "session_type": "physical",
                    "display_order": 1,
                }
            ]
        }
        resp = api_client.post(GYM_SERVICES_URL, payload, format="json")
        assert resp.status_code == 200
        assert len(resp.data["data"]["services"]) == 1
        assert resp.data["data"]["onboarding_step"] == 1

    def test_gym_post_replaces_existing_services(self, api_client):
        from apps.profiles.tests.factories import ServiceGymFactory

        gym = GymFactory()
        gym_profile = GymProfileFactory(user=gym)
        ServiceGymFactory(gym=gym_profile, name="Old Service")
        api_client.force_authenticate(user=gym)
        payload = {"services": [{"name": "New Service", "session_type": "virtual"}]}
        resp = api_client.post(GYM_SERVICES_URL, payload, format="json")
        assert resp.status_code == 200
        names = [s["name"] for s in resp.data["data"]["services"]]
        assert "New Service" in names
        assert "Old Service" not in names

    def test_gym_get_returns_current_services(self, api_client):
        from apps.profiles.tests.factories import ServiceGymFactory

        gym = GymFactory()
        gym_profile = GymProfileFactory(user=gym)
        ServiceGymFactory(gym=gym_profile, name="Yoga Class")
        api_client.force_authenticate(user=gym)
        resp = api_client.get(GYM_SERVICES_URL)
        assert resp.status_code == 200
        names = [s["name"] for s in resp.data["data"]["services"]]
        assert "Yoga Class" in names

    def test_gym_post_sets_onboarding_in_progress(self, api_client):
        gym = GymFactory()
        GymProfileFactory(user=gym)
        api_client.force_authenticate(user=gym)
        api_client.post(
            GYM_SERVICES_URL,
            {"services": [{"name": "Crossfit", "session_type": "physical"}]},
            format="json",
        )
        gym.refresh_from_db()
        assert gym.onboarding_status == "in_progress"
        assert gym.onboarding_step == 1


# ---------------------------------------------------------------------------
# Gym products
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestGymProductsView:
    def test_unauthenticated_returns_401(self, api_client):
        resp = api_client.post(GYM_PRODUCTS_URL, {}, format="json")
        assert resp.status_code == 401

    def test_trainer_returns_403(self, api_client):
        trainer = TrainerFactory()
        TrainerProfileFactory(user=trainer)
        api_client.force_authenticate(user=trainer)
        resp = api_client.post(
            GYM_PRODUCTS_URL, {"offers_products": True}, format="json"
        )
        assert resp.status_code == 403

    def test_client_returns_403(self, api_client):
        client = ClientFactory()
        ClientProfileFactory(user=client)
        api_client.force_authenticate(user=client)
        resp = api_client.post(
            GYM_PRODUCTS_URL, {"offers_products": True}, format="json"
        )
        assert resp.status_code == 403

    def test_gym_post_completes_onboarding(self, api_client):
        gym = GymFactory()
        GymProfileFactory(user=gym)
        api_client.force_authenticate(user=gym)
        resp = api_client.post(
            GYM_PRODUCTS_URL, {"offers_products": True}, format="json"
        )
        assert resp.status_code == 200
        assert resp.data["data"]["offers_products"] is True
        assert resp.data["data"]["is_published"] is True
        assert resp.data["data"]["onboarding_step"] == 2
        gym.refresh_from_db()
        assert gym.onboarding_status == "completed"

    def test_gym_get_returns_current_offers_products(self, api_client):
        gym = GymFactory()
        GymProfileFactory(user=gym, offers_products=False)
        api_client.force_authenticate(user=gym)
        resp = api_client.get(GYM_PRODUCTS_URL)
        assert resp.status_code == 200
        assert resp.data["data"]["offers_products"] is False


# ---------------------------------------------------------------------------
# Client goal
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestClientGoalView:
    def _goal_detail_url(self, goal_id):
        return f"/api/v1/onboarding/client/goal/{goal_id}/"

    def test_unauthenticated_returns_401(self, api_client):
        resp = api_client.get(CLIENT_GOAL_URL)
        assert resp.status_code == 401

    def test_trainer_returns_403(self, api_client):
        trainer = TrainerFactory()
        TrainerProfileFactory(user=trainer)
        api_client.force_authenticate(user=trainer)
        resp = api_client.get(CLIENT_GOAL_URL)
        assert resp.status_code == 403

    def test_gym_returns_403(self, api_client):
        gym = GymFactory()
        GymProfileFactory(user=gym)
        api_client.force_authenticate(user=gym)
        resp = api_client.get(CLIENT_GOAL_URL)
        assert resp.status_code == 403

    def test_client_get_no_goals_returns_empty_list(self, api_client):
        client = ClientFactory()
        ClientProfileFactory(user=client)
        api_client.force_authenticate(user=client)
        resp = api_client.get(CLIENT_GOAL_URL)
        assert resp.status_code == 200
        assert resp.data["data"]["goals"] == []

    def test_client_post_valid_goal_ids(self, api_client):
        from apps.profiles.models import Goal

        client = ClientFactory()
        ClientProfileFactory(user=client)
        g1 = Goal.objects.create(name="Build Muscle Test", is_predefined=True)
        g2 = Goal.objects.create(name="Lose Weight Test", is_predefined=True)
        api_client.force_authenticate(user=client)
        resp = api_client.post(
            CLIENT_GOAL_URL,
            {"goal_ids": [g1.id, g2.id], "custom_names": []},
            format="json",
        )
        assert resp.status_code == 200
        assert len(resp.data["data"]["goals"]) == 2
        assert resp.data["data"]["onboarding_step"] == 1

    def test_client_post_custom_names_creates_goal(self, api_client):
        client = ClientFactory()
        ClientProfileFactory(user=client)
        api_client.force_authenticate(user=client)
        resp = api_client.post(
            CLIENT_GOAL_URL,
            {"goal_ids": [], "custom_names": ["Run a Marathon"]},
            format="json",
        )
        assert resp.status_code == 200
        names = [g["name"] for g in resp.data["data"]["goals"]]
        assert "Run a Marathon" in names

    def test_client_post_exceeding_6_returns_400(self, api_client):
        from apps.profiles.models import Goal

        client = ClientFactory()
        ClientProfileFactory(user=client)
        goals = [Goal.objects.create(name=f"Goal Limit {i}") for i in range(7)]
        api_client.force_authenticate(user=client)
        resp = api_client.post(
            CLIENT_GOAL_URL,
            {"goal_ids": [g.id for g in goals], "custom_names": []},
            format="json",
        )
        assert resp.status_code == 400

    def test_client_delete_goal_returns_204(self, api_client):
        from apps.profiles.models import Goal

        client = ClientFactory()
        cp = ClientProfileFactory(user=client)
        goal = Goal.objects.create(name="Dance For Fun", is_predefined=False)
        cp.primary_goals.add(goal)
        api_client.force_authenticate(user=client)
        resp = api_client.delete(self._goal_detail_url(goal.id))
        assert resp.status_code == 204
        assert not cp.primary_goals.filter(id=goal.id).exists()

    def test_client_delete_goal_not_attached_returns_404(self, api_client):
        from apps.profiles.models import Goal

        client = ClientFactory()
        ClientProfileFactory(user=client)
        goal = Goal.objects.create(name="Swim Daily", is_predefined=False)
        api_client.force_authenticate(user=client)
        resp = api_client.delete(self._goal_detail_url(goal.id))
        assert resp.status_code == 404

    def test_client_post_sets_onboarding_in_progress(self, api_client):
        from apps.profiles.models import Goal

        client = ClientFactory()
        ClientProfileFactory(user=client)
        goal = Goal.objects.create(name="Sleep Better", is_predefined=False)
        api_client.force_authenticate(user=client)
        api_client.post(
            CLIENT_GOAL_URL,
            {"goal_ids": [goal.id], "custom_names": []},
            format="json",
        )
        client.refresh_from_db()
        assert client.onboarding_status == "in_progress"
        assert client.onboarding_step == 1


# ---------------------------------------------------------------------------
# Client focus
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestClientFocusView:
    def _focus_detail_url(self, spec_id):
        return f"/api/v1/onboarding/client/focus/{spec_id}/"

    def test_unauthenticated_returns_401(self, api_client):
        resp = api_client.get(CLIENT_FOCUS_URL)
        assert resp.status_code == 401

    def test_trainer_returns_403(self, api_client):
        trainer = TrainerFactory()
        TrainerProfileFactory(user=trainer)
        api_client.force_authenticate(user=trainer)
        resp = api_client.get(CLIENT_FOCUS_URL)
        assert resp.status_code == 403

    def test_gym_returns_403(self, api_client):
        gym = GymFactory()
        GymProfileFactory(user=gym)
        api_client.force_authenticate(user=gym)
        resp = api_client.get(CLIENT_FOCUS_URL)
        assert resp.status_code == 403

    def test_client_get_no_focus_returns_empty_list(self, api_client):
        client = ClientFactory()
        ClientProfileFactory(user=client)
        api_client.force_authenticate(user=client)
        resp = api_client.get(CLIENT_FOCUS_URL)
        assert resp.status_code == 200
        assert resp.data["data"]["specialisations"] == []

    def test_client_post_valid_specialisation_ids(self, api_client):
        client = ClientFactory()
        ClientProfileFactory(user=client)
        s1 = SpecialisationFactory(name="Strength Training")
        s2 = SpecialisationFactory(name="Cardio")
        api_client.force_authenticate(user=client)
        resp = api_client.post(
            CLIENT_FOCUS_URL,
            {"specialisation_ids": [s1.id, s2.id], "custom_names": []},
            format="json",
        )
        assert resp.status_code == 200
        assert len(resp.data["data"]["specialisations"]) == 2
        assert resp.data["data"]["onboarding_step"] == 2

    def test_client_post_completes_onboarding(self, api_client):
        client = ClientFactory()
        ClientProfileFactory(user=client)
        s1 = SpecialisationFactory(name="Flexibility")
        api_client.force_authenticate(user=client)
        api_client.post(
            CLIENT_FOCUS_URL,
            {"specialisation_ids": [s1.id], "custom_names": []},
            format="json",
        )
        client.refresh_from_db()
        assert client.onboarding_status == "completed"
        assert client.onboarding_step == 2

    def test_client_delete_focus_returns_204(self, api_client):
        client = ClientFactory()
        cp = ClientProfileFactory(user=client)
        spec = SpecialisationFactory(name="Cycling")
        cp.specialisations.add(spec)
        api_client.force_authenticate(user=client)
        resp = api_client.delete(self._focus_detail_url(spec.id))
        assert resp.status_code == 204
        assert not cp.specialisations.filter(id=spec.id).exists()

    def test_client_delete_focus_not_attached_returns_404(self, api_client):
        client = ClientFactory()
        ClientProfileFactory(user=client)
        spec = SpecialisationFactory(name="Swimming")
        api_client.force_authenticate(user=client)
        resp = api_client.delete(self._focus_detail_url(spec.id))
        assert resp.status_code == 404

    def test_client_post_exceeding_10_returns_400(self, api_client):
        client = ClientFactory()
        ClientProfileFactory(user=client)
        specs = [SpecialisationFactory().id for _ in range(11)]
        api_client.force_authenticate(user=client)
        resp = api_client.post(
            CLIENT_FOCUS_URL,
            {"specialisation_ids": specs, "custom_names": []},
            format="json",
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Login response after onboarding
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestLoginOnboardingResponse:
    LOGIN_URL = "/api/v1/auth/login/"

    def test_trainer_step_0_in_login_response(self, api_client):
        trainer = TrainerFactory()
        TrainerProfileFactory(user=trainer)
        trainer.set_password("ValidPass123!")
        trainer.is_email_verified = True
        trainer.save()
        resp = api_client.post(
            self.LOGIN_URL,
            {"email": trainer.email, "password": "ValidPass123!"},
            format="json",
        )
        assert resp.status_code == 200
        onboarding = resp.data["data"]["onboarding"]
        assert onboarding["current_step"] == 0
        assert onboarding["is_profile_published"] is False
        assert onboarding["total_steps"] == 2

    def test_trainer_after_completing_step2(self, api_client):
        trainer = TrainerFactory()
        TrainerProfileFactory(user=trainer, is_published=True, offers_products=True)
        trainer.onboarding_step = 2
        trainer.set_password("ValidPass123!")
        trainer.is_email_verified = True
        trainer.save()
        resp = api_client.post(
            self.LOGIN_URL,
            {"email": trainer.email, "password": "ValidPass123!"},
            format="json",
        )
        assert resp.status_code == 200
        onboarding = resp.data["data"]["onboarding"]
        assert onboarding["current_step"] == 2
        assert onboarding["is_profile_published"] is True

    def test_client_after_completing_step2(self, api_client):
        client = ClientFactory()
        ClientProfileFactory(user=client)
        client.onboarding_step = 2
        client.set_password("ValidPass123!")
        client.is_email_verified = True
        client.save()
        resp = api_client.post(
            self.LOGIN_URL,
            {"email": client.email, "password": "ValidPass123!"},
            format="json",
        )
        assert resp.status_code == 200
        onboarding = resp.data["data"]["onboarding"]
        assert onboarding["current_step"] == 2
        assert onboarding["is_profile_published"] is False

    def test_login_response_has_no_needs_specialisation(self, api_client):
        trainer = TrainerFactory()
        TrainerProfileFactory(user=trainer)
        trainer.set_password("ValidPass123!")
        trainer.is_email_verified = True
        trainer.save()
        resp = api_client.post(
            self.LOGIN_URL,
            {"email": trainer.email, "password": "ValidPass123!"},
            format="json",
        )
        assert resp.status_code == 200
        onboarding = resp.data["data"]["onboarding"]
        assert "needs_specialisation" not in onboarding

    def test_login_response_has_no_profile_completion_percentage(self, api_client):
        trainer = TrainerFactory()
        TrainerProfileFactory(user=trainer)
        trainer.set_password("ValidPass123!")
        trainer.is_email_verified = True
        trainer.save()
        resp = api_client.post(
            self.LOGIN_URL,
            {"email": trainer.email, "password": "ValidPass123!"},
            format="json",
        )
        assert resp.status_code == 200
        onboarding = resp.data["data"]["onboarding"]
        assert "profile_completion_percentage" not in onboarding
