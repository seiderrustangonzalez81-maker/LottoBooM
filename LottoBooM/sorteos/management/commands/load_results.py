import requests
from django.core.management.base import BaseCommand
from sorteos.models import Sorteo  # importamos Sorteo, ajustaremos Resultado cuando lo identifiquemos

URL_JSON = "https://raw.githubusercontent.com/seiderrustangonzalez81-maker/LottoBooM/main/resultados.json"

class Command(BaseCommand):
    help = 'Carga resultados desde el JSON de GitHub a la base de datos'

    def handle(self, *args, **kwargs):
        try:
            resp = requests.get(URL_JSON, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"No se pudo descargar el JSON: {e}"))
            return

        self.stdout.write(self.style.NOTICE(f"Descargados {len(data)} registros."))

        for item in data:
            # TODO: reemplazar por el modelo real cuando lo confirmemos
            # Por ahora solo imprimimos para verificar la estructura
            self.stdout.write(f"Item: {item}")

        self.stdout.write(self.style.SUCCESS("Proceso terminado."))
