from django.apps import AppConfig


class HordakConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "hordak"

    def ready(self):
        import hordak.receivers  # noqa
