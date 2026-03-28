"""
Marketplace models — Product listings and enquiries.
"""

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from apps.core.models import BaseModel
from apps.profiles.models import ClientProfile, GymProfile, TrainerProfile


class Product(BaseModel):
    class Category(models.TextChoices):
        PROGRAM = "program", "Program"
        EQUIPMENT = "equipment", "Equipment"
        NUTRITION = "nutrition", "Nutrition"
        CLASS = "class", "Class"
        EBOOK = "ebook", "E-Book"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        SOLD_OUT = "sold_out", "Sold Out"
        ARCHIVED = "archived", "Archived"

    trainer = models.ForeignKey(
        TrainerProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="products",
    )
    gym = models.ForeignKey(
        GymProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="products",
    )
    name = models.CharField(max_length=200)
    description = models.TextField()
    category = models.CharField(choices=Category.choices, max_length=20, db_index=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="NGN")
    status = models.CharField(
        choices=Status.choices,
        max_length=10,
        default=Status.DRAFT,
        db_index=True,
    )
    # List of image URL strings, max 5
    images = models.JSONField(default=list, blank=True)
    is_featured = models.BooleanField(default=False, db_index=True)
    view_count = models.PositiveIntegerField(default=0)
    enquiry_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(trainer__isnull=False, gym__isnull=True)
                    | Q(trainer__isnull=True, gym__isnull=False)
                ),
                name="product_exactly_one_owner",
            )
        ]

    def __str__(self):
        owner = self.trainer or self.gym
        return f"{self.name} ({owner})"

    def clean(self):
        if bool(self.trainer_id) == bool(self.gym_id):
            raise ValidationError("Set exactly one of trainer or gym.")

    def get_owner_profile(self):
        return self.trainer or self.gym

    def get_owner_user(self):
        if self.trainer_id:
            return self.trainer.user
        return self.gym.user


class ProductEnquiry(BaseModel):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        RESPONDED = "responded", "Responded"
        CLOSED = "closed", "Closed"

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="enquiries",
    )
    client = models.ForeignKey(
        ClientProfile,
        on_delete=models.CASCADE,
        related_name="enquiries",
    )
    message = models.TextField(blank=True)
    status = models.CharField(
        choices=Status.choices,
        max_length=10,
        default=Status.OPEN,
        db_index=True,
    )
    trainer_response = models.TextField(blank=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        # One enquiry per client per product
        unique_together = ("product", "client")

    def __str__(self):
        return f"Enquiry by {self.client} on {self.product}"
