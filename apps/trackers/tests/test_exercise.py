"""Tests for exercise tracker endpoints."""

from datetime import date

import pytest

EXERCISE_URL = "/api/v1/trackers/exercise/"
RECORDS_URL = "/api/v1/trackers/exercise/records/"


@pytest.mark.django_db
class TestExercisePermissions:
    def test_unauthenticated_list_returns_401(self, anon_client):
        resp = anon_client.get(EXERCISE_URL)
        assert resp.status_code == 401

    def test_unauthenticated_create_returns_401(self, anon_client):
        resp = anon_client.post(EXERCISE_URL, {}, format="json")
        assert resp.status_code == 401

    def test_trainer_list_returns_403(self, trainer_user):
        _, _, api = trainer_user
        resp = api.get(EXERCISE_URL)
        assert resp.status_code == 403

    def test_client_without_addon_list_returns_403(self, client_no_addon):
        _, _, api = client_no_addon
        resp = api.get(EXERCISE_URL)
        assert resp.status_code == 403

    def test_client_without_addon_create_returns_403(self, client_no_addon):
        _, _, api = client_no_addon
        resp = api.post(
            EXERCISE_URL,
            {"date": str(date.today()), "exercises": [{"name": "Squat"}]},
            format="json",
        )
        assert resp.status_code == 403

    def test_client_with_addon_can_list(self, client_with_addon):
        _, _, api = client_with_addon
        resp = api.get(EXERCISE_URL)
        assert resp.status_code == 200
        assert resp.data["status"] == "success"
        assert isinstance(resp.data["data"], list)


@pytest.mark.django_db
class TestWorkoutLogCreate:
    def test_create_returns_201_with_exercises(self, client_with_addon):
        _, _, api = client_with_addon
        payload = {
            "date": str(date.today()),
            "notes": "Leg day",
            "exercises": [
                {"name": "Squat", "sets": 3, "reps": 10, "weight_kg": "80.00"},
                {"name": "Leg Press", "sets": 4, "reps": 12, "weight_kg": "120.00"},
            ],
        }
        resp = api.post(EXERCISE_URL, payload, format="json")
        assert resp.status_code == 201
        assert resp.data["status"] == "success"
        assert resp.data["data"]["notes"] == "Leg day"
        assert len(resp.data["data"]["exercises"]) == 2

    def test_create_empty_exercises_returns_400(self, client_with_addon):
        _, _, api = client_with_addon
        payload = {"date": str(date.today()), "exercises": []}
        resp = api.post(EXERCISE_URL, payload, format="json")
        assert resp.status_code == 400

    def test_create_exercise_without_name_returns_400(self, client_with_addon):
        _, _, api = client_with_addon
        payload = {
            "date": str(date.today()),
            "exercises": [{"sets": 3, "reps": 10}],
        }
        resp = api.post(EXERCISE_URL, payload, format="json")
        assert resp.status_code == 400

    def test_create_sets_client_from_auth_user(self, client_with_addon):
        user, profile, api = client_with_addon
        payload = {
            "date": str(date.today()),
            "exercises": [{"name": "Push-up", "sets": 3, "reps": 20}],
        }
        resp = api.post(EXERCISE_URL, payload, format="json")
        assert resp.status_code == 201
        from apps.trackers.models import WorkoutLog

        log = WorkoutLog.objects.get(id=resp.data["data"]["id"])
        assert log.client == profile

    def test_create_without_weight_is_valid(self, client_with_addon):
        _, _, api = client_with_addon
        payload = {
            "date": str(date.today()),
            "exercises": [{"name": "Push-up", "sets": 3, "reps": 20}],
        }
        resp = api.post(EXERCISE_URL, payload, format="json")
        assert resp.status_code == 201
        assert resp.data["data"]["exercises"][0]["weight_kg"] is None


@pytest.mark.django_db
class TestWorkoutLogList:
    def test_list_is_paginated(self, client_with_addon):
        _, _, api = client_with_addon
        resp = api.get(EXERCISE_URL)
        assert "pagination" in resp.data["meta"]

    def test_list_scoped_to_authenticated_client(
        self, client_with_addon, client2_with_addon
    ):
        from apps.trackers.tests.factories import (
            ExerciseEntryFactory,
            WorkoutLogFactory,
        )

        _, profile, api = client_with_addon
        _, profile2, _ = client2_with_addon
        log1 = WorkoutLogFactory(client=profile)
        ExerciseEntryFactory(workout_log=log1)
        log2 = WorkoutLogFactory(client=profile2)
        ExerciseEntryFactory(workout_log=log2)

        resp = api.get(EXERCISE_URL)
        ids = [item["id"] for item in resp.data["data"]]
        assert str(log1.id) in ids
        assert str(log2.id) not in ids

    def test_date_filter_returns_matching_logs(self, client_with_addon):
        from apps.trackers.tests.factories import (
            ExerciseEntryFactory,
            WorkoutLogFactory,
        )

        _, profile, api = client_with_addon
        log1 = WorkoutLogFactory(client=profile, date=date(2025, 1, 15))
        ExerciseEntryFactory(workout_log=log1)
        log2 = WorkoutLogFactory(client=profile, date=date(2025, 2, 15))
        ExerciseEntryFactory(workout_log=log2)

        resp = api.get(EXERCISE_URL, {"date": "2025-01-15"})
        assert len(resp.data["data"]) == 1
        assert resp.data["data"][0]["date"] == "2025-01-15"

    def test_list_ordered_by_date_descending(self, client_with_addon):
        from apps.trackers.tests.factories import (
            ExerciseEntryFactory,
            WorkoutLogFactory,
        )

        _, profile, api = client_with_addon
        log1 = WorkoutLogFactory(client=profile, date=date(2025, 1, 1))
        ExerciseEntryFactory(workout_log=log1)
        log2 = WorkoutLogFactory(client=profile, date=date(2025, 3, 1))
        ExerciseEntryFactory(workout_log=log2)

        resp = api.get(EXERCISE_URL)
        dates = [item["date"] for item in resp.data["data"]]
        assert dates == sorted(dates, reverse=True)


@pytest.mark.django_db
class TestWorkoutLogDetail:
    def test_returns_log_with_exercises(self, client_with_addon):
        from apps.trackers.tests.factories import (
            ExerciseEntryFactory,
            WorkoutLogFactory,
        )

        _, profile, api = client_with_addon
        log = WorkoutLogFactory(client=profile)
        ExerciseEntryFactory(
            workout_log=log, name="Deadlift", sets=5, reps=5, weight_kg="150.00"
        )

        resp = api.get(f"{EXERCISE_URL}{log.id}/")
        assert resp.status_code == 200
        assert resp.data["data"]["id"] == str(log.id)
        assert len(resp.data["data"]["exercises"]) == 1
        assert resp.data["data"]["exercises"][0]["name"] == "Deadlift"

    def test_other_client_log_returns_404(self, client_with_addon, client2_with_addon):
        from apps.trackers.tests.factories import (
            ExerciseEntryFactory,
            WorkoutLogFactory,
        )

        _, profile2, _ = client2_with_addon
        _, _, api = client_with_addon
        log = WorkoutLogFactory(client=profile2)
        ExerciseEntryFactory(workout_log=log)

        resp = api.get(f"{EXERCISE_URL}{log.id}/")
        assert resp.status_code == 404

    def test_nonexistent_log_returns_404(self, client_with_addon):
        _, _, api = client_with_addon
        resp = api.get(f"{EXERCISE_URL}00000000-0000-0000-0000-000000000000/")
        assert resp.status_code == 404


@pytest.mark.django_db
class TestWorkoutLogUpdate:
    def test_put_updates_notes(self, client_with_addon):
        from apps.trackers.tests.factories import (
            ExerciseEntryFactory,
            WorkoutLogFactory,
        )

        _, profile, api = client_with_addon
        log = WorkoutLogFactory(client=profile, notes="Original")
        ExerciseEntryFactory(workout_log=log, name="Old Exercise")

        payload = {
            "date": str(log.date),
            "notes": "Updated",
            "exercises": [{"name": "New Exercise", "sets": 3, "reps": 10}],
        }
        resp = api.put(f"{EXERCISE_URL}{log.id}/", payload, format="json")
        assert resp.status_code == 200
        assert resp.data["data"]["notes"] == "Updated"

    def test_put_replaces_all_exercises(self, client_with_addon):
        from apps.trackers.models import ExerciseEntry
        from apps.trackers.tests.factories import (
            ExerciseEntryFactory,
            WorkoutLogFactory,
        )

        _, profile, api = client_with_addon
        log = WorkoutLogFactory(client=profile)
        ExerciseEntryFactory(workout_log=log, name="Old Exercise")

        payload = {
            "date": str(log.date),
            "notes": "",
            "exercises": [{"name": "New Exercise", "sets": 3, "reps": 10}],
        }
        api.put(f"{EXERCISE_URL}{log.id}/", payload, format="json")
        names = list(
            ExerciseEntry.objects.filter(workout_log=log).values_list("name", flat=True)
        )
        assert "New Exercise" in names
        assert "Old Exercise" not in names

    def test_put_other_client_log_returns_404(
        self, client_with_addon, client2_with_addon
    ):
        from apps.trackers.tests.factories import (
            ExerciseEntryFactory,
            WorkoutLogFactory,
        )

        _, profile2, _ = client2_with_addon
        _, _, api = client_with_addon
        log = WorkoutLogFactory(client=profile2)
        ExerciseEntryFactory(workout_log=log)

        payload = {
            "date": str(log.date),
            "exercises": [{"name": "X", "sets": 1, "reps": 1}],
        }
        resp = api.put(f"{EXERCISE_URL}{log.id}/", payload, format="json")
        assert resp.status_code == 404


@pytest.mark.django_db
class TestWorkoutLogDelete:
    def test_delete_returns_204(self, client_with_addon):
        from apps.trackers.tests.factories import (
            ExerciseEntryFactory,
            WorkoutLogFactory,
        )

        _, profile, api = client_with_addon
        log = WorkoutLogFactory(client=profile)
        ExerciseEntryFactory(workout_log=log)

        resp = api.delete(f"{EXERCISE_URL}{log.id}/")
        assert resp.status_code == 204

    def test_delete_is_soft(self, client_with_addon):
        from apps.trackers.models import WorkoutLog
        from apps.trackers.tests.factories import (
            ExerciseEntryFactory,
            WorkoutLogFactory,
        )

        _, profile, api = client_with_addon
        log = WorkoutLogFactory(client=profile)
        ExerciseEntryFactory(workout_log=log)

        api.delete(f"{EXERCISE_URL}{log.id}/")
        assert not WorkoutLog.objects.filter(id=log.id).exists()
        assert WorkoutLog.all_objects.filter(id=log.id).exists()

    def test_delete_other_client_log_returns_404(
        self, client_with_addon, client2_with_addon
    ):
        from apps.trackers.tests.factories import (
            ExerciseEntryFactory,
            WorkoutLogFactory,
        )

        _, profile2, _ = client2_with_addon
        _, _, api = client_with_addon
        log = WorkoutLogFactory(client=profile2)
        ExerciseEntryFactory(workout_log=log)

        resp = api.delete(f"{EXERCISE_URL}{log.id}/")
        assert resp.status_code == 404


@pytest.mark.django_db
class TestPersonalRecords:
    def test_unauthenticated_returns_401(self, anon_client):
        resp = anon_client.get(RECORDS_URL)
        assert resp.status_code == 401

    def test_trainer_returns_403(self, trainer_user):
        _, _, api = trainer_user
        resp = api.get(RECORDS_URL)
        assert resp.status_code == 403

    def test_client_without_addon_returns_403(self, client_no_addon):
        _, _, api = client_no_addon
        resp = api.get(RECORDS_URL)
        assert resp.status_code == 403

    def test_empty_list_when_no_logs(self, client_with_addon):
        _, _, api = client_with_addon
        resp = api.get(RECORDS_URL)
        assert resp.status_code == 200
        assert resp.data["data"]["records"] == []

    def test_returns_max_weight_per_exercise(self, client_with_addon):
        from apps.trackers.tests.factories import (
            ExerciseEntryFactory,
            WorkoutLogFactory,
        )

        _, profile, api = client_with_addon
        log1 = WorkoutLogFactory(client=profile, date=date(2025, 1, 10))
        log2 = WorkoutLogFactory(client=profile, date=date(2025, 2, 10))
        ExerciseEntryFactory(workout_log=log1, name="Squat", weight_kg="80.00")
        ExerciseEntryFactory(workout_log=log2, name="Squat", weight_kg="100.00")
        ExerciseEntryFactory(workout_log=log2, name="Deadlift", weight_kg="120.00")

        resp = api.get(RECORDS_URL)
        records = {r["exercise_name"]: r for r in resp.data["data"]["records"]}
        assert records["Squat"]["max_weight_kg"] == "100.00"
        assert records["Deadlift"]["max_weight_kg"] == "120.00"

    def test_exercises_without_weight_excluded(self, client_with_addon):
        from apps.trackers.tests.factories import (
            ExerciseEntryFactory,
            WorkoutLogFactory,
        )

        _, profile, api = client_with_addon
        log = WorkoutLogFactory(client=profile)
        ExerciseEntryFactory(workout_log=log, name="Push-up", weight_kg=None)

        resp = api.get(RECORDS_URL)
        names = [r["exercise_name"] for r in resp.data["data"]["records"]]
        assert "Push-up" not in names

    def test_records_ordered_alphabetically(self, client_with_addon):
        from apps.trackers.tests.factories import (
            ExerciseEntryFactory,
            WorkoutLogFactory,
        )

        _, profile, api = client_with_addon
        log = WorkoutLogFactory(client=profile)
        ExerciseEntryFactory(workout_log=log, name="Squat", weight_kg="80.00")
        ExerciseEntryFactory(workout_log=log, name="Bench Press", weight_kg="60.00")
        ExerciseEntryFactory(workout_log=log, name="Deadlift", weight_kg="100.00")

        resp = api.get(RECORDS_URL)
        names = [r["exercise_name"] for r in resp.data["data"]["records"]]
        assert names == sorted(names)

    def test_records_scoped_to_authenticated_client(
        self, client_with_addon, client2_with_addon
    ):
        from apps.trackers.tests.factories import (
            ExerciseEntryFactory,
            WorkoutLogFactory,
        )

        _, profile, api = client_with_addon
        _, profile2, _ = client2_with_addon
        log2 = WorkoutLogFactory(client=profile2)
        ExerciseEntryFactory(workout_log=log2, name="Squat", weight_kg="200.00")

        resp = api.get(RECORDS_URL)
        names = [r["exercise_name"] for r in resp.data["data"]["records"]]
        assert "Squat" not in names

    def test_logged_on_matches_session_of_max_weight(self, client_with_addon):
        from apps.trackers.tests.factories import (
            ExerciseEntryFactory,
            WorkoutLogFactory,
        )

        _, profile, api = client_with_addon
        log1 = WorkoutLogFactory(client=profile, date=date(2025, 1, 10))
        log2 = WorkoutLogFactory(client=profile, date=date(2025, 2, 10))
        ExerciseEntryFactory(workout_log=log1, name="Squat", weight_kg="80.00")
        ExerciseEntryFactory(workout_log=log2, name="Squat", weight_kg="100.00")

        resp = api.get(RECORDS_URL)
        squat = next(
            r for r in resp.data["data"]["records"] if r["exercise_name"] == "Squat"
        )
        assert squat["logged_on"] == "2025-02-10"
