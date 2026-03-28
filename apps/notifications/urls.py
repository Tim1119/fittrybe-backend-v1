from django.urls import path

from .views import (
    FCMDeviceRegisterView,
    FCMDeviceUnregisterView,
    NotificationListView,
    NotificationMarkAllReadView,
    NotificationMarkReadView,
    UnreadCountView,
)

urlpatterns = [
    path("device/", FCMDeviceRegisterView.as_view()),
    path("device/<str:token>/", FCMDeviceUnregisterView.as_view()),
    path("", NotificationListView.as_view()),
    path("unread-count/", UnreadCountView.as_view()),
    path("read-all/", NotificationMarkAllReadView.as_view()),
    path("<int:pk>/read/", NotificationMarkReadView.as_view()),
]
