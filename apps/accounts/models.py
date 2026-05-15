"""
Accounts models.
"""

import uuid
from datetime import timedelta

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        extra_fields.setdefault("is_active", True)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    class Role(models.TextChoices):
        TRAINER = "trainer", "Trainer"
        GYM = "gym", "Gym"
        CLIENT = "client", "Client"

    class OnboardingStatus(models.TextChoices):
        NOT_STARTED = "not_started", "Not Started"
        IN_PROGRESS = "in_progress", "In Progress"
        COMPLETED = "completed", "Completed"

    username = None

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    is_active = models.BooleanField(default=True, db_index=True)
    role = models.CharField(max_length=10, choices=Role.choices, db_index=True)
    is_email_verified = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Profile
    country = models.CharField(max_length=100, blank=True)
    terms_accepted_at = models.DateTimeField(null=True, blank=True)

    # Soft delete
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)

    # Onboarding tracking
    onboarding_status = models.CharField(
        max_length=20,
        choices=OnboardingStatus.choices,
        default=OnboardingStatus.NOT_STARTED,
        db_index=True,
    )
    onboarding_completed_at = models.DateTimeField(null=True, blank=True)
    is_first_login = models.BooleanField(default=True)
    onboarding_step = models.IntegerField(default=0)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"

    def __str__(self):
        return self.email

    def delete(self, using=None, keep_parents=False):
        from django.utils import timezone

        self.deleted_at = timezone.now()
        self.is_active = False
        self.save(update_fields=["deleted_at", "is_active"])

    def hard_delete(self):
        super().delete()

    def restore(self):
        self.deleted_at = None
        self.is_active = True
        self.save(update_fields=["deleted_at", "is_active"])

    @property
    def is_deleted(self):
        return self.deleted_at is not None

    @property
    def full_name_display(self):
        try:
            if self.role == "trainer":
                return self.trainer_profile.full_name
            elif self.role == "gym":
                return self.gym_profile.full_name
            elif self.role == "client":
                return self.client_profile.full_name
        except Exception:
            pass
        return self.email.split("@")[0]

    def complete_onboarding(self):
        from django.utils import timezone

        self.onboarding_status = self.OnboardingStatus.COMPLETED
        self.onboarding_completed_at = timezone.now()
        self.save(update_fields=["onboarding_status", "onboarding_completed_at"])


class OTPCode(models.Model):
    class Purpose(models.TextChoices):
        EMAIL_VERIFICATION = "email_verification", "Email Verification"
        PASSWORD_RESET = "password_reset", "Password Reset"

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="otp_codes",
    )
    code = models.CharField(max_length=6)
    purpose = models.CharField(max_length=30, choices=Purpose.choices)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    attempts = models.IntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]

    def is_valid(self):
        from django.utils import timezone

        return (
            not self.is_used and self.expires_at > timezone.now() and self.attempts < 5
        )

    def __str__(self):
        return f"{self.user.email} — {self.purpose} — {self.code}"


def generate_otp(user, purpose):
    import random

    from django.utils import timezone

    OTPCode.objects.filter(
        user=user,
        purpose=purpose,
        is_used=False,
    ).update(is_used=True)
    code = f"{random.randint(0, 999999):06d}"
    expires_at = timezone.now() + timedelta(minutes=10)
    return OTPCode.objects.create(
        user=user,
        code=code,
        purpose=purpose,
        expires_at=expires_at,
    )


def verify_otp(user, code, purpose):
    try:
        otp = OTPCode.objects.filter(
            user=user,
            purpose=purpose,
            is_used=False,
        ).latest("created_at")
    except OTPCode.DoesNotExist:
        return None, "Invalid or expired code."

    otp.attempts += 1
    otp.save(update_fields=["attempts"])

    if not otp.is_valid():
        return None, "Code has expired or too many attempts. Request a new code."

    if otp.code != code:
        return None, "Invalid code."

    otp.is_used = True
    otp.save(update_fields=["is_used"])
    return otp, None
