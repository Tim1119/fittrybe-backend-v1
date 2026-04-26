"""Tracker models — exercise and nutrition logs for clients."""

import uuid

from django.db import models

from apps.core.models import BaseModel


class WorkoutLog(BaseModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client = models.ForeignKey(
        "profiles.ClientProfile",
        on_delete=models.CASCADE,
        related_name="workout_logs",
    )
    date = models.DateField()
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-date", "-created_at"]

    def __str__(self):
        return f"WorkoutLog({self.client} — {self.date})"


class ExerciseEntry(BaseModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workout_log = models.ForeignKey(
        WorkoutLog,
        on_delete=models.CASCADE,
        related_name="exercises",
    )
    name = models.CharField(max_length=100)
    sets = models.PositiveIntegerField(default=1)
    reps = models.PositiveIntegerField(default=1)
    weight_kg = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True
    )

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.name} ({self.sets}x{self.reps})"


class DailyNutritionLog(BaseModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client = models.ForeignKey(
        "profiles.ClientProfile",
        on_delete=models.CASCADE,
        related_name="nutrition_logs",
    )
    date = models.DateField()
    calorie_goal = models.PositiveIntegerField(null=True, blank=True)
    protein_goal_g = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True
    )
    carbs_goal_g = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True
    )
    fat_goal_g = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True
    )

    class Meta:
        ordering = ["-date", "-created_at"]
        unique_together = [("client", "date")]

    def __str__(self):
        return f"NutritionLog({self.client} — {self.date})"


class MealEntry(BaseModel):
    class MealType(models.TextChoices):
        BREAKFAST = "breakfast", "Breakfast"
        LUNCH = "lunch", "Lunch"
        DINNER = "dinner", "Dinner"
        SNACKS = "snacks", "Snacks"

    class Unit(models.TextChoices):
        G = "g", "Grams"
        ML = "ml", "Millilitres"
        SERVING = "serving", "Serving"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nutrition_log = models.ForeignKey(
        DailyNutritionLog,
        on_delete=models.CASCADE,
        related_name="meals",
    )
    meal_type = models.CharField(max_length=20, choices=MealType.choices)
    food_name = models.CharField(max_length=200)
    quantity = models.DecimalField(max_digits=8, decimal_places=2)
    unit = models.CharField(max_length=10, choices=Unit.choices, default=Unit.SERVING)
    calories = models.PositiveIntegerField(default=0)
    protein_g = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    carbs_g = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    fat_g = models.DecimalField(max_digits=6, decimal_places=2, default=0)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.food_name} ({self.meal_type})"
