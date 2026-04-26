"""Factories for tracker model tests."""

import datetime

import factory
from factory.django import DjangoModelFactory

from apps.profiles.tests.factories import ClientProfileFactory
from apps.trackers.models import DailyNutritionLog, ExerciseEntry, MealEntry, WorkoutLog


class WorkoutLogFactory(DjangoModelFactory):
    class Meta:
        model = WorkoutLog

    client = factory.SubFactory(ClientProfileFactory)
    date = factory.LazyFunction(datetime.date.today)
    notes = ""


class ExerciseEntryFactory(DjangoModelFactory):
    class Meta:
        model = ExerciseEntry

    workout_log = factory.SubFactory(WorkoutLogFactory)
    name = "Squat"
    sets = 3
    reps = 10
    weight_kg = None


class DailyNutritionLogFactory(DjangoModelFactory):
    class Meta:
        model = DailyNutritionLog

    client = factory.SubFactory(ClientProfileFactory)
    date = factory.LazyFunction(datetime.date.today)
    calorie_goal = None
    protein_goal_g = None
    carbs_goal_g = None
    fat_goal_g = None


class MealEntryFactory(DjangoModelFactory):
    class Meta:
        model = MealEntry

    nutrition_log = factory.SubFactory(DailyNutritionLogFactory)
    meal_type = "breakfast"
    food_name = "Oats"
    quantity = "100.00"
    unit = "g"
    calories = 389
    protein_g = "13.00"
    carbs_g = "66.00"
    fat_g = "7.00"
