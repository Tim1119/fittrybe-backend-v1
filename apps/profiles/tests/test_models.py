"""Tests for profile models."""

import pytest
from django.core.exceptions import ValidationError

from apps.profiles.models import Availability, GymTrainer
from apps.profiles.tests.factories import (
    AvailabilityGymFactory,
    AvailabilityTrainerFactory,
    ClientProfileFactory,
    GymProfileFactory,
    GymTrainerFactory,
    ServiceGymFactory,
    ServiceTrainerFactory,
    SpecialisationFactory,
    TrainerProfileFactory,
)


@pytest.mark.django_db
class TestTrainerProfileModel:
    def test_slug_auto_generated(self):
        profile = TrainerProfileFactory(full_name="Alice Johnson")
        assert profile.slug
        assert "alice" in profile.slug.lower()

    def test_duplicate_names_get_unique_slugs(self):
        p1 = TrainerProfileFactory(full_name="Bob Smith")
        p2 = TrainerProfileFactory(full_name="Bob Smith")
        assert p1.slug != p2.slug

    def test_completion_percentage_zero_when_empty(self):
        profile = TrainerProfileFactory(
            full_name="",
            bio="",
            location="",
            profile_photo_url="",
            cover_photo_url="",
            years_experience=0,
            pricing_range="",
        )
        assert profile.profile_completion_percentage == 0

    def test_completion_percentage_100_when_all_filled(self):
        profile = TrainerProfileFactory(
            full_name="Full Name",
            bio="A bio here",
            location="Lagos",
            profile_photo_url="http://example.com/photo.jpg",
            cover_photo_url="http://example.com/cover.jpg",
            years_experience=5,
        )
        spec = SpecialisationFactory()
        profile.specialisations.add(spec)
        AvailabilityTrainerFactory(trainer=profile)
        ServiceTrainerFactory(trainer=profile)
        assert profile.profile_completion_percentage == 100

    def test_get_missing_fields_returns_empty_when_complete(self):
        profile = TrainerProfileFactory(
            bio="A bio",
            location="Lagos",
            profile_photo_url="http://example.com/p.jpg",
            cover_photo_url="http://example.com/c.jpg",
            years_experience=3,
        )
        spec = SpecialisationFactory()
        profile.specialisations.add(spec)
        AvailabilityTrainerFactory(trainer=profile)
        ServiceTrainerFactory(trainer=profile)
        assert profile.get_missing_fields() == []

    def test_get_missing_fields_lists_empty_required_fields(self):
        profile = TrainerProfileFactory()
        missing = profile.get_missing_fields()
        assert "bio" in missing
        assert "availability" in missing
        assert "services" in missing

    def test_get_public_url_contains_slug(self, settings):
        settings.FRONTEND_URL = "http://frontend.test"
        profile = TrainerProfileFactory()
        assert f"/trainer/{profile.slug}" in profile.get_public_url()

    def test_str(self):
        profile = TrainerProfileFactory(full_name="Jane Doe")
        assert "Jane Doe" in str(profile)


@pytest.mark.django_db
class TestGymProfileModel:
    def test_completion_starts_at_gym_name_and_admin_only(self):
        profile = GymProfileFactory()
        # gym_name(15) + admin_full_name(10) = 25
        assert profile.profile_completion_percentage == 25

    def test_completion_includes_availability_points(self):
        profile = GymProfileFactory(
            about="Great gym",
            location="Lagos",
            city="Lagos",
            logo_url="http://example.com/logo.jpg",
            cover_photo_url="http://example.com/cover.jpg",
            contact_phone="08012345678",
            business_email="gym@example.com",
        )
        AvailabilityGymFactory(gym=profile)
        assert profile.profile_completion_percentage == 100

    def test_get_public_url_contains_slug(self, settings):
        settings.FRONTEND_URL = "http://frontend.test"
        profile = GymProfileFactory()
        assert f"/gym/{profile.slug}" in profile.get_public_url()


@pytest.mark.django_db
class TestAvailabilityModel:
    def test_clean_raises_if_start_gte_end(self):
        av = AvailabilityTrainerFactory.build(start_time="10:00", end_time="09:00")
        with pytest.raises(ValidationError, match="before end time"):
            av.clean()

    def test_clean_raises_if_equal_times(self):
        av = AvailabilityTrainerFactory.build(start_time="10:00", end_time="10:00")
        with pytest.raises(ValidationError, match="before end time"):
            av.clean()

    def test_clean_ok_if_start_before_end(self):
        av = AvailabilityTrainerFactory.build(start_time="09:00", end_time="10:00")
        av.clean()  # should not raise

    def test_clean_raises_if_no_trainer_or_gym(self):
        av = Availability(
            trainer=None,
            gym=None,
            day_of_week="monday",
            start_time="09:00",
            end_time="10:00",
        )
        with pytest.raises(ValidationError, match="must belong to"):
            av.clean()

    def test_clean_raises_if_both_trainer_and_gym(self):
        trainer_profile = TrainerProfileFactory()
        gym_profile = GymProfileFactory()
        av = Availability(
            trainer=trainer_profile,
            gym=gym_profile,
            day_of_week="monday",
            start_time="09:00",
            end_time="10:00",
        )
        with pytest.raises(ValidationError, match="cannot belong to both"):
            av.clean()

    def test_str_includes_day(self):
        av = AvailabilityTrainerFactory()
        assert "monday" in str(av)


@pytest.mark.django_db
class TestGymTrainerModel:
    def test_unique_together_enforced(self):
        from django.db import IntegrityError

        gt = GymTrainerFactory()
        with pytest.raises(IntegrityError):
            GymTrainer.objects.create(gym=gt.gym, trainer=gt.trainer)

    def test_str(self):
        gt = GymTrainerFactory()
        assert gt.gym.gym_name in str(gt)
        assert gt.trainer.full_name in str(gt)


@pytest.mark.django_db
class TestClientProfileModel:
    def test_username_auto_generated_from_email(self):
        profile = ClientProfileFactory()
        local = profile.user.email.split("@")[0]
        assert profile.username.startswith(local)

    def test_completion_zero_when_empty(self):
        profile = ClientProfileFactory(display_name="", profile_photo_url="")
        assert profile.profile_completion_percentage == 0

    def test_completion_100_when_all_filled(self):
        profile = ClientProfileFactory(
            display_name="Joe",
            profile_photo_url="http://example.com/p.jpg",
        )
        assert profile.profile_completion_percentage == 100

    def test_str_includes_username(self):
        profile = ClientProfileFactory()
        assert profile.username in str(profile)


@pytest.mark.django_db
class TestSpecialisationModel:
    def test_slug_auto_generated(self):
        spec = SpecialisationFactory(name="Weight Loss")
        assert spec.slug
        assert "weight" in spec.slug.lower()

    def test_str(self):
        spec = SpecialisationFactory(name="HIIT")
        assert str(spec) == "HIIT"


@pytest.mark.django_db
class TestServiceModel:
    def test_trainer_service_str(self):
        svc = ServiceTrainerFactory(name="Personal Training 1-on-1")
        assert str(svc) == "Personal Training 1-on-1"

    def test_gym_service_str(self):
        svc = ServiceGymFactory(name="Group Classes")
        assert str(svc) == "Group Classes"

    def test_clean_raises_without_trainer_or_gym(self):
        svc = ServiceTrainerFactory.build(trainer=None, gym=None)
        with pytest.raises(Exception, match="trainer or gym"):
            svc.clean()

    def test_clean_raises_with_both_trainer_and_gym(self):
        trainer = TrainerProfileFactory()
        gym = GymProfileFactory()
        svc = ServiceTrainerFactory.build(trainer=trainer, gym=gym)
        with pytest.raises(Exception, match="cannot belong to both"):
            svc.clean()

    def test_trainer_completion_increases_with_service(self):
        profile = TrainerProfileFactory(
            bio="bio",
            location="Lagos",
            profile_photo_url="http://x.com/p.jpg",
            cover_photo_url="http://x.com/c.jpg",
            years_experience=3,
        )
        before = profile.profile_completion_percentage
        ServiceTrainerFactory(trainer=profile)
        assert profile.profile_completion_percentage == before + 10

    def test_services_missing_field_cleared_after_adding_service(self):
        profile = TrainerProfileFactory()
        assert "services" in profile.get_missing_fields()
        ServiceTrainerFactory(trainer=profile)
        assert "services" not in profile.get_missing_fields()

    def test_gym_service_saved_with_correct_fk(self):
        svc = ServiceGymFactory(name="Yoga Class")
        assert svc.gym is not None
        assert svc.trainer is None
