from django.contrib import admin

from apps.sessions.models import Session


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = [
        "trainer",
        "client",
        "session_date",
        "session_type",
        "status",
        "duration_minutes",
    ]
    list_filter = ["status", "session_type"]
    search_fields = ["trainer__full_name", "client__username"]
    date_hierarchy = "session_date"
