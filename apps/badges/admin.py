from django.contrib import admin

from apps.badges.models import Badge, BadgeAssignment


@admin.register(Badge)
class BadgeAdmin(admin.ModelAdmin):
    list_display = ["name", "badge_type", "milestone_threshold", "is_system"]
    list_filter = ["badge_type", "is_system"]


@admin.register(BadgeAssignment)
class BadgeAssignmentAdmin(admin.ModelAdmin):
    list_display = [
        "badge",
        "client",
        "trainer",
        "assigned_by",
        "post_to_chatroom",
        "created_at",
    ]
    list_filter = ["badge__badge_type"]
    search_fields = ["client__username", "badge__name"]
