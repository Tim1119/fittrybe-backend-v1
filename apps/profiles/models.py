"""
Profile models — TrainerProfile, GymProfile, GymTrainer.
"""

from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class TrainerProfile(BaseModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="trainer_profile",
    )
    bio = models.TextField(blank=True)
    specializations = models.JSONField(default=list)
    years_experience = models.PositiveIntegerField(default=0)
    certifications = models.JSONField(default=list)
    avatar = models.ImageField(upload_to="avatars/trainers/", blank=True)
    is_published = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Trainer Profile"
        verbose_name_plural = "Trainer Profiles"

    def __str__(self):
        return f"Trainer: {self.user.email}"


class GymProfile(BaseModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="gym_profile",
    )
    gym_name = models.CharField(max_length=200)
    bio = models.TextField(blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, default="Nigeria")
    logo = models.ImageField(upload_to="avatars/gyms/", blank=True)
    amenities = models.JSONField(default=list)
    is_published = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Gym Profile"
        verbose_name_plural = "Gym Profiles"

    def __str__(self):
        return f"Gym: {self.gym_name}"


class GymTrainer(BaseModel):
    """Links a trainer account to a gym."""

    gym = models.ForeignKey(
        GymProfile, on_delete=models.CASCADE, related_name="gym_trainers"
    )
    trainer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="gym_memberships",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Gym Trainer"
        verbose_name_plural = "Gym Trainers"
        unique_together = ("gym", "trainer")

    def __str__(self):
        return f"{self.trainer.email} @ {self.gym.gym_name}"
