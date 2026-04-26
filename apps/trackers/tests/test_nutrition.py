"""Tests for nutrition tracker endpoints."""

from datetime import date

import pytest

NUTRITION_URL = "/api/v1/trackers/nutrition/"


@pytest.mark.django_db
class TestNutritionPermissions:
    def test_unauthenticated_list_returns_401(self, anon_client):
        resp = anon_client.get(NUTRITION_URL)
        assert resp.status_code == 401

    def test_unauthenticated_create_returns_401(self, anon_client):
        resp = anon_client.post(NUTRITION_URL, {}, format="json")
        assert resp.status_code == 401

    def test_trainer_returns_403(self, trainer_user):
        _, _, api = trainer_user
        resp = api.get(NUTRITION_URL)
        assert resp.status_code == 403

    def test_client_without_addon_returns_403(self, client_no_addon):
        _, _, api = client_no_addon
        resp = api.get(NUTRITION_URL)
        assert resp.status_code == 403

    def test_client_with_addon_can_list(self, client_with_addon):
        _, _, api = client_with_addon
        resp = api.get(NUTRITION_URL)
        assert resp.status_code == 200
        assert resp.data["status"] == "success"


@pytest.mark.django_db
class TestNutritionLogCreate:
    def test_new_date_returns_201(self, client_with_addon):
        _, _, api = client_with_addon
        payload = {
            "date": "2025-06-01",
            "calorie_goal": 2000,
            "protein_goal_g": "150.00",
            "carbs_goal_g": "200.00",
            "fat_goal_g": "65.00",
        }
        resp = api.post(NUTRITION_URL, payload, format="json")
        assert resp.status_code == 201
        assert resp.data["data"]["calorie_goal"] == 2000

    def test_same_date_returns_200_and_updates(self, client_with_addon):
        _, _, api = client_with_addon
        api.post(
            NUTRITION_URL, {"date": "2025-06-01", "calorie_goal": 2000}, format="json"
        )
        resp = api.post(
            NUTRITION_URL, {"date": "2025-06-01", "calorie_goal": 2200}, format="json"
        )
        assert resp.status_code == 200
        assert resp.data["data"]["calorie_goal"] == 2200

    def test_all_goal_fields_optional(self, client_with_addon):
        _, _, api = client_with_addon
        resp = api.post(NUTRITION_URL, {"date": "2025-06-02"}, format="json")
        assert resp.status_code == 201

    def test_sets_client_from_auth_user(self, client_with_addon):
        user, profile, api = client_with_addon
        resp = api.post(NUTRITION_URL, {"date": "2025-06-03"}, format="json")
        from apps.trackers.models import DailyNutritionLog

        log = DailyNutritionLog.objects.get(id=resp.data["data"]["id"])
        assert log.client == profile


@pytest.mark.django_db
class TestNutritionLogList:
    def test_list_is_paginated(self, client_with_addon):
        _, _, api = client_with_addon
        resp = api.get(NUTRITION_URL)
        assert "pagination" in resp.data["meta"]

    def test_list_scoped_to_authenticated_client(
        self, client_with_addon, client2_with_addon
    ):
        from apps.trackers.tests.factories import DailyNutritionLogFactory

        _, profile, api = client_with_addon
        _, profile2, _ = client2_with_addon
        log1 = DailyNutritionLogFactory(client=profile, date=date(2025, 1, 10))
        log2 = DailyNutritionLogFactory(client=profile2, date=date(2025, 1, 10))

        resp = api.get(NUTRITION_URL)
        ids = [item["id"] for item in resp.data["data"]]
        assert str(log1.id) in ids
        assert str(log2.id) not in ids

    def test_date_filter_returns_matching_logs(self, client_with_addon):
        from apps.trackers.tests.factories import DailyNutritionLogFactory

        _, profile, api = client_with_addon
        DailyNutritionLogFactory(client=profile, date=date(2025, 1, 15))
        DailyNutritionLogFactory(client=profile, date=date(2025, 2, 15))

        resp = api.get(NUTRITION_URL, {"date": "2025-01-15"})
        assert len(resp.data["data"]) == 1
        assert resp.data["data"][0]["date"] == "2025-01-15"


@pytest.mark.django_db
class TestNutritionLogDetail:
    def test_returns_log_with_meals_and_totals(self, client_with_addon):
        from apps.trackers.tests.factories import (
            DailyNutritionLogFactory,
            MealEntryFactory,
        )

        _, profile, api = client_with_addon
        log = DailyNutritionLogFactory(
            client=profile, date=date(2025, 1, 15), calorie_goal=2000
        )
        MealEntryFactory(
            nutrition_log=log,
            calories=389,
            protein_g="13.00",
            carbs_g="66.00",
            fat_g="7.00",
        )

        resp = api.get(f"{NUTRITION_URL}{log.id}/")
        assert resp.status_code == 200
        d = resp.data["data"]
        assert "meals" in d
        assert "total_calories" in d
        assert "total_protein_g" in d
        assert "total_carbs_g" in d
        assert "total_fat_g" in d
        assert d["total_calories"] == 389

    def test_goal_progress_null_when_no_goal(self, client_with_addon):
        from apps.trackers.tests.factories import DailyNutritionLogFactory

        _, profile, api = client_with_addon
        log = DailyNutritionLogFactory(client=profile, calorie_goal=None)
        resp = api.get(f"{NUTRITION_URL}{log.id}/")
        assert resp.data["data"]["goal_progress"] is None

    def test_goal_progress_calculated_correctly(self, client_with_addon):
        from apps.trackers.tests.factories import (
            DailyNutritionLogFactory,
            MealEntryFactory,
        )

        _, profile, api = client_with_addon
        log = DailyNutritionLogFactory(client=profile, calorie_goal=2000)
        MealEntryFactory(nutrition_log=log, calories=1800)

        resp = api.get(f"{NUTRITION_URL}{log.id}/")
        assert resp.data["data"]["goal_progress"] == 90.0

    def test_other_client_returns_404(self, client_with_addon, client2_with_addon):
        from apps.trackers.tests.factories import DailyNutritionLogFactory

        _, profile2, _ = client2_with_addon
        _, _, api = client_with_addon
        log = DailyNutritionLogFactory(client=profile2)
        resp = api.get(f"{NUTRITION_URL}{log.id}/")
        assert resp.status_code == 404

    def test_nonexistent_log_returns_404(self, client_with_addon):
        _, _, api = client_with_addon
        resp = api.get(f"{NUTRITION_URL}00000000-0000-0000-0000-000000000000/")
        assert resp.status_code == 404


@pytest.mark.django_db
class TestNutritionLogUpdate:
    def test_put_updates_goals(self, client_with_addon):
        from apps.trackers.tests.factories import DailyNutritionLogFactory

        _, profile, api = client_with_addon
        log = DailyNutritionLogFactory(client=profile, calorie_goal=2000)

        resp = api.put(
            f"{NUTRITION_URL}{log.id}/",
            {"calorie_goal": 2500, "protein_goal_g": "160.00"},
            format="json",
        )
        assert resp.status_code == 200
        assert resp.data["data"]["calorie_goal"] == 2500

    def test_put_other_client_returns_404(self, client_with_addon, client2_with_addon):
        from apps.trackers.tests.factories import DailyNutritionLogFactory

        _, profile2, _ = client2_with_addon
        _, _, api = client_with_addon
        log = DailyNutritionLogFactory(client=profile2)

        resp = api.put(
            f"{NUTRITION_URL}{log.id}/", {"calorie_goal": 999}, format="json"
        )
        assert resp.status_code == 404


@pytest.mark.django_db
class TestMealEntries:
    def test_add_meal_returns_201(self, client_with_addon):
        from apps.trackers.tests.factories import DailyNutritionLogFactory

        _, profile, api = client_with_addon
        log = DailyNutritionLogFactory(client=profile)

        payload = {
            "meal_type": "breakfast",
            "food_name": "Oats",
            "quantity": "100.00",
            "unit": "g",
            "calories": 389,
            "protein_g": "13.00",
            "carbs_g": "66.00",
            "fat_g": "7.00",
        }
        resp = api.post(f"{NUTRITION_URL}{log.id}/meals/", payload, format="json")
        assert resp.status_code == 201
        assert resp.data["data"]["food_name"] == "Oats"

    def test_add_meal_to_other_client_log_returns_404(
        self, client_with_addon, client2_with_addon
    ):
        from apps.trackers.tests.factories import DailyNutritionLogFactory

        _, profile2, _ = client2_with_addon
        _, _, api = client_with_addon
        log = DailyNutritionLogFactory(client=profile2)

        payload = {
            "meal_type": "lunch",
            "food_name": "Rice",
            "quantity": "150.00",
            "unit": "g",
            "calories": 200,
        }
        resp = api.post(f"{NUTRITION_URL}{log.id}/meals/", payload, format="json")
        assert resp.status_code == 404

    def test_delete_meal_returns_204(self, client_with_addon):
        from apps.trackers.tests.factories import (
            DailyNutritionLogFactory,
            MealEntryFactory,
        )

        _, profile, api = client_with_addon
        log = DailyNutritionLogFactory(client=profile)
        meal = MealEntryFactory(nutrition_log=log)

        resp = api.delete(f"{NUTRITION_URL}{log.id}/meals/{meal.id}/")
        assert resp.status_code == 204

    def test_delete_meal_removes_it(self, client_with_addon):
        from apps.trackers.models import MealEntry
        from apps.trackers.tests.factories import (
            DailyNutritionLogFactory,
            MealEntryFactory,
        )

        _, profile, api = client_with_addon
        log = DailyNutritionLogFactory(client=profile)
        meal = MealEntryFactory(nutrition_log=log)

        api.delete(f"{NUTRITION_URL}{log.id}/meals/{meal.id}/")
        assert not MealEntry.objects.filter(id=meal.id).exists()

    def test_delete_meal_from_other_client_log_returns_404(
        self, client_with_addon, client2_with_addon
    ):
        from apps.trackers.tests.factories import (
            DailyNutritionLogFactory,
            MealEntryFactory,
        )

        _, profile2, _ = client2_with_addon
        _, _, api = client_with_addon
        log = DailyNutritionLogFactory(client=profile2)
        meal = MealEntryFactory(nutrition_log=log)

        resp = api.delete(f"{NUTRITION_URL}{log.id}/meals/{meal.id}/")
        assert resp.status_code == 404
