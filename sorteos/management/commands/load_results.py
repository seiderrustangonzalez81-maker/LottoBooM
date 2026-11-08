import requests
import unicodedata
from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_date
from django.contrib.auth.models import User
from sorteos.models import Sorteo
from resultados.models import Resultado
from resultados.views import procesar_resultado

URL_JSON = "https://raw.githubusercontent.com/seiderrustangonzalez81-maker/LottoBooM/main/resultados.json"

MAPEO_NOMBRES = {
    "Anguilla 8AM": "Anguila 8 AM", "Anguilla 9AM": "Anguila 9 AM",
    "Anguilla 10AM": "Anguila 10 AM", "Anguilla 11AM": "Anguila 11 AM",
    "Anguilla 12PM": "Anguila 12 PM", "Anguilla 1PM": "Anguila 1 PM",
    "Anguilla 2PM": "Anguila 2 PM", "Anguilla 3PM": "Anguila 3 PM",
    "Anguilla 4PM": "Anguila 4 PM", "Anguilla 5PM": "Anguila 5 PM",
    "Anguilla 6PM": "Anguila 6 PM", "Anguilla 7PM": "Anguila 7 PM",
    "Anguilla 8PM": "Anguila 8 PM", "Anguilla 9PM": "Anguila 9 PM",
    "Anguilla 10PM": "Anguila 10 PM",
    "Haiti Bolet 9:30 AM": "Haiti Bolet 9:30 AM",
    "Haiti Bolet 10:30 AM": "Haiti Bolet 10:30 AM",
    "Haiti Bolet 11:30 AM": "Haiti Bolet 11:30 AM",
    "Haiti Bolet 5:30 PM": "Haiti Bolet 5:30 PM",
    "Haiti Bolet 6:30 PM": "Haiti Bolet 6:30 PM",
    "Haiti Bolet 7:30 PM": "Haiti Bolet 7:30 PM",
    "Nacional Gana Más": "Nacional Gana Más", "Nacional Noche": "Nacional Noche",
    "Leidsa": "Leidsa 8:55 PM",
    "Loteka Tarde": "Loteka 1:30 PM", "Loteka": "Loteka 7:55 PM",
    "La Primera": "La Primera", "La Primera Noche": "La Primera Noche",
    "La Suerte": "La Suerte", "La Suerte 6PM": "La Suerte 6PM",
    "LoteDom": "Lotedom", "LoteDom Noche": "Lotedom Noche",
    "King Lottery Día": "King Lottery 12:30 PM", "King Lottery Noche": "King Lottery 7:30 PM",
    "El Quemaito Mayor": "El Quemaito Mayor", "El Quemaito Mayor Noche": "El Quemaito Mayor Noche",
    "El Quinielón Día": "El Quinielón Día", "El Quinielón Noche": "El Quinielón Noche",
    "Real": "Real", "Real Noche": "Real Noche",
    "Texas Mañana": "Texas 10:20 AM", "Texas Día": "Texas 11 AM",
    "Texas Tarde": "Texas 7 PM", "Texas Noche": "Texas 11 PM",
    "Tennessee Mañana": "Tennessee 10:20 AM", "Tennessee Día": "Tennessee 1:20 PM",
    "Tennessee Tarde": "Tennessee 7:20 PM",
    "Georgia Día": "Georgia 12:30 PM", "Georgia Tarde": "Georgia 7 PM", "Georgia Noche": "Georgia 11:34 PM",
    "Florida Tarde": "Florida 1:35 PM", "Florida Noche": "Florida 9:50 PM",
    "New York Tarde": "New York 2:30 PM", "New York Noche": "New York 10:30 PM",
    "New Jersey Tarde": "New Jersey 12:50 PM", "New Jersey Noche": "New Jersey 10:50 PM",
}

def normalizar_texto(texto):
    """Quita acentos y pasa a minúsculas para comparar de forma segura."""
    if not texto: return ""
    texto = unicodedata.normalize('NFD', str(texto))
    texto = ''.join(c for c in texto if unicodedata.category(c) != 'Mn')
    return texto.lower().strip()

class FakeRequest:
    def __init__(self, user): self.user = user

class Command(BaseCommand):
    help = "Carga resultados desde EnLoteria y calcula premios automáticamente."

    def handle(self, *args, **kwargs):
        try:
            resp = requests.get(URL_JSON, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error descargando JSON: {e}"))
            return

        admin = User.objects.filter(is_superuser=True).first()
        if not admin:
            self.stdout.write(self.style.ERROR("No hay superusuario"))
            return
        req = FakeRequest(admin)

        # Creamos un diccionario auxiliar normalizado para búsquedas sin acentos
        mapeo_normalizado = {normalizar_texto(k): v for k, v in MAPEO_NOMBRES.items()}

        creados = actualizados = errores = premios_ok = premios_err = 0
        for item in data:
            try:
                nombre_web = item.get("sorteo_nombre", "").strip()
                
                # 1. Búsqueda exacta
                nombre_db = MAPEO_NOMBRES.get(nombre_web)
                
                # 2. Si falla, búsqueda normalizada (sin acentos)
                if not nombre_db:
                    nombre_db = mapeo_normalizado.get(normalizar_texto(nombre_web))
                    
                if not nombre_db:
                    continue

                sorteo = Sorteo.objects.filter(nombre__iexact=nombre_db).first()
                if not sorteo:
                    continue

                fecha = parse_date(item.get("fecha", ""))
                if not fecha: continue

                numeros = item.get("numeros", [])
                num_ganador = "-".join(numeros) if numeros else ""
                if not num_ganador: continue

                defaults = {
                    "hora": sorteo.hora_salida,
                    "numero_ganador": str(num_ganador)[:10],
                    "fijo": numeros[0] if len(numeros) > 0 else None,
                    "corrido_1": numeros[1] if len(numeros) > 1 else None,
                    "corrido_2": numeros[2] if len(numeros) > 2 else None,
                    "pick3": numeros[2] if len(numeros) == 3 else None,
                    "derivados": {},
                    "metadata": {"fuente": item.get("fuente", "")},
                    "procesamiento_estado": "pendiente",
                    "procesamiento_msg": "",
                    "premios_generados": 0,
                }

                obj, created = Resultado.objects.update_or_create(
                    sorteo=sorteo, fecha=fecha, defaults=defaults
                )
                if created:
                    creados += 1
                    self.stdout.write(self.style.SUCCESS(f"✅ Nuevo: {nombre_db} -> {num_ganador}"))
                else:
                    actualizados += 1

                try:
                    datos = {
                        'sorteo': obj.sorteo, 'fecha': obj.fecha, 'hora': obj.hora,
                        'pick2': obj.pick2 or '', 'pick3': obj.pick3 or '',
                        'pick4': obj.pick4 or '', 'pick5': obj.pick5 or '',
                        'fijo': obj.fijo or '', 'corrido_1': obj.corrido_1 or '',
                        'corrido_2': obj.corrido_2 or '', 'pf': obj.pf or '',
                        'centena_corrida_1': obj.centena_corrida_1 or '',
                        'centena_corrida_2': obj.centena_corrida_2 or '',
                    }
                    resultado_obj, premios_count = procesar_resultado(req, datos, resultado_existente=obj)
                    obj.premios_generados = premios_count
                    obj.procesamiento_estado = 'completado'
                    obj.save(update_fields=['premios_generados', 'procesamiento_estado'])
                    premios_ok += 1
                except Exception as pe:
                    premios_err += 1
                    self.stdout.write(self.style.WARNING(f"⚠️ Premios {nombre_db}: {pe}"))

            except Exception as e:
                errores += 1
                self.stdout.write(self.style.ERROR(f"Error: {e}"))

        self.stdout.write(self.style.SUCCESS(
            f"Resumen -> Creados={creados}, Actualizados={actualizados}, "
            f"Premios OK={premios_ok}, Premios FAIL={premios_err}, Errores={errores}"
        ))
