from django.contrib import admin

from apps.profiles.models import (
    Availability,
    Certification,
    ClientProfile,
    GymProfile,
    GymTrainer,
    Service,
    Specialisation,
    TrainerProfile,
)


class AvailabilityTrainerInline(admin.TabularInline):
    model = Availability
    fk_name = "trainer"
    extra = 0
    fields = (
        "day_of_week",
        "start_time",
        "end_time",
        "session_type",
        "duration_minutes",
    )


class AvailabilityGymInline(admin.TabularInline):
    model = Availability
    fk_name = "gym"
    extra = 0
    fields = (
        "day_of_week",
        "start_time",
        "end_time",
        "session_type",
        "duration_minutes",
    )


class CertificationInline(admin.TabularInline):
    model = Certification
    extra = 0
    fields = ("name", "issuing_body", "year_obtained")


class ServiceTrainerInline(admin.TabularInline):
    model = Service
    fk_name = "trainer"
    extra = 0
    fields = ("name", "description", "session_type", "display_order")


class ServiceGymInline(admin.TabularInline):
    model = Service
    fk_name = "gym"
    extra = 0
    fields = ("name", "description", "session_type", "display_order")


@admin.register(TrainerProfile)
class TrainerProfileAdmin(admin.ModelAdmin):
    list_display = (
        "full_name",
        "user",
        "trainer_type",
        "is_published",
        "wizard_step",
        "avg_rating",
    )
    list_filter = ("trainer_type", "is_published", "wizard_completed")
    search_fields = ("full_name", "user__email", "location")
    raw_id_fields = ("user",)
    inlines = [AvailabilityTrainerInline, CertificationInline, ServiceTrainerInline]
    readonly_fields = ("slug", "avg_rating", "rating_count", "created_at", "updated_at")


@admin.register(GymProfile)
class GymProfileAdmin(admin.ModelAdmin):
    list_display = (
        "gym_name",
        "user",
        "city",
        "is_published",
        "wizard_step",
    )
    list_filter = ("is_published", "wizard_completed")
    search_fields = ("gym_name", "user__email", "city", "location")
    raw_id_fields = ("user",)
    inlines = [AvailabilityGymInline, ServiceGymInline]
    readonly_fields = ("slug", "avg_rating", "rating_count", "created_at", "updated_at")


@admin.register(Specialisation)
class SpecialisationAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_predefined")
    list_filter = ("is_predefined",)
    search_fields = ("name",)
    readonly_fields = ("slug",)


@admin.register(GymTrainer)
class GymTrainerAdmin(admin.ModelAdmin):
    list_display = ("trainer", "gym", "role")
    list_filter = ("role",)
    raw_id_fields = ("trainer", "gym")


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "session_type", "display_order", "trainer", "gym")
    list_filter = ("session_type",)
    search_fields = ("name", "trainer__full_name", "gym__gym_name")
    raw_id_fields = ("trainer", "gym")


@admin.register(ClientProfile)
class ClientProfileAdmin(admin.ModelAdmin):
    list_display = ("username", "display_name", "user")
    search_fields = ("username", "user__email", "display_name")
    raw_id_fields = ("user",)
    readonly_fields = ("username", "created_at", "updated_at")
