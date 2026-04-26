from django.contrib import admin

from .models import DailyNutritionLog, ExerciseEntry, MealEntry, WorkoutLog


@admin.register(WorkoutLog)
class WorkoutLogAdmin(admin.ModelAdmin):
    list_display = ["client", "date", "created_at"]
    list_filter = ["date"]
    search_fields = ["client__user__email"]


@admin.register(ExerciseEntry)
class ExerciseEntryAdmin(admin.ModelAdmin):
    list_display = ["name", "workout_log", "sets", "reps", "weight_kg"]
    search_fields = ["name"]


@admin.register(DailyNutritionLog)
class DailyNutritionLogAdmin(admin.ModelAdmin):
    list_display = ["client", "date", "calorie_goal"]
    list_filter = ["date"]
    search_fields = ["client__user__email"]


@admin.register(MealEntry)
class MealEntryAdmin(admin.ModelAdmin):
    list_display = ["food_name", "meal_type", "nutrition_log", "calories"]
    list_filter = ["meal_type"]
    search_fields = ["food_name"]
