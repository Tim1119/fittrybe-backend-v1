from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"

    def ready(self):
        import sys

        # Skip the reference data check when running management commands
        # that don't need the data to exist yet
        skip_commands = {
            "seed_app_data",
            "migrate",
            "makemigrations",
            "flush",
            "createsuperuser",
            "shell",
            "shell_plus",
            "test",
            "collectstatic",
            "showmigrations",
            "axes_reset",
        }
        if len(sys.argv) > 1 and sys.argv[1] in skip_commands:
            return
        from apps.core.startup import check_reference_data

        check_reference_data()
