from django.apps import AppConfig


class SchemesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "schemes"

    def ready(self):
        from . import checks  # noqa: F401
