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
    # ─── ANGUILA Y HAITI ───
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

    # ─── DOMINICANAS ───
    "Nacional Gana Más": "Nacional Gana Más", "Nacional Noche": "Nacional Noche",
    "Leidsa": "Leidsa 8:55 PM",
    "Loteka Tarde": "Loteka 1:30 PM", "Loteka": "Loteka 7:55 PM",
    "La Primera": "La Primera", "La Primera Noche": "La Primera Noche",
    "La Suerte": "La Suerte", "La Suerte 6PM": "La Suerte 6PM",
    "LoteDom": "Lotedom", "LoteDom Noche": "Lotedom Noche",
    "King Lottery Día": "King Lottery 12:30 PM", "King Lottery Noche": "King Lottery 7:30 PM",

    # ─── VENEZOLANAS/OTRAS ───
    "El Quemaito Mayor": "El Quemaito Mayor", "El Quemaito Mayor Noche": "El Quemaito Mayor Noche",
    "El Quinielón Día": "El Quinielón Día", "El Quinielón Noche": "El Quinielón Noche",
    "Real": "Real", "Real Noche": "Real Noche",

    # ─── USA (SOLO desde LotteryUSA - fuente oficial) ───
    "Texas 1:20 PM": "Texas 1:20 PM",
    "Texas 10:12 PM": "Texas 11 PM",
    "Florida 9:45 PM": "Florida 9:50 PM",
    "New Jersey 10:57 PM": "New Jersey 10:50 PM",
    "Tennessee 6:30 PM": "Tennessee 7:20 PM",
    "Florida 1:35 PM": "Florida 1:35 PM",
    "New York 2:30 PM": "New York 2:30 PM",
    "New York 10:30 PM": "New York 10:30 PM",
    "New Jersey 12:50 PM": "New Jersey 12:50 PM",
    "Georgia 12:30 PM": "Georgia 12:30 PM",
    "Georgia 11:34 PM": "Georgia 11:34 PM",
    "Tennessee 1:20 PM": "Tennessee 1:20 PM",
    # NOTA: los nombres de enloteria para USA (Georgia Día, New York Tarde, etc.)
    # se dejan FUERA a propósito, para no contaminar con datos no oficiales.
}

TZ_CUBA = ZoneInfo('America/Havana')

def normalizar_texto(texto):
    if not texto: return ""
    texto = unicodedata.normalize('NFD', str(texto))
    texto = ''.join(c for c in texto if unicodedata.category(c) != 'Mn')
    return texto.lower().strip()

class FakeRequest:
    def __init__(self, user): self.user = user

class Command(BaseCommand):
    help = "Carga resultados desde EnLoteria y LotteryUSA, calculando premios automáticamente."

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

        mapeo_normalizado = {normalizar_texto(k): v for k, v in MAPEO_NOMBRES.items()}

        ahora_cuba = datetime.now(TZ_CUBA)
        hoy_cuba = ahora_cuba.date()
        ayer_cuba = hoy_cuba - timedelta(days=1)

        creados = actualizados = errores = premios_ok = 0
        sin_mapeo = set()
        sin_sorteo_db = set()

        for item in data:
            nombre_web = ""
            try:
                nombre_web = item.get("sorteo_nombre", "").strip()
                if not nombre_web:
                    continue

                nombre_db = (MAPEO_NOMBRES.get(nombre_web)
                             or mapeo_normalizado.get(normalizar_texto(nombre_web)))
                if not nombre_db:
                    sin_mapeo.add(nombre_web)
                    continue

                sorteo = Sorteo.objects.filter(nombre__iexact=nombre_db).first()
                if not sorteo:
                    sin_sorteo_db.add(nombre_db)
                    continue

                fecha = parse_date(item.get("fecha", ""))
                if not fecha:
                    self.stdout.write(self.style.WARNING(
                        f"⚠️ Fecha inválida en '{nombre_web}': {item.get('fecha')!r}"))
                    continue

                # ─── BLOQUEO ESTRICTO DE FECHAS FUTURAS ───
                if fecha > hoy_cuba:
                    self.stdout.write(self.style.WARNING(
                        f"⚠️ Saltando {nombre_db}: fecha futura ({fecha})."))
                    continue

                numeros = item.get("numeros", [])
                if not numeros or len(numeros) < 2:
                    continue

                fuente = item.get("fuente", "")

                # ─── VALIDACIÓN DE FECHA PARA LOTTERYUSA ───
                # Cuba (UTC-4) va 1 hora por delante del Este EE.UU. (UTC-5).
                # Los sorteos de noche (10:00 PM - 11:34 PM EST) se publican
                # cuando en Cuba ya es el día siguiente. Por eso se acepta
                # tanto hoy_cuba como ayer_cuba.
                if fuente == "lotteryusa" and fecha not in (hoy_cuba, ayer_cuba):
                    self.stdout.write(self.style.WARNING(
                        f"⚠️ Saltando {nombre_db}: fecha {fecha} fuera de ventana "
                        f"({ayer_cuba}..{hoy_cuba})."))
                    continue

                # ─── INICIALIZAR VARIABLES ───
                formas = [str(f).lower().strip() for f in (sorteo.formas_juego or [])]
                pick2_val = pick3_val = pick4_val = pick5_val = ''
                fijo_val = corrido1_val = corrido2_val = ''

                if fuente == "lotteryusa":
                    # LotteryUSA: 3 bolas individuales → llenar todas las formas disponibles
                    if len(numeros) >= 2:
                        if 'pick2' in formas:
                            pick2_val = "".join(numeros[:2])
                        if 'fijo' in formas:
                            fijo_val = numeros[0]
                        if 'corridos' in formas and len(numeros) >= 3:
                            corrido1_val = numeros[1]
                            corrido2_val = numeros[2]
                    if 'pick3' in formas and len(numeros) >= 3:
                        pick3_val = "".join(numeros[:3])
                    elif 'pick4' in formas and len(numeros) >= 4:
                        pick4_val = "".join(numeros[:4])
                else:
                    # Enloteria: solo fijo y corridos (3 números separados)
                    fijo_val = numeros[0] if len(numeros) > 0 else ''
                    corrido1_val = numeros[1] if len(numeros) > 1 else ''
                    corrido2_val = numeros[2] if len(numeros) > 2 else ''

                resultado_existente = Resultado.objects.filter(sorteo=sorteo, fecha=fecha).first()

                datos = {
                    'sorteo': sorteo, 'fecha': fecha, 'hora': sorteo.hora_salida,
                    'pick2': pick2_val, 'pick3': pick3_val,
                    'pick4': pick4_val, 'pick5': pick5_val,
                    'fijo': fijo_val,
                    'corrido_1': corrido1_val, 'corrido_2': corrido2_val,
                    'pf': '', 'centena_corrida_1': '', 'centena_corrida_2': '',
                }

                resultado_obj, premios_count = procesar_resultado(
                    req, datos, resultado_existente=resultado_existente)

                resultado_obj.metadata = resultado_obj.metadata or {}
                resultado_obj.metadata['fuente'] = fuente
                resultado_obj.procesamiento_estado = 'completado'
                resultado_obj.save(update_fields=['metadata', 'procesamiento_estado'])

                if resultado_existente:
                    actualizados += 1
                else:
                    creados += 1
                premios_ok += 1
                self.stdout.write(self.style.SUCCESS(
                    f"✅ {nombre_db} [{fecha}] -> P3={pick3_val or '-'} P2={pick2_val or '-'} "
                    f"F={fijo_val or '-'} C1={corrido1_val or '-'} C2={corrido2_val or '-'} "
                    f"(premios: {premios_count})"
                ))

            except Exception as e:
                errores += 1
                self.stdout.write(self.style.ERROR(
                    f"❌ Error procesando '{nombre_web}': {str(e)}"))

        # ─── RESUMEN FINAL ───
        self.stdout.write(self.style.SUCCESS(
            f"\nResumen Final -> Creados={creados}, Actualizados={actualizados}, "
            f"Premios OK={premios_ok}, Errores={errores}"
        ))
        if sin_mapeo:
            self.stdout.write(self.style.WARNING(
                f"\n⚠️ Nombres del JSON SIN MAPEO (revisa MAPEO_NOMBRES):"))
            for n in sorted(sin_mapeo):
                self.stdout.write(self.style.WARNING(f"   - {n}"))
        if sin_sorteo_db:
            self.stdout.write(self.style.WARNING(
                f"\n⚠️ Sorteos mapeados pero NO EXISTEN en BD (créalos):"))
            for n in sorted(sin_sorteo_db):
                self.stdout.write(self.style.WARNING(f"   - {n}"))