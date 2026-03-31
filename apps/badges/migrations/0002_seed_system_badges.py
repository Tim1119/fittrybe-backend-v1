"""
Data migration — seed predefined system badges.
"""

from django.db import migrations

SYSTEM_BADGES = [
    # Manual badges — trainer assigns from TRN-16 grid
    {
        "name": "New Member",
        "badge_type": "manual",
        "description": "Welcome to the community!",
        "milestone_threshold": None,
        "is_system": True,
    },
    {
        "name": "Top Performer",
        "badge_type": "manual",
        "description": "Outstanding performance this week.",
        "milestone_threshold": None,
        "is_system": True,
    },
    {
        "name": "Most Consistent",
        "badge_type": "manual",
        "description": "Never misses a session.",
        "milestone_threshold": None,
        "is_system": True,
    },
    {
        "name": "Most Improved",
        "badge_type": "manual",
        "description": "Biggest improvement this month.",
        "milestone_threshold": None,
        "is_system": True,
    },
    {
        "name": "Session Streak",
        "badge_type": "manual",
        "description": "On a great streak!",
        "milestone_threshold": None,
        "is_system": True,
    },
    # Milestone badges — auto-assigned by system
    {
        "name": "First Session",
        "badge_type": "milestone",
        "description": "Completed their first session!",
        "milestone_threshold": 1,
        "is_system": True,
    },
    {
        "name": "5 Sessions",
        "badge_type": "milestone",
        "description": "5 sessions completed.",
        "milestone_threshold": 5,
        "is_system": True,
    },
    {
        "name": "10 Sessions",
        "badge_type": "milestone",
        "description": "10 sessions completed.",
        "milestone_threshold": 10,
        "is_system": True,
    },
    {
        "name": "25 Sessions",
        "badge_type": "milestone",
        "description": "25 sessions completed.",
        "milestone_threshold": 25,
        "is_system": True,
    },
    {
        "name": "50 Sessions",
        "badge_type": "milestone",
        "description": "50 sessions completed.",
        "milestone_threshold": 50,
        "is_system": True,
    },
    # Weekly top badges — auto every Monday
    {
        "name": "Weekly Top 1",
        "badge_type": "weekly_top",
        "description": "#1 most active client this week.",
        "milestone_threshold": None,
        "is_system": True,
    },
    {
        "name": "Weekly Top 2",
        "badge_type": "weekly_top",
        "description": "#2 most active client this week.",
        "milestone_threshold": None,
        "is_system": True,
    },
    {
        "name": "Weekly Top 3",
        "badge_type": "weekly_top",
        "description": "#3 most active client this week.",
        "milestone_threshold": None,
        "is_system": True,
    },
]


def seed_badges(apps, schema_editor):
    Badge = apps.get_model("badges", "Badge")
    for data in SYSTEM_BADGES:
        Badge.objects.get_or_create(name=data["name"], defaults=data)


def unseed_badges(apps, schema_editor):
    Badge = apps.get_model("badges", "Badge")
    Badge.objects.filter(is_system=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("badges", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_badges, reverse_code=unseed_badges),
    ]
