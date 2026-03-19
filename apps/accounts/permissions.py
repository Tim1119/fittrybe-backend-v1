"""
Custom DRF permission classes for Fit Trybe role-based access.
"""

from rest_framework.permissions import BasePermission


class IsTrainer(BasePermission):
    message = "Only trainers can perform this action."

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == "trainer"


class IsGym(BasePermission):
    message = "Only gym accounts can perform this action."

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == "gym"


class IsClient(BasePermission):
    message = "Only clients can perform this action."

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == "client"


class IsTrainerOrGym(BasePermission):
    message = "Only trainers or gym accounts can perform this action."

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in ("trainer", "gym")


class IsVerified(BasePermission):
    message = "Please verify your email address first."

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_email_verified
