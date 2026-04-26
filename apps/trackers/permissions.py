from rest_framework.permissions import BasePermission


class HasTrackerAddon(BasePermission):
    message = "Tracker add-on subscription required."

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.user.role != "client":
            return False
        try:
            return request.user.client_profile.tracker_addon_active
        except Exception:
            return False
