"""
Management command to seed test data for development/testing.
NEVER run in production.

Usage:
    python manage.py seed_test_data
    python manage.py seed_test_data --clear
"""

import random

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

NIGERIAN_CITIES = ["Lagos", "Abuja", "Port Harcourt", "Kano", "Ibadan"]
SPECIALISATIONS = ["Weight Loss", "Muscle Building", "HIIT", "Yoga", "Boxing"]
BIOS = [
    "Certified personal trainer with 5+ years experience.",
    "Helping clients achieve their fitness goals since 2019.",
    "Specialist in functional training and weight management.",
    "Former professional athlete turned fitness coach.",
    "Passionate about making fitness accessible to everyone.",
]
FIRST_NAMES = [
    "Emeka",
    "Chidi",
    "Ngozi",
    "Amara",
    "Tunde",
    "Bola",
    "Yemi",
    "Sola",
    "Kemi",
    "Dami",
    "Uche",
    "Ike",
    "Ada",
    "Nkem",
    "Tobi",
    "Femi",
    "Seun",
    "Wale",
    "Lola",
    "Zara",
    "Musa",
    "Aisha",
    "Fatima",
    "Ibrahim",
    "Hauwa",
]
LAST_NAMES = [
    "Okonkwo",
    "Adeyemi",
    "Bello",
    "Ibrahim",
    "Okafor",
    "Eze",
    "Nwosu",
    "Adeleke",
    "Musa",
    "Chukwu",
]


class Command(BaseCommand):
    help = "Seed test data for development/testing. NEVER run in production."

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear existing seed data before seeding",
        )

    def handle(self, *args, **options):
        if options["clear"]:
            self.clear_seed_data()

        with transaction.atomic():
            self.stdout.write("Creating gyms...")
            gym1_profile = self.create_gym("FitZone Lagos", "Lagos")
            gym2_profile = self.create_gym("PowerHouse Abuja", "Abuja")

            self.stdout.write("Creating gym trainers...")
            self.create_trainer("Emeka Okonkwo", gym=gym1_profile)
            self.create_trainer("Ngozi Adeyemi", gym=gym1_profile)
            self.create_trainer("Tunde Bello", gym=gym2_profile)
            self.create_trainer("Amara Eze", gym=gym2_profile)

            self.stdout.write("Creating independent trainers...")
            indie_trainer1 = self.create_trainer("Chidi Nwosu", gym=None)
            indie_trainer2 = self.create_trainer("Kemi Adeleke", gym=None)

            self.stdout.write("Creating 24 clients...")
            clients = [self.create_client(i) for i in range(24)]

            self.stdout.write("Creating memberships...")
            for client in clients[0:6]:
                self.create_membership(client, gym=gym1_profile)

            for client in clients[6:12]:
                self.create_membership(client, gym=gym2_profile)

            for client in clients[12:18]:
                self.create_membership(client, trainer=indie_trainer1)

            for client in clients[18:24]:
                self.create_membership(client, trainer=indie_trainer2)

            self.stdout.write(
                self.style.SUCCESS(
                    "\n✅ Seed data created successfully!\n"
                    "\nSummary:\n"
                    "  Gyms: 2\n"
                    "    └─ FitZone Lagos (2 gym trainers)\n"
                    "    └─ PowerHouse Abuja (2 gym trainers)\n"
                    "  Independent Trainers: 2\n"
                    "  Clients: 24\n"
                    "    └─ 6 clients → FitZone Lagos\n"
                    "    └─ 6 clients → PowerHouse Abuja\n"
                    "    └─ 6 clients → Chidi Nwosu\n"
                    "    └─ 6 clients → Kemi Adeleke\n"
                    "\nLogin credentials:\n"
                    "  All users: password = Test1234!\n"
                    "  Gym 1 admin: fitzonelago@fittrybe.com\n"
                    "  Gym 2 admin: powerhouseabuja@fittrybe.com\n"
                    "  Indie Trainer 1: chidi.nwosu@fittrybe.com\n"
                    "  Indie Trainer 2: kemi.adeleke@fittrybe.com\n"
                    "  Clients: client01@fittrybe.com ... client24@fittrybe.com\n"
                )
            )

    def create_gym(self, gym_name, city):
        from apps.accounts.models import User
        from apps.profiles.models import Availability, GymProfile
        from apps.subscriptions.models import PlanConfig, Subscription

        email = f"{gym_name.lower().replace(' ', '')}@fittrybe.com"

        user = User.objects.create_user(
            email=email,
            password="Test1234!",
            role="gym",
            display_name=gym_name,
            is_email_verified=True,
            is_active=True,
            onboarding_status="completed",
        )

        profile = GymProfile.objects.create(
            user=user,
            gym_name=gym_name,
            admin_full_name=f"Admin of {gym_name}",
            about=f"Premier fitness facility in {city}.",
            location=f"{city}, Nigeria",
            city=city,
            contact_phone=f"080{random.randint(10000000, 99999999)}",
            business_email=email,
            is_published=True,
            wizard_step=4,
            wizard_completed=True,
        )

        for day in ["monday", "wednesday", "friday"]:
            Availability.objects.create(
                gym=profile,
                day_of_week=day,
                start_time="06:00",
                end_time="20:00",
                session_type="both",
            )

        try:
            plan = PlanConfig.objects.get(plan="pro")
            now = timezone.now()
            Subscription.objects.get_or_create(
                user=user,
                defaults={
                    "plan": plan,
                    "status": "active",
                    "trial_end": now + timezone.timedelta(days=14),
                    "current_period_start": now,
                    "current_period_end": now + timezone.timedelta(days=30),
                },
            )
        except PlanConfig.DoesNotExist:
            pass

        self.stdout.write(f"  ✓ Gym: {gym_name} ({email})")
        return profile

    def create_trainer(self, full_name, gym=None):
        from apps.accounts.models import User
        from apps.profiles.models import (
            Availability,
            GymTrainer,
            Service,
            Specialisation,
            TrainerProfile,
        )
        from apps.subscriptions.models import PlanConfig, Subscription

        email = f"{full_name.lower().replace(' ', '.')}@fittrybe.com"
        trainer_type = "gym_trainer" if gym else "independent"

        user = User.objects.create_user(
            email=email,
            password="Test1234!",
            role="trainer",
            display_name=full_name,
            is_email_verified=True,
            is_active=True,
            onboarding_status="completed",
        )

        profile = TrainerProfile.objects.create(
            user=user,
            full_name=full_name,
            bio=random.choice(BIOS),
            location=f"{random.choice(NIGERIAN_CITIES)}, Nigeria",
            years_experience=random.randint(2, 10),
            pricing_range=f"From \u20a6{random.randint(10, 30) * 1000:,}/session",
            trainer_type=trainer_type,
            gym=gym,
            is_published=True,
            wizard_step=4,
            wizard_completed=True,
        )

        specs = Specialisation.objects.filter(
            name__in=random.sample(SPECIALISATIONS, 2)
        )
        profile.specialisations.set(specs)

        for day in ["tuesday", "thursday", "saturday"]:
            Availability.objects.create(
                trainer=profile,
                day_of_week=day,
                start_time="07:00",
                end_time="18:00",
                session_type="both",
                duration_minutes=60,
            )

        Service.objects.create(
            trainer=profile,
            name="Personal Training 1-on-1",
            description="One-on-one personal training session.",
            session_type="both",
        )

        # Gym trainers are covered by the gym's Pro Plan — no own subscription
        if gym is None:
            try:
                plan = PlanConfig.objects.get(plan="basic")
                now = timezone.now()
                Subscription.objects.get_or_create(
                    user=user,
                    defaults={
                        "plan": plan,
                        "status": "active",
                        "trial_end": now + timezone.timedelta(days=14),
                        "current_period_start": now,
                        "current_period_end": now + timezone.timedelta(days=30),
                    },
                )
            except PlanConfig.DoesNotExist:
                pass

        if gym:
            GymTrainer.objects.get_or_create(
                gym=gym,
                trainer=profile,
                defaults={"role": "trainer"},
            )

        self.stdout.write(f"  ✓ Trainer: {full_name} ({trainer_type}) ({email})")
        return profile

    def create_client(self, index):
        from apps.accounts.models import User
        from apps.profiles.models import ClientProfile

        num = str(index + 1).zfill(2)
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        email = f"client{num}@fittrybe.com"
        display_name = f"{first} {last}"

        user = User.objects.create_user(
            email=email,
            password="Test1234!",
            role="client",
            display_name=display_name,
            is_email_verified=True,
            is_active=True,
        )
        profile = ClientProfile.objects.create(
            user=user,
            display_name=display_name,
        )

        return profile

    def create_membership(self, client_profile, trainer=None, gym=None):
        from apps.clients.models import ClientMembership

        kwargs = {
            "client": client_profile,
            "status": ClientMembership.Status.ACTIVE,
            "payment_amount": random.choice([15000, 20000, 25000, 30000]),
            "payment_currency": "NGN",
            "payment_notes": "Pays via bank transfer",
            "sessions_count": random.randint(0, 20),
        }
        if trainer:
            kwargs["trainer"] = trainer
        if gym:
            kwargs["gym"] = gym

        ClientMembership.objects.create(**kwargs)

    def clear_seed_data(self):
        from apps.accounts.models import User
        from apps.profiles.models import GymTrainer

        # Delete GymTrainer records first to avoid FK issues during user cascade
        gym_trainer_count, _ = GymTrainer.objects.filter(
            trainer__user__email__icontains="fittrybe.com"
        ).delete()

        patterns = ["fitzonelago", "powerhouseabuja", "fittrybe.com"]
        deleted = 0
        for pattern in patterns:
            count, _ = User.objects.filter(email__icontains=pattern).delete()
            deleted += count

        self.stdout.write(
            self.style.WARNING(
                f"Cleared {gym_trainer_count} GymTrainer records "
                f"and {deleted} seed users."
            )
        )
