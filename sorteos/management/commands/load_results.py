import requests
import unicodedata
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_date
from django.contrib.auth.models import User
from sorteos.models import Sorteo
from resultados.models import Resultado
from resultados.views import procesar_resultado

URL_JSON = "https://raw.githubusercontent.com/seiderrustangonzalez81-maker/LottoBooM/main/resultados.json"

MAPEO_NOMBRES = {
    # DOMINICANAS Y OTRAS
    "Anguilla 8AM": "Anguila 8 AM", "Anguilla 9AM": "Anguila 9 AM",
    "Anguilla 10AM": "Anguila 10 AM", "Anguilla 11AM": "Anguila 11 AM",
    "Anguilla 12PM": "Anguila 12 PM", "Anguilla 1PM": "Anguila 1 PM",
    "Anguilla 2PM": "Anguila 2 PM", "Anguilla 3PM": "Anguila 3 PM",
    "Anguilla 4PM": "Anguila 4 PM", "Anguilla 5PM": "Anguila 5 PM",
    "Anguilla 6PM": "Anguila 6 PM", "Anguilla 7PM": "Anguila 7 PM",
    "Anguilla 8PM": "Anguila 8 PM", "Anguilla 9PM": "Anguila 9 PM",
    "Anguilla 10PM": "Anguila 10 PM",
    "Haiti Bolet 9:30 AM": "Haiti Bolet 9:30 AM", "Haiti Bolet 10:30 AM": "Haiti Bolet 10:30 AM",
    "Haiti Bolet 11:30 AM": "Haiti Bolet 11:30 AM", "Haiti Bolet 5:30 PM": "Haiti Bolet 5:30 PM",
    "Haiti Bolet 6:30 PM": "Haiti Bolet 6:30 PM", "Haiti Bolet 7:30 PM": "Haiti Bolet 7:30 PM",
    "Nacional Gana Más": "Nacional Gana Más", "Nacional Noche": "Nacional Noche",
    "Leidsa": "Leidsa 8:55 PM", "Loteka Tarde": "Loteka 1:30 PM", "Loteka": "Loteka 7:55 PM",
    "La Primera": "La Primera", "La Primera Noche": "La Primera Noche",
    "La Suerte": "La Suerte", "La Suerte 6PM": "La Suerte 6PM",
    "LoteDom": "Lotedom", "LoteDom Noche": "Lotedom Noche",
    "King Lottery Día": "King Lottery 12:30 PM", "King Lottery Noche": "King Lottery 7:30 PM",
    "El Quemaito Mayor": "El Quemaito Mayor", "El Quemaito Mayor Noche": "El Quemaito Mayor Noche",
    "El Quinielón Día": "El Quinielón Día", "El Quinielón Noche": "El Quinielón Noche",
    "Real": "Real", "Real Noche": "Real Noche",

    # USA - LotteryUSA (Fuente Oficial)
    "Texas 1:20 PM": "Texas 1:20 PM", "Texas 10:12 PM": "Texas 11 PM",
    "Florida 1:35 PM": "Florida 1:35 PM", "Florida 9:45 PM": "Florida 9:50 PM",
    "New York 2:30 PM": "New York 2:30 PM", "New York 10:30 PM": "New York 10:30 PM",
    "New Jersey 12:50 PM": "New Jersey 12:50 PM", "New Jersey 10:57 PM": "New Jersey 10:50 PM",
    "Georgia 12:30 PM": "Georgia 12:30 PM", "Georgia 11:34 PM": "Georgia 11:40 PM",
    "Tennessee 1:20 PM": "Tennessee 1:20 PM", "Tennessee 6:30 PM": "Tennessee 7:20 PM",

    # USA - Enloteria (Fallback: Solo si lotteryusa falla o para sacar Fijo/Corridos)
    "Georgia Día": "Georgia 12:30 PM", "Georgia Tarde": "Georgia 7 PM",
    "Florida Tarde": "Florida 9:50 PM", "Florida Noche": "Florida 9:50 PM",
    "New York Tarde": "New York 2:30 PM", "New York Noche": "New York 10:30 PM",
    "New Jersey Tarde": "New Jersey 12:50 PM", "Texas Tarde": "Texas 7 PM",
    "Tennessee Día": "Tennessee 1:20 PM",
}

TZ_CUBA = ZoneInfo('America/Havana')
TZ_ESTE = ZoneInfo('America/New_York')
DIAS_ES = {0: 'lunes', 1: 'martes', 2: 'miercoles', 3: 'jueves', 4: 'viernes', 5: 'sabado', 6: 'domingo'}

def normalizar_texto(texto):
    if not texto: return ""
    texto = unicodedata.normalize('NFD', str(texto))
    texto = ''.join(c for c in texto if unicodedata.category(c) != 'Mn')
    return texto.lower().strip()

def temporada_actual():
    offset = datetime.now(TZ_ESTE).utcoffset()
    return 'invierno' if offset == timedelta(hours=-5) else 'verano'

def sorteo_corre_hoy(sorteo, dia_actual, temporada):
    horarios = sorteo.horarios
    if not horarios or not isinstance(horarios, dict): return True
    bloque = horarios.get(temporada) or horarios.get('invierno') or {}
    if not bloque: return True
    valor = bloque.get(dia_actual)
    return bool(valor and str(valor).strip())

class FakeRequest:
    def __init__(self, user): self.user = user

class Command(BaseCommand):
    help = "Carga resultados y calcula premios."

    def handle(self, *args, **kwargs):
        try:
            resp = requests.get(URL_JSON, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error descargando JSON: {e}"))
            return

        admin = User.objects.filter(is_superuser=True).first()
        if not admin: return
        req = FakeRequest(admin)

        mapeo_normalizado = {normalizar_texto(k): v for k, v in MAPEO_NOMBRES.items()}
        ahora_cuba = datetime.now(TZ_CUBA)
        hoy_cuba = ahora_cuba.date()
        ayer_cuba = hoy_cuba - timedelta(days=1)
        dia_actual = DIAS_ES[ahora_cuba.weekday()]
        temporada = temporada_actual()

        self.stdout.write(f"Día actual: {dia_actual} | Temporada: {temporada}")

        creados = actualizados = errores = premios_ok = 0

        for item in data:
            nombre_web = item.get("sorteo_nombre", "").strip()
            if not nombre_web: continue

            nombre_db = (MAPEO_NOMBRES.get(nombre_web) or mapeo_normalizado.get(normalizar_texto(nombre_web)))
            if not nombre_db: continue

            sorteo = Sorteo.objects.filter(nombre__iexact=nombre_db).first()
            if not sorteo: continue
            if not sorteo_corre_hoy(sorteo, dia_actual, temporada): continue

            fecha = parse_date(item.get("fecha", ""))
            if not fecha or fecha > hoy_cuba: continue

            fuente = item.get("fuente", "")
            if fuente == "lotteryusa" and fecha not in (hoy_cuba, ayer_cuba): continue

            resultado_existente = Resultado.objects.filter(sorteo=sorteo, fecha=fecha).first()

            pick2_val = pick3_val = pick4_val = pick5_val = ''
            fijo_val = corrido1_val = corrido2_val = ''

            if fuente == "lotteryusa":
                pick2_val = item.get("pick2", "")
                pick3_val = item.get("pick3", "")
                pick4_val = item.get("pick4", "")
                pick5_val = item.get("pick5", "")

                if not pick3_val and item.get("numeros"):
                    raw_nums = [str(x).strip() for x in item.get("numeros")]
                    if len(raw_nums) >= 2: pick2_val = "".join(raw_nums[:2])
                    if len(raw_nums) >= 3: pick3_val = "".join(raw_nums[:3])
                    if len(raw_nums) >= 4: pick4_val = "".join(raw_nums[:4])
                    if len(raw_nums) >= 5: pick5_val = "".join(raw_nums[:5])

                # PRESERVAR Fijo y Corridos si ya existen
                if resultado_existente and resultado_existente.fijo:
                    fijo_val = resultado_existente.fijo
                    corrido1_val = resultado_existente.corrido_1
                    corrido2_val = resultado_existente.corrido_2
                elif pick3_val and len(pick3_val) == 3:
                    fijo_val = pick3_val[0].zfill(2)
                    corrido1_val = pick3_val[1].zfill(2)
                    corrido2_val = pick3_val[2].zfill(2)

            else:
                raw_nums = [str(x).strip() for x in item.get("numeros", [])]
                fijo_val = raw_nums[0].zfill(2) if len(raw_nums) > 0 else ''
                corrido1_val = raw_nums[1].zfill(2) if len(raw_nums) > 1 else ''
                corrido2_val = raw_nums[2].zfill(2) if len(raw_nums) > 2 else ''

                # PRESERVAR Picks si ya existen
                if resultado_existente:
                    pick2_val = resultado_existente.pick2 or ''
                    pick3_val = resultado_existente.pick3 or ''
                    pick4_val = resultado_existente.pick4 or ''
                    pick5_val = resultado_existente.pick5 or ''

            datos = {
                'sorteo': sorteo, 'fecha': fecha, 'hora': sorteo.hora_salida,
                'pick2': pick2_val, 'pick3': pick3_val, 'pick4': pick4_val, 'pick5': pick5_val,
                'fijo': fijo_val, 'corrido_1': corrido1_val, 'corrido_2': corrido2_val,
                'pf': '', 'centena_corrida_1': '', 'centena_corrida_2': '',
            }

            try:
                resultado_obj, premios_count = procesar_resultado(req, datos, resultado_existente=resultado_existente)
                resultado_obj.metadata = resultado_obj.metadata or {}
                resultado_obj.metadata['fuente'] = fuente
                resultado_obj.procesamiento_estado = 'completado'
                resultado_obj.save(update_fields=['metadata', 'procesamiento_estado'])

                if resultado_existente: actualizados += 1
                else: creados += 1
                premios_ok += 1

                if fuente == "lotteryusa":
                    self.stdout.write(self.style.SUCCESS(
                        f"✅ {nombre_db} [{fecha}] (usa) -> P3={pick3_val or '-'} P2={pick2_val or '-'} P4={pick4_val or '-'} P5={pick5_val or '-'} F={fijo_val or '-'} C1={corrido1_val or '-'} C2={corrido2_val or '-'} (premios: {premios_count})"
                    ))
                else:
                    self.stdout.write(self.style.SUCCESS(
                        f"✅ {nombre_db} [{fecha}] (enlo) -> F={fijo_val or '-'} C1={corrido1_val or '-'} C2={corrido2_val or '-'} (premios: {premios_count})"
                    ))

            except Exception as e:
                errores += 1
                self.stdout.write(self.style.ERROR(f"❌ Error procesando '{nombre_web}': {str(e)}"))

        self.stdout.write(self.style.SUCCESS(f"\nResumen Final -> Creados={creados}, Actualizados={actualizados}, Premios OK={premios_ok}, Errores={errores}"))

if __name__ == "__main__":
    pass