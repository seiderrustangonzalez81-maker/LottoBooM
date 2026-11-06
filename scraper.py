import requests
from datetime import time
from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_date, parse_time
from sorteos.models import Sorteo
from resultados.models import Resultado

URL_JSON = "https://raw.githubusercontent.com/seiderrustangonzalez81-maker/LottoBooM/main/resultados.json"

class Command(BaseCommand):
    help = "Carga resultados desde el JSON de GitHub a la BD"

    def handle(self, *args, **kwargs):
        try:
            resp = requests.get(URL_JSON, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error descargando JSON: {e}"))
            return

        creados = actualizados = errores = 0
        for item in data:
            try:
                nombre = item.get("sorteo_nombre", "").strip()
                if not nombre:
                    continue
                
                # Buscamos el sorteo en tu base de datos (ignorando mayúsculas/minúsculas)
                sorteo = Sorteo.objects.filter(nombre__iexact=nombre).first()
                if not sorteo:
                    self.stdout.write(self.style.WARNING(f"Sorteo no encontrado en BD: {nombre}"))
                    errores += 1
                    continue

                fecha = parse_date(item.get("fecha", ""))
                hora = parse_time(item.get("hora", "00:00:00")) or time(0, 0)
                if not fecha:
                    errores += 1
                    continue

                # Unimos los números en un string para el campo numero_ganador
                numeros = item.get("numeros", [])
                num_ganador = "-".join(numeros) if numeros else ""
                
                if not num_ganador:
                    continue

                defaults = {
                    # Si tu modelo tiene campos pick2, pick3, puedes llenarlos así:
                    "pick2": numeros[0] if len(numeros) > 0 else None,
                    "pick3": numeros[1] if len(numeros) > 1 else None,
                    "pick4": numeros[2] if len(numeros) > 2 else None,
                    "pick5": numeros[3] if len(numeros) > 3 else None,
                    
                    # Campos obligatorios de tu modelo
                    "numero_ganador": str(num_ganador)[:10],
                    "derivados": {},
                    "metadata": {"fuente": item.get("fuente", "")},
                    "procesamiento_estado": "pendiente",
                    "procesamiento_msg": "",
                    "premios_generados": 0,
                }

                # Actualiza o crea el resultado
                obj, created = Resultado.objects.update_or_create(
                    sorteo=sorteo, fecha=fecha, hora=hora, defaults=defaults,
                )
                if created: creados += 1
                else: actualizados += 1
                
            except Exception as e:
                errores += 1
                self.stdout.write(self.style.ERROR(f"Error en item {item}: {e}"))

        self.stdout.write(self.style.SUCCESS(
            f"Creados={creados}, Actualizados={actualizados}, Errores={errores}"
        ))
