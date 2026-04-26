"""Serializers for the trackers app."""

from decimal import Decimal

from django.db.models import Sum
from rest_framework import serializers

from .models import DailyNutritionLog, ExerciseEntry, MealEntry, WorkoutLog


class ExerciseEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = ExerciseEntry
        fields = ["id", "name", "sets", "reps", "weight_kg"]
        read_only_fields = ["id"]


class WorkoutLogSerializer(serializers.ModelSerializer):
    exercises = ExerciseEntrySerializer(many=True)

    class Meta:
        model = WorkoutLog
        fields = ["id", "date", "notes", "exercises", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate_exercises(self, value):
        if not value:
            raise serializers.ValidationError("At least one exercise is required.")
        return value

    def create(self, validated_data):
        exercises_data = validated_data.pop("exercises")
        log = WorkoutLog.objects.create(**validated_data)
        for exercise_data in exercises_data:
            ExerciseEntry.objects.create(workout_log=log, **exercise_data)
        return log

    def update(self, instance, validated_data):
        exercises_data = validated_data.pop("exercises")
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        # Hard-replace all exercises
        ExerciseEntry.objects.filter(workout_log=instance).delete()
        for exercise_data in exercises_data:
            ExerciseEntry.objects.create(workout_log=instance, **exercise_data)
        return instance


class MealEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = MealEntry
        fields = [
            "id",
            "meal_type",
            "food_name",
            "quantity",
            "unit",
            "calories",
            "protein_g",
            "carbs_g",
            "fat_g",
        ]
        read_only_fields = ["id"]


class DailyNutritionLogListSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyNutritionLog
        fields = [
            "id",
            "date",
            "calorie_goal",
            "protein_goal_g",
            "carbs_goal_g",
            "fat_goal_g",
        ]


class DailyNutritionLogDetailSerializer(serializers.ModelSerializer):
    meals = MealEntrySerializer(many=True, read_only=True)
    total_calories = serializers.SerializerMethodField()
    total_protein_g = serializers.SerializerMethodField()
    total_carbs_g = serializers.SerializerMethodField()
    total_fat_g = serializers.SerializerMethodField()
    goal_progress = serializers.SerializerMethodField()

    class Meta:
        model = DailyNutritionLog
        fields = [
            "id",
            "date",
            "calorie_goal",
            "protein_goal_g",
            "carbs_goal_g",
            "fat_goal_g",
            "meals",
            "total_calories",
            "total_protein_g",
            "total_carbs_g",
            "total_fat_g",
            "goal_progress",
        ]

    def get_total_calories(self, obj):
        return obj.meals.aggregate(total=Sum("calories"))["total"] or 0

    def get_total_protein_g(self, obj):
        total = obj.meals.aggregate(total=Sum("protein_g"))["total"] or Decimal("0.00")
        return f"{total:.2f}"

    def get_total_carbs_g(self, obj):
        total = obj.meals.aggregate(total=Sum("carbs_g"))["total"] or Decimal("0.00")
        return f"{total:.2f}"

    def get_total_fat_g(self, obj):
        total = obj.meals.aggregate(total=Sum("fat_g"))["total"] or Decimal("0.00")
        return f"{total:.2f}"

    def get_goal_progress(self, obj):
        if not obj.calorie_goal:
            return None
        total = obj.meals.aggregate(total=Sum("calories"))["total"] or 0
        return round(total / obj.calorie_goal * 100, 1)


class NutritionGoalUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyNutritionLog
        fields = ["calorie_goal", "protein_goal_g", "carbs_goal_g", "fat_goal_g"]
