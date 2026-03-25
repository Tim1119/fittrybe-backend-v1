"""
Clients app models — ClientMembership and InviteLink.
"""

import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, UniqueConstraint
from django.utils import timezone

from apps.core.models import BaseModel


class ClientMembership(BaseModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        LAPSED = "lapsed", "Lapsed"
        PENDING = "pending", "Pending"
        SUSPENDED = "suspended", "Suspended"

    client = models.ForeignKey(
        "profiles.ClientProfile",
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    trainer = models.ForeignKey(
        "profiles.TrainerProfile",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="client_memberships",
    )
    gym = models.ForeignKey(
        "profiles.GymProfile",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="client_memberships",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    renewal_date = models.DateField(null=True, blank=True)
    payment_amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    payment_currency = models.CharField(max_length=3, default="NGN")
    payment_notes = models.TextField(blank=True)
    last_reminder_at = models.DateTimeField(null=True, blank=True)
    sessions_count = models.IntegerField(default=0)
    notes = models.TextField(blank=True)

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["client", "trainer"],
                condition=Q(trainer__isnull=False),
                name="unique_client_trainer",
            ),
            UniqueConstraint(
                fields=["client", "gym"],
                condition=Q(gym__isnull=False),
                name="unique_client_gym",
            ),
        ]

    def clean(self):
        if bool(self.trainer_id) == bool(self.gym_id):
            raise ValidationError(
                "Set exactly one of trainer or gym, not both or neither."
            )

    def __str__(self):
        owner = self.trainer.full_name if self.trainer_id else self.gym.gym_name
        return f"{self.client} → {owner} [{self.status}]"


class InviteLink(models.Model):
    trainer = models.ForeignKey(
        "profiles.TrainerProfile",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="invite_links",
    )
    gym = models.ForeignKey(
        "profiles.GymProfile",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="invite_links",
    )
    token = models.CharField(max_length=64, unique=True, db_index=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    max_uses = models.IntegerField(null=True, blank=True)
    uses_count = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = uuid.uuid4().hex + uuid.uuid4().hex  # 64 chars
        super().save(*args, **kwargs)

    def is_valid(self):
        if not self.is_active:
            return False, "This invite link has been deactivated."
        if self.expires_at and self.expires_at < timezone.now():
            return False, "This invite link has expired."
        if self.max_uses and self.uses_count >= self.max_uses:
            return False, "This invite link has reached its maximum uses."
        return True, None

    def clean(self):
        if bool(self.trainer_id) == bool(self.gym_id):
            raise ValidationError(
                "Set exactly one of trainer or gym, not both or neither."
            )

    def __str__(self):
        owner = self.trainer.full_name if self.trainer_id else self.gym.gym_name
        return f"Invite({owner}) uses={self.uses_count}"
