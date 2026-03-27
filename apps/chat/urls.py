from django.urls import path

from apps.chat.views import (
    ChatroomDetailView,
    ChatroomListView,
    ChatroomMemberListView,
    ChatroomUpdateView,
    DMMarkReadView,
    DMMessageListView,
    DMSendView,
    DMThreadListView,
    MarkReadView,
    MediaUploadView,
    MessageDeleteView,
    MessageListCreateView,
    MuteView,
    PinMessageView,
    PinnedMessageListView,
    RemoveMemberView,
    UnpinMessageView,
    UnreadCountView,
)

urlpatterns = [
    # CHAT-01 Community chatroom
    path("rooms/", ChatroomListView.as_view()),
    path("rooms/<int:pk>/", ChatroomDetailView.as_view()),
    path("rooms/<int:pk>/update/", ChatroomUpdateView.as_view()),
    path("rooms/<int:pk>/messages/", MessageListCreateView.as_view()),
    path(
        "rooms/<int:pk>/messages/<int:msg_pk>/",
        MessageDeleteView.as_view(),
    ),
    path("rooms/<int:pk>/upload/", MediaUploadView.as_view()),
    path("rooms/<int:pk>/pin/", PinnedMessageListView.as_view()),
    path("rooms/<int:pk>/pin/<int:msg_pk>/", PinMessageView.as_view()),
    path("rooms/<int:pk>/unpin/<int:msg_pk>/", UnpinMessageView.as_view()),
    path("rooms/<int:pk>/read/", MarkReadView.as_view()),
    path("rooms/<int:pk>/unread/", UnreadCountView.as_view()),
    path("rooms/<int:pk>/mute/", MuteView.as_view()),
    # CHAT-04 Member management
    path("rooms/<int:pk>/members/", ChatroomMemberListView.as_view()),
    path(
        "rooms/<int:pk>/members/<uuid:user_id>/",
        RemoveMemberView.as_view(),
    ),
    # CHAT-02 DM inbox
    path("dm/threads/", DMThreadListView.as_view()),
    # CHAT-03 DM thread
    path("dm/<uuid:user_id>/", DMSendView.as_view()),
    path("dm/<uuid:user_id>/messages/", DMMessageListView.as_view()),
    path("dm/<uuid:user_id>/read/", DMMarkReadView.as_view()),
]
