from django.apps import AppConfig


class ResultadosConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "resultados"
    verbose_name = "Resultados de Lotería"  # Opcional: nombre legible

    def ready(self):
        import resultados.signals  # noqa: F401
