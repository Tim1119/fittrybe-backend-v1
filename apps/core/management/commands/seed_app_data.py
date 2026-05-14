"""
Management command to seed all reference/lookup data the app needs to function.
Completely idempotent — safe to run multiple times on the same DB. Creates NO users.
Usage:
    python manage.py seed_app_data
"""

from django.core.management.base import BaseCommand

SPECIALISATIONS = [
    "Weight Loss",
    "Muscle Building",
    "HIIT",
    "Strength Training",
    "Yoga",
    "Pilates",
    "Nutrition Coaching",
    "Rehabilitation",
    "Boxing",
    "Dance Fitness",
    "Cardio",
    "CrossFit",
    "Calisthenics",
    "Powerlifting",
    "Bodybuilding",
    "Mobility & Flexibility",
    "Pre/Postnatal Fitness",
    "Senior Fitness",
    "Sports Performance",
    "Functional Training",
]

GOALS = [
    "Build Muscle",
    "Lose Weight",
    "Core Strength",
    "Improve Fitness",
    "Feel Healthier",
    "Stay Consistent",
]

BADGES = [
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

PLANS = [
    {
        "plan": "basic",
        "display_name": "Basic",
        "price_ngn": 15000,
        "price_usd": 10,
        "trial_days": 14,
        "is_active": True,
        "features": [
            "Individual trainer profile",
            "1 community chatroom",
            "Client management (up to 50 clients)",
            "Marketplace listings",
            "Basic analytics",
            "1-on-1 direct messaging",
            "Badge assignment",
            "Session tracking",
        ],
    },
    {
        "plan": "pro",
        "display_name": "Pro",
        "price_ngn": 35000,
        "price_usd": 25,
        "trial_days": 14,
        "is_active": True,
        "features": [
            "Full gym profile",
            "Up to 3 trainer logins",
            "Multiple chatrooms",
            "Shared gym marketplace",
            "Per-trainer analytics",
            "Gym-wide leaderboard",
            "Priority support",
        ],
    },
]


class Command(BaseCommand):
    help = "Seed all reference/lookup data. Idempotent — safe to run multiple times."

    def handle(self, *args, **options):
        from apps.badges.models import Badge
        from apps.profiles.models import Goal, Specialisation
        from apps.subscriptions.models import PlanConfig

        self.stdout.write("FitTrybe — Seeding app data")
        self.stdout.write("━" * 38)

        # ── Specialisations ──────────────────────────────────────────────────
        spec_created = spec_existed = 0
        for name in SPECIALISATIONS:
            _, created = Specialisation.objects.get_or_create(
                name=name, defaults={"is_predefined": True}
            )
            if created:
                spec_created += 1
            else:
                spec_existed += 1
        self.stdout.write(
            f"✓ Specialisations : {len(SPECIALISATIONS)} seeded "
            f"({spec_created} created, {spec_existed} already existed)"
        )

        # ── Goals ────────────────────────────────────────────────────────────
        goal_created = goal_existed = 0
        for name in GOALS:
            _, created = Goal.objects.get_or_create(
                name=name, defaults={"is_predefined": True}
            )
            if created:
                goal_created += 1
            else:
                goal_existed += 1
        self.stdout.write(
            f"✓ Goals           :  {len(GOALS)} seeded "
            f"({goal_created} created, {goal_existed} already existed)"
        )

        # ── Badges ───────────────────────────────────────────────────────────
        badge_created = badge_existed = 0
        for data in BADGES:
            _, created = Badge.objects.get_or_create(name=data["name"], defaults=data)
            if created:
                badge_created += 1
            else:
                badge_existed += 1
        self.stdout.write(
            f"✓ Badges          : {len(BADGES)} seeded "
            f"({badge_created} created, {badge_existed} already existed)"
        )

        # ── Subscription Plans ───────────────────────────────────────────────
        plan_created = plan_updated = 0
        for data in PLANS:
            plan_key = data["plan"]
            plan_fields = {k: v for k, v in data.items() if k != "plan"}
            obj, created = PlanConfig.objects.get_or_create(
                plan=plan_key, defaults=plan_fields
            )
            if created:
                plan_created += 1
            else:
                for field, value in plan_fields.items():
                    setattr(obj, field, value)
                obj.save()
                plan_updated += 1
        self.stdout.write(
            f"✓ Plans           :  {len(PLANS)} seeded "
            f"({plan_created} created, {plan_updated} updated)"
        )

        self.stdout.write("━" * 38)
        self.stdout.write(self.style.SUCCESS("✅ Done. App reference data is ready."))
        self.stdout.write("   Run python manage.py seed_test_data to add test users.")
