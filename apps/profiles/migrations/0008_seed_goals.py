from django.db import migrations

GOALS = [
    "Build Muscle",
    "Lose Weight",
    "Core Strength",
    "Improve Fitness",
    "Feel Healthier",
    "Stay Consistent",
]


def seed_goals(apps, schema_editor):
    Goal = apps.get_model("profiles", "Goal")
    for name in GOALS:
        Goal.objects.get_or_create(name=name, defaults={"is_predefined": True})


def reverse_goals(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("profiles", "0007_goal_remove_gymprofile_wizard_completed_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_goals, reverse_goals),
    ]
