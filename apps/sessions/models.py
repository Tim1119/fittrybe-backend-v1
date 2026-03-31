"""
Sessions app models — training session logs.
"""

from django.db import models

from apps.core.models import BaseModel


class Session(BaseModel):
    class SessionType(models.TextChoices):
        PHYSICAL = "physical", "Physical"
        VIRTUAL = "virtual", "Virtual"

    class Status(models.TextChoices):
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"
        NO_SHOW = "no_show", "No Show"

    trainer = models.ForeignKey(
        "profiles.TrainerProfile",
        on_delete=models.CASCADE,
        related_name="sessions",
    )
    client = models.ForeignKey(
        "profiles.ClientProfile",
        on_delete=models.CASCADE,
        related_name="sessions",
    )
    session_date = models.DateField(db_index=True)
    session_time = models.TimeField(null=True, blank=True)
    duration_minutes = models.PositiveIntegerField(default=60)
    session_type = models.CharField(
        max_length=10,
        choices=SessionType.choices,
        default=SessionType.PHYSICAL,
    )
    virtual_platform = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.COMPLETED,
        db_index=True,
    )

    class Meta:
        ordering = ["-session_date", "-created_at"]
        verbose_name = "Session"
        verbose_name_plural = "Sessions"

    def __str__(self):
        return (
            f"Session({self.trainer} → {self.client}"
            f" on {self.session_date} [{self.status}])"
        )
