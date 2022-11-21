from django.apps import AppConfig


class HordakConfig(AppConfig):
    name = "hordak"

    def ready(self):
        import hordak.receivers  # noqa
