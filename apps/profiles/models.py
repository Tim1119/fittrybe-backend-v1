"""
Profile models — Specialisation, TrainerProfile, GymProfile,
GymTrainer, Availability, Certification, Service, ClientProfile.
"""

from decimal import Decimal

from autoslug import AutoSlugField
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, UniqueConstraint

from apps.core.models import BaseModel


class Specialisation(BaseModel):
    name = models.CharField(max_length=100, unique=True)
    slug = AutoSlugField(populate_from="name", unique=True, always_update=False)
    is_predefined = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Specialisation"
        verbose_name_plural = "Specialisations"
        ordering = ["name"]

    def __str__(self):
        return self.name


class TrainerProfile(BaseModel):
    class TrainerType(models.TextChoices):
        INDEPENDENT = "independent", "Independent"
        GYM_TRAINER = "gym_trainer", "Gym Trainer"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="trainer_profile",
    )
    gym = models.ForeignKey(
        "GymProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="gym_trainers",
    )
    trainer_type = models.CharField(
        max_length=20,
        choices=TrainerType.choices,
        default=TrainerType.INDEPENDENT,
        db_index=True,
    )
    full_name = models.CharField(max_length=200)
    slug = AutoSlugField(populate_from="full_name", unique=True, always_update=False)
    bio = models.TextField(max_length=500, blank=True)
    location = models.CharField(max_length=200, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    years_experience = models.PositiveIntegerField(default=0)
    pricing_range = models.CharField(max_length=200, blank=True)
    profile_photo_url = models.URLField(blank=True)
    cover_photo_url = models.URLField(blank=True)
    specialisations = models.ManyToManyField(
        Specialisation, blank=True, related_name="trainers"
    )
    is_published = models.BooleanField(default=False, db_index=True)
    avg_rating = models.DecimalField(
        max_digits=3, decimal_places=2, default=Decimal("0.00")
    )
    rating_count = models.PositiveIntegerField(default=0)
    wizard_step = models.PositiveIntegerField(default=0)
    wizard_completed = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Trainer Profile"
        verbose_name_plural = "Trainer Profiles"

    @property
    def profile_completion_percentage(self):
        points = 0
        if self.full_name:
            points += 15
        if self.bio:
            points += 15
        if self.location:
            points += 10
        if self.profile_photo_url:
            points += 20
        if self.cover_photo_url:
            points += 5
        if self.years_experience > 0:
            points += 5
        if self.services.exists():
            points += 10
        if self.specialisations.exists():
            points += 10
        if self.availability.exists():
            points += 10
        return points

    def get_missing_fields(self):
        missing = []
        if not self.bio:
            missing.append("bio")
        if not self.location:
            missing.append("location")
        if not self.profile_photo_url:
            missing.append("profile_photo")
        if not self.cover_photo_url:
            missing.append("cover_photo")
        if self.years_experience == 0:
            missing.append("years_experience")
        if not self.services.exists():
            missing.append("services")
        if not self.specialisations.exists():
            missing.append("specialisations")
        if not self.availability.exists():
            missing.append("availability")
        return missing

    def get_public_url(self):
        return f"{settings.FRONTEND_URL}/trainer/{self.slug}"

    def __str__(self):
        return f"{self.full_name} ({self.user.email})"


class GymProfile(BaseModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="gym_profile",
    )
    gym_name = models.CharField(max_length=200)
    slug = AutoSlugField(populate_from="gym_name", unique=True, always_update=False)
    admin_full_name = models.CharField(max_length=200)
    about = models.TextField(max_length=500, blank=True)
    location = models.CharField(max_length=200, blank=True)
    city = models.CharField(max_length=100, blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)
    business_email = models.EmailField(blank=True)
    logo_url = models.URLField(blank=True)
    cover_photo_url = models.URLField(blank=True)
    is_published = models.BooleanField(default=False, db_index=True)
    avg_rating = models.DecimalField(
        max_digits=3, decimal_places=2, default=Decimal("0.00")
    )
    rating_count = models.PositiveIntegerField(default=0)
    wizard_step = models.PositiveIntegerField(default=0)
    wizard_completed = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Gym Profile"
        verbose_name_plural = "Gym Profiles"

    @property
    def profile_completion_percentage(self):
        points = 0
        if self.gym_name:
            points += 15
        if self.admin_full_name:
            points += 10
        if self.about:
            points += 15
        if self.location:
            points += 10
        if self.city:
            points += 5
        if self.logo_url:
            points += 15
        if self.cover_photo_url:
            points += 5
        if self.contact_phone:
            points += 5
        if self.business_email:
            points += 5
        if self.availability.exists():
            points += 15
        return points

    def get_missing_fields(self):
        missing = []
        if not self.about:
            missing.append("about")
        if not self.location:
            missing.append("location")
        if not self.city:
            missing.append("city")
        if not self.logo_url:
            missing.append("logo")
        if not self.cover_photo_url:
            missing.append("cover_photo")
        if not self.contact_phone:
            missing.append("contact_phone")
        if not self.business_email:
            missing.append("business_email")
        if not self.availability.exists():
            missing.append("availability")
        return missing

    def get_public_url(self):
        return f"{settings.FRONTEND_URL}/gym/{self.slug}"

    def __str__(self):
        return f"{self.gym_name} ({self.user.email})"


class GymTrainer(BaseModel):
    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        TRAINER = "trainer", "Trainer"

    gym = models.ForeignKey(
        GymProfile,
        on_delete=models.CASCADE,
        related_name="gym_trainer_memberships",
    )
    trainer = models.ForeignKey(
        TrainerProfile,
        on_delete=models.CASCADE,
        related_name="gym_memberships",
    )
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.TRAINER)

    class Meta:
        unique_together = ("gym", "trainer")
        verbose_name = "Gym Trainer"
        verbose_name_plural = "Gym Trainers"

    def __str__(self):
        return f"{self.trainer.full_name} @ {self.gym.gym_name}"


class Availability(BaseModel):
    class DayOfWeek(models.TextChoices):
        MONDAY = "monday", "Monday"
        TUESDAY = "tuesday", "Tuesday"
        WEDNESDAY = "wednesday", "Wednesday"
        THURSDAY = "thursday", "Thursday"
        FRIDAY = "friday", "Friday"
        SATURDAY = "saturday", "Saturday"
        SUNDAY = "sunday", "Sunday"

    class SessionType(models.TextChoices):
        PHYSICAL = "physical", "Physical"
        VIRTUAL = "virtual", "Virtual"
        BOTH = "both", "Both"

    trainer = models.ForeignKey(
        TrainerProfile,
        on_delete=models.CASCADE,
        related_name="availability",
        null=True,
        blank=True,
    )
    gym = models.ForeignKey(
        GymProfile,
        on_delete=models.CASCADE,
        related_name="availability",
        null=True,
        blank=True,
    )
    day_of_week = models.CharField(
        max_length=10, choices=DayOfWeek.choices, db_index=True
    )
    start_time = models.TimeField()
    end_time = models.TimeField()
    session_type = models.CharField(
        max_length=10,
        choices=SessionType.choices,
        default=SessionType.BOTH,
    )
    duration_minutes = models.PositiveIntegerField(default=60)
    virtual_platform = models.CharField(max_length=100, blank=True)
    notes = models.CharField(
        max_length=200,
        blank=True,
        help_text="e.g. Morning HIIT class, Evening yoga",
    )

    class Meta:
        verbose_name = "Availability"
        verbose_name_plural = "Availabilities"
        constraints = [
            UniqueConstraint(
                fields=["trainer", "day_of_week"],
                condition=Q(trainer__isnull=False),
                name="unique_trainer_day",
            ),
            UniqueConstraint(
                fields=["gym", "day_of_week"],
                condition=Q(gym__isnull=False),
                name="unique_gym_day",
            ),
        ]

    def clean(self):
        if self.start_time and self.end_time:
            if self.start_time >= self.end_time:
                raise ValidationError("Start time must be before end time.")
        if not self.trainer and not self.gym:
            raise ValidationError("Availability must belong to a trainer or gym.")
        if self.trainer and self.gym:
            raise ValidationError("Availability cannot belong to both trainer and gym.")

    def __str__(self):
        owner = self.trainer or self.gym
        return f"{owner} - {self.day_of_week}"


class Certification(BaseModel):
    trainer = models.ForeignKey(
        TrainerProfile, on_delete=models.CASCADE, related_name="certifications"
    )
    name = models.CharField(max_length=200)
    issuing_body = models.CharField(max_length=200, blank=True)
    year_obtained = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        verbose_name = "Certification"
        verbose_name_plural = "Certifications"

    def __str__(self):
        return f"{self.name} - {self.trainer.full_name}"


class Service(BaseModel):
    class SessionType(models.TextChoices):
        PHYSICAL = "physical", "Physical"
        VIRTUAL = "virtual", "Virtual"
        BOTH = "both", "Both"

    trainer = models.ForeignKey(
        TrainerProfile,
        on_delete=models.CASCADE,
        related_name="services",
        null=True,
        blank=True,
    )
    gym = models.ForeignKey(
        GymProfile,
        on_delete=models.CASCADE,
        related_name="services",
        null=True,
        blank=True,
    )
    name = models.CharField(
        max_length=200,
        help_text="e.g. Personal Training 1-on-1",
    )
    description = models.TextField(max_length=500, blank=True)
    session_type = models.CharField(
        max_length=10,
        choices=SessionType.choices,
        default=SessionType.BOTH,
    )
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Service"
        verbose_name_plural = "Services"
        ordering = ["display_order", "name"]

    def clean(self):
        if not self.trainer and not self.gym:
            raise ValidationError("Service must belong to trainer or gym.")
        if self.trainer and self.gym:
            raise ValidationError("Service cannot belong to both.")

    def __str__(self):
        return self.name


class ClientProfile(BaseModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="client_profile",
    )
    display_name = models.CharField(max_length=100, blank=True)
    username = AutoSlugField(
        populate_from="_get_username_base", unique=True, always_update=False
    )
    profile_photo_url = models.URLField(blank=True)

    class Meta:
        verbose_name = "Client Profile"
        verbose_name_plural = "Client Profiles"

    def _get_username_base(self):
        return self.user.email.split("@")[0]

    @property
    def profile_completion_percentage(self):
        points = 0
        if self.display_name:
            points += 50
        if self.profile_photo_url:
            points += 50
        return points

    def __str__(self):
        return f"{self.username} ({self.user.email})"
