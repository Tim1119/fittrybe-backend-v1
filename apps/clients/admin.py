from django.contrib import admin

from apps.clients.models import ClientMembership, InviteLink


@admin.register(ClientMembership)
class ClientMembershipAdmin(admin.ModelAdmin):
    list_display = (
        "client",
        "trainer",
        "gym",
        "status",
        "renewal_date",
        "sessions_count",
        "created_at",
    )
    list_filter = ("status",)
    search_fields = ("client__user__email",)
    raw_id_fields = ("client", "trainer", "gym")
    readonly_fields = ("created_at", "updated_at")


@admin.register(InviteLink)
class InviteLinkAdmin(admin.ModelAdmin):
    list_display = (
        "token",
        "trainer",
        "gym",
        "uses_count",
        "max_uses",
        "is_active",
        "expires_at",
    )
    list_filter = ("is_active",)
    raw_id_fields = ("trainer", "gym")
    readonly_fields = ("token", "created_at")
