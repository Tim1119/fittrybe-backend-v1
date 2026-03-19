"""
Accounts models.
Stub — full User model implementation added in Phase 2.
The custom User model must be declared here so Django can resolve AUTH_USER_MODEL.
"""

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Custom User model for Fit Trybe.
    Extends AbstractUser — additional fields added in Phase 2.
    """

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"

    def __str__(self):
        return self.email
