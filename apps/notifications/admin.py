from django.contrib import admin

from .models import FCMDevice, Notification


@admin.register(FCMDevice)
class FCMDeviceAdmin(admin.ModelAdmin):
    list_display = ["user", "platform", "is_active", "last_used_at"]
    list_filter = ["platform", "is_active"]
    search_fields = ["user__email", "token"]


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["recipient", "notification_type", "title", "is_read", "created_at"]
    list_filter = ["notification_type", "is_read"]
    search_fields = ["recipient__email", "title"]
