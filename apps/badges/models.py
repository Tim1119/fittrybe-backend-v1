"""
Badges app models — Badge definitions and assignments.
"""

from django.db import models

from apps.core.models import BaseModel


class Badge(BaseModel):
    class BadgeType(models.TextChoices):
        MILESTONE = "milestone", "Milestone"
        STREAK = "streak", "Streak"
        WEEKLY_TOP = "weekly_top", "Weekly Top"
        MANUAL = "manual", "Manual"

    name = models.CharField(max_length=100, unique=True)
    badge_type = models.CharField(
        max_length=20,
        choices=BadgeType.choices,
        db_index=True,
    )
    description = models.TextField(blank=True)
    icon_url = models.CharField(max_length=500, blank=True)
    is_system = models.BooleanField(default=False)
    milestone_threshold = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text=(
            "Session count that triggers this badge. " "Only for badge_type=milestone."
        ),
    )

    class Meta:
        ordering = ["badge_type", "milestone_threshold", "name"]
        verbose_name = "Badge"
        verbose_name_plural = "Badges"

    def __str__(self):
        return f"{self.name} ({self.badge_type})"


class BadgeAssignment(BaseModel):
    badge = models.ForeignKey(
        Badge,
        on_delete=models.CASCADE,
        related_name="assignments",
    )
    client = models.ForeignKey(
        "profiles.ClientProfile",
        on_delete=models.CASCADE,
        related_name="badge_assignments",
    )
    trainer = models.ForeignKey(
        "profiles.TrainerProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="badge_assignments_given",
    )
    gym = models.ForeignKey(
        "profiles.GymProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="badge_assignments_given",
    )
    assigned_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="badges_assigned",
    )
    note = models.TextField(blank=True)
    post_to_chatroom = models.BooleanField(default=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Badge Assignment"
        verbose_name_plural = "Badge Assignments"

    def __str__(self):
        return f"{self.badge.name} → {self.client}"
