from django.urls import re_path

from apps.chat.consumers import ChatroomConsumer, DirectMessageConsumer

websocket_urlpatterns = [
    re_path(
        r"ws/chat/room/(?P<chatroom_id>\d+)/$",
        ChatroomConsumer.as_asgi(),
    ),
    re_path(
        r"ws/chat/dm/(?P<user_id>[0-9a-f-]+)/$",
        DirectMessageConsumer.as_asgi(),
    ),
]
