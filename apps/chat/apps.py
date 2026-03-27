from django.apps import AppConfig


class ChatConfig(AppConfig):
    name = "apps.chat"

    def ready(self):
        import apps.chat.signals  # noqa: F401
