"""
Accounts serializers.
"""

import zxcvbn
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.accounts.models import User


def _check_password_strength(password):
    """Run Django validators then zxcvbn strength check."""
    try:
        validate_password(password)
    except DjangoValidationError as exc:
        raise serializers.ValidationError(list(exc.messages))

    result = zxcvbn.zxcvbn(password)
    if result["score"] < 2:
        suggestions = result["feedback"].get("suggestions", [])
        warning = result["feedback"].get("warning", "")
        msg = "Password is too weak."
        if warning:
            msg += f" {warning}"
        if suggestions:
            msg += " " + " ".join(suggestions)
        raise serializers.ValidationError(msg)


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True)
    role = serializers.ChoiceField(choices=User.Role.choices)

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate_password(self, value):
        _check_password_strength(value)
        return value

    def validate(self, attrs):
        if attrs["password"] != attrs["confirm_password"]:
            raise serializers.ValidationError(
                {"confirm_password": "Passwords do not match."}
            )
        return attrs

    def create(self, validated_data):
        validated_data.pop("confirm_password")
        return User.objects.create_user(
            email=validated_data["email"],
            password=validated_data["password"],
            role=validated_data["role"],
            is_active=False,
            is_email_verified=False,
        )


def _validate_terms_accepted(value):
    if not value:
        raise serializers.ValidationError("You must accept the terms to register.")
    return value


class TrainerRegisterSerializer(RegisterSerializer):
    display_name = serializers.CharField(max_length=100)
    terms_accepted = serializers.BooleanField()

    def validate_terms_accepted(self, value):
        return _validate_terms_accepted(value)

    def create(self, validated_data):
        display_name = validated_data.pop("display_name")
        validated_data.pop("terms_accepted")
        validated_data.pop("confirm_password")
        user = User.objects.create_user(
            email=validated_data["email"],
            password=validated_data["password"],
            role=validated_data["role"],
            is_active=False,
            is_email_verified=False,
        )
        user.display_name = display_name
        user.terms_accepted_at = timezone.now()
        user.save(update_fields=["display_name", "terms_accepted_at"])
        return user


class GymRegisterSerializer(RegisterSerializer):
    terms_accepted = serializers.BooleanField()

    def validate_terms_accepted(self, value):
        return _validate_terms_accepted(value)

    def create(self, validated_data):
        validated_data.pop("terms_accepted")
        validated_data.pop("confirm_password")
        user = User.objects.create_user(
            email=validated_data["email"],
            password=validated_data["password"],
            role=validated_data["role"],
            is_active=False,
            is_email_verified=False,
        )
        user.terms_accepted_at = timezone.now()
        user.save(update_fields=["terms_accepted_at"])
        return user


class ClientRegisterSerializer(RegisterSerializer):
    display_name = serializers.CharField(max_length=100)
    terms_accepted = serializers.BooleanField()

    def validate_terms_accepted(self, value):
        return _validate_terms_accepted(value)

    def create(self, validated_data):
        display_name = validated_data.pop("display_name")
        validated_data.pop("terms_accepted")
        validated_data.pop("confirm_password")
        user = User.objects.create_user(
            email=validated_data["email"],
            password=validated_data["password"],
            role=validated_data["role"],
            is_active=False,
            is_email_verified=False,
        )
        user.display_name = display_name
        user.terms_accepted_at = timezone.now()
        user.save(update_fields=["display_name", "terms_accepted_at"])
        return user


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["email"] = user.email
        token["role"] = user.role
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data["email"] = self.user.email
        data["role"] = self.user.role
        return data


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()


class ResetPasswordSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True)

    def validate_new_password(self, value):
        _check_password_strength(value)
        return value

    def validate(self, attrs):
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError(
                {"confirm_password": "Passwords do not match."}
            )
        return attrs


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True)

    def validate_new_password(self, value):
        _check_password_strength(value)
        return value

    def validate(self, attrs):
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError(
                {"confirm_password": "Passwords do not match."}
            )
        return attrs


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "email", "role", "is_email_verified", "created_at")
        read_only_fields = fields
