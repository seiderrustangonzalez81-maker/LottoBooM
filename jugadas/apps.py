from django.apps import AppConfig


class JugadasConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "jugadas"

    def ready(self):
        import jugadas.signals  # noqa: F401
