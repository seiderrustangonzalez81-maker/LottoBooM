# sorteos/apps.py
from django.apps import AppConfig

class SorteosConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'sorteos'

    def ready(self):
        import sorteos.signals  # Esto carga las señales