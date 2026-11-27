import requests
import unicodedata
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from LottoBooM.utils import es_verano_cuba
from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_date
from django.contrib.auth.models import User
from sorteos.models import Sorteo
from resultados.models import Resultado
from resultados.views import procesar_resultado
from sorteos.utils import get_hora_salida, get_datetime_salida_cuba

URL_JSON = "https://raw.githubusercontent.com/seiderrustangonzalez81-maker/LottoBooM/main/resultados.json"

MAPEO_NOMBRES = {
    "Anguila 8 AM": "Anguila 8 AM",
    "Anguila 9 AM": "Anguila 9 AM",
    "Haití 1": "Haití 1",
    "Anguila 10 AM": "Anguila 10 AM",
    "Tennessee 9:28 AM": "Tennessee 9:28 AM",
    "Haití 2": "Haití 2",
    "Anguila 11 AM": "Anguila 11 AM",
    "Texas 11 AM": "Texas 11 AM",
    "Haití 3": "Haití 3",
    "Lotedom": "Lotedom",
    "Quemaito": "Quemaito",
    "Anguila 12 PM": "Anguila 12 PM",
    "Primera": "Primera",
    "Quinielón": "Quinielón",
    "Suerte 12:30 PM": "Suerte 12:30 PM",
    "King Lottery 12:30 PM": "King Lottery 12:30 PM",
    "Georgia 12:30 PM": "Georgia 12:30 PM",
    "Real 12:55 PM": "Real 12:55 PM",
    "New Yol Real 12:50 PM": "New Yol Real 12:50 PM",
    "New Jersey 12:50 PM": "New Jersey 12:50 PM",
    "Anguila 1 PM": "Anguila 1 PM",
    "Tennessee 12:28 PM": "Tennessee 12:28 PM",
    "Texas 1:20 PM": "Texas 1:20 PM",
    "Florida 1:35 PM": "Florida 1:35 PM",
    "Anguila 2 PM": "Anguila 2 PM",
    "Gana Más 2:30 PM": "Gana Más 2:30 PM",
    "New York 2:30 PM": "New York 2:30 PM",
    "Anguila 3 PM": "Anguila 3 PM",
    "Anguila 4 PM": "Anguila 4 PM",
    "Anguila 5 PM": "Anguila 5 PM",
    "Haití 4": "Haití 4",
    "Suerte 6 PM": "Suerte 6 PM",
    "Anguila 6 PM": "Anguila 6 PM",
    "Haití 5": "Haití 5",
    "Anguila 7 PM": "Anguila 7 PM",
    "Primera 7 PM": "Primera 7 PM",
    "Georgia 7 PM": "Georgia 7 PM",
    "Texas 7 PM": "Texas 7 PM",
    "Tennessee 6:28 PM": "Tennessee 6:28 PM",
    "King Lottery 7:30 PM": "King Lottery 7:30 PM",
    "Haití 6": "Haití 6",
    "Loteka 7:55 PM": "Loteka 7:55 PM",
    "Tok 3": "Tok 3",
    "Anguila 8 PM": "Anguila 8 PM",
    "Nacional": "Nacional",
    "Leidsa 8:55 PM": "Leidsa 8:55 PM",
    "Pega 3+": "Pega 3+",
    "Anguila 9 PM": "Anguila 9 PM",
    "Florida 9:50 PM": "Florida 9:50 PM",
    "Anguila 10 PM": "Anguila 10 PM",
    "New York 10:30 PM": "New York 10:30 PM",
    "New Jersey 10:50 PM": "New Jersey 10:50 PM",
    "Texas 11 PM": "Texas 11 PM",
    "Georgia 11:40 PM": "Georgia 11:40 PM",
    "Real Noche": "Real Noche",
    "Loteka Tarde": "Loteka Tarde",
    "Lotedom Noche": "Lotedom Noche",
    "Quemaito Noche": "Quemaito Noche",
    "Quinielón Noche": "Quinielón Noche",
    "Haiti Bolet 9:30 AM": "Haití 1",
    "Haiti Bolet 10:30 AM": "Haití 2",
    "Haiti Bolet 11:30 AM": "Haití 3",
    "Haiti Bolet 5:30 PM": "Haití 4",
    "Haiti Bolet 6:30 PM": "Haití 5",
    "Haiti Bolet 7:30 PM": "Haití 6",
    "El Quemaito Mayor": "Quemaito",
    "El Quinielon Dia": "Quinielón",
    "La Primera": "Primera",
    "La Primera Noche": "Primera 7 PM",
    "La Suerte": "Suerte 12:30 PM",
    "La Suerte 6PM": "Suerte 6 PM",
    "LoteDom": "Lotedom",
    "King Lottery Día": "King Lottery 12:30 PM",
    "King Lottery Noche": "King Lottery 7:30 PM",
    "Real": "Real 12:55 PM",
    "Nacional Noche": "Nacional",
    "New York Noche": "New York 10:30 PM",
    "Nacional Gana Más": "Gana Más 2:30 PM",
    "Leidsa": "Leidsa 8:55 PM",
    "Loteka": "Loteka 7:55 PM",
    "LoteDom Noche": "Lotedom Noche",
    "El Quemaito Mayor Noche": "Quemaito Noche",
    "El Quinielon Noche": "Quinielón Noche",
    "Tennessee 10:20 AM": "Tennessee 9:28 AM",
    "Tennessee 1:20 PM": "Tennessee 12:28 PM",
    "Tennessee 6:30 PM": "Tennessee 6:28 PM",
    "Tennessee 7:20 PM": "Tennessee 6:28 PM",
    "Tennessee 10:28 AM": "Tennessee 9:28 AM",
    "Tennessee 1:28 PM": "Tennessee 12:28 PM",
    "Tennessee 7:28 PM": "Tennessee 6:28 PM",
    "Texas 10:12 PM": "Texas 11 PM",
    "Florida 9:45 PM": "Florida 9:50 PM",
    "New Jersey 10:57 PM": "New Jersey 10:50 PM",
    "Georgia 6:59 PM": "Georgia 7 PM",
    "Georgia 11:34 PM": "Georgia 11:40 PM",
    "Loteka 1:30 PM": "Loteka Tarde",
    "Loteka 7:50 PM": "Loteka 7:55 PM"
}

def obtener_hora_cuba_actual():
    """Usa la regla operativa vigente de Cuba, sin depender de tzdata desactualizada."""
    ahora_utc = datetime.now(timezone.utc)
    offset = -4 if es_verano_cuba(ahora_utc) else -5
    return ahora_utc.astimezone(timezone(timedelta(hours=offset)))
TZ_ESTE = ZoneInfo('America/New_York')
DIAS_ES = {0: 'lunes', 1: 'martes', 2: 'miercoles', 3: 'jueves', 4: 'viernes', 5: 'sabado', 6: 'domingo'}

def normalizar_texto(texto):
    if not texto: return ""
    texto = unicodedata.normalize('NFD', str(texto))
    texto = ''.join(c for c in texto if unicodedata.category(c) != 'Mn')
    return texto.lower().strip()

def temporada_actual(fecha=None):
    """Temporada de Cuba para la fecha operativa consultada."""
    if fecha is None:
        fecha = (obtener_hora_cuba_actual() - timedelta(hours=1)).date()
    return 'verano' if es_verano_cuba(fecha) else 'invierno'


def sorteo_corre_hoy(sorteo, dia_actual, temporada, fecha_operativa=None):
    """Comprueba el calendario real; USA se evalúa en su zona de origen."""
    if fecha_operativa is not None:
        return get_datetime_salida_cuba(sorteo, fecha_operativa) is not None
    horarios = getattr(sorteo, 'horarios', None)
    if not isinstance(horarios, dict) or not horarios:
        return False
    bloque = horarios.get(temporada)
    if not isinstance(bloque, dict):
        return False
    valor = bloque.get(dia_actual)
    return bool(valor and str(valor).strip())

def calcular_derivados(pick2, pick3, pick4, fijo, c1, c2):
    """Replica la lógica del frontend crear_resultado.html"""
    pf = ""
    if pick3 and len(pick3) >= 2:
        pf = pick3[:2].zfill(2)
    elif pick2 and len(pick2) >= 2:
        pf = pick2.zfill(2)

    centena1 = ""
    centena2 = ""
    if pick3 and len(pick3) == 3 and c1 and len(c1) == 2:
        centena1 = pick3[2] + c1
    if pick3 and len(pick3) == 3 and c2 and len(c2) == 2:
        d1 = int(pick3[0])
        d3 = int(pick3[2])
        centena2 = str((d1 + d3) % 10) + c2

    fijos_list = [f for f in [fijo, c1, c2] if f and len(f) == 2]

    parlets = set()
    for i in range(len(fijos_list)):
        for j in range(i+1, len(fijos_list)):
            if fijos_list[i] != fijos_list[j]:
                parlets.add(fijos_list[i] + 'x' + fijos_list[j])
                parlets.add(fijos_list[j] + 'x' + fijos_list[i])
    parlet_str = "  ".join(sorted(parlets))

    posicion = ""
    tripleta = ""
    if fijo and c1 and c2:
        posicion = f"{fijo} {c1} {c2}"
        tripleta = posicion

    vspf_arr = []
    if pf:
        for n in fijos_list:
            if n != pf:
                vspf_arr.append(pf + 'x' + n)
    vspf_str = "  ".join(sorted(vspf_arr))

    vspick2_arr = []
    if pick2 and len(pick2) == 2:
        for n in fijos_list:
            if n != pick2:
                vspick2_arr.append(pick2 + 'x' + n)
    vspick2_str = "  ".join(sorted(vspick2_arr))

    pick2vspf_str = ""
    if pick2 and len(pick2) == 2 and pf and pick2 != pf:
        pick2vspf_str = pf + 'x' + pick2

    return {
        'pf': pf,
        'centena_corrida_1': centena1,
        'centena_corrida_2': centena2,
        'parlet': parlet_str,
        'posicion': posicion,
        'tripleta': tripleta,
        'vspf': vspf_str,
        'vspick2': vspick2_str,
        'pick2vspf': pick2vspf_str
    }

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
        if not admin:
            self.stdout.write(self.style.ERROR("No hay superusuario. Abortando."))
            return
        req = FakeRequest(admin)

        mapeo_normalizado = {normalizar_texto(k): v for k, v in MAPEO_NOMBRES.items()}
        ahora_cuba = obtener_hora_cuba_actual()
        hoy_cuba = ahora_cuba.date()
        dia_operativo = (ahora_cuba - timedelta(hours=1)).date()
        ayer_cuba = dia_operativo - timedelta(days=1)
        dia_actual = DIAS_ES[dia_operativo.weekday()]
        temporada = temporada_actual(dia_operativo)

        self.stdout.write(f"Día actual: {dia_actual} | Temporada: {temporada}")
        self.stdout.write(f"Fecha/hora Cuba: {ahora_cuba.isoformat()} | Día operativo: {dia_operativo} (01:00–00:59)")

        creados = actualizados = errores = premios_ok = 0
        nombres_sin_mapeo = set()
        destinos_sin_sorteo = set()

        # PRIMERA PASADA: identificar qué sorteos tienen datos de enloteria en este JSON
        sorteos_con_enloteria = set()
        for item in data:
            if item.get("fuente") == "enloteria":
                nombre_web = item.get("sorteo_nombre", "").strip()
                nombre_db = (MAPEO_NOMBRES.get(nombre_web) or mapeo_normalizado.get(normalizar_texto(nombre_web)))
                if nombre_db:
                    sorteos_con_enloteria.add(nombre_db)
                else:
                    nombres_sin_mapeo.add(nombre_web)

        # SEGUNDA PASADA: procesar
        for item in data:
            nombre_web = item.get("sorteo_nombre", "").strip()
            if not nombre_web:
                continue

            nombre_db = (MAPEO_NOMBRES.get(nombre_web) or mapeo_normalizado.get(normalizar_texto(nombre_web)))
            if not nombre_db:
                nombres_sin_mapeo.add(nombre_web)
                continue

            sorteo = Sorteo.objects.filter(nombre__iexact=nombre_db).first()
            if not sorteo:
                destinos_sin_sorteo.add((nombre_web, nombre_db))
                continue
            if not sorteo_corre_hoy(sorteo, dia_actual, temporada, dia_operativo):
                continue

            fecha = parse_date(item.get("fecha", ""))
            if not fecha or fecha != dia_operativo:
                self.stdout.write(self.style.WARNING(
                    f"⏭️ Descartado {nombre_web} [{fecha}] (fuera del día operativo {dia_operativo})"
                ))
                continue

            fuente = item.get("fuente", "")

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

                if pick3_val and len(pick3_val) >= 3:
                    fijo_val = pick3_val[-2:].zfill(2)
                    corrido1_val = pick3_val[:2].zfill(2)
                    corrido2_val = (pick3_val[0] + pick3_val[2]).zfill(2)

                if nombre_db in sorteos_con_enloteria:
                    if resultado_existente and resultado_existente.fijo:
                        fijo_val = resultado_existente.fijo
                        corrido1_val = resultado_existente.corrido_1
                        corrido2_val = resultado_existente.corrido_2

            else:  # enloteria
                raw_nums = [str(x).strip() for x in item.get("numeros", [])]
                fijo_val = raw_nums[0].zfill(2) if len(raw_nums) > 0 else ''
                corrido1_val = raw_nums[1].zfill(2) if len(raw_nums) > 1 else ''
                corrido2_val = raw_nums[2].zfill(2) if len(raw_nums) > 2 else ''

                if resultado_existente:
                    pick2_val = resultado_existente.pick2 or ''
                    pick3_val = resultado_existente.pick3 or ''
                    pick4_val = resultado_existente.pick4 or ''
                    pick5_val = resultado_existente.pick5 or ''

            derivados = calcular_derivados(pick2_val, pick3_val, pick4_val, fijo_val, corrido1_val, corrido2_val)

            datos = {
                'sorteo': sorteo, 'fecha': fecha, 'hora': get_hora_salida(sorteo, fecha),
                'pick2': pick2_val, 'pick3': pick3_val, 'pick4': pick4_val, 'pick5': pick5_val,
                'fijo': fijo_val, 'corrido_1': corrido1_val, 'corrido_2': corrido2_val,
                'pf': derivados['pf'],
                'centena_corrida_1': derivados['centena_corrida_1'],
                'centena_corrida_2': derivados['centena_corrida_2'],
                'parlet': derivados['parlet'],
                'posicion': derivados['posicion'],
                'tripleta': derivados['tripleta'],
                'vspf': derivados['vspf'],
                'vspick2': derivados['vspick2'],
                'pick2vspf': derivados['pick2vspf'],
            }

            try:
                resultado_obj, premios_count = procesar_resultado(req, datos, resultado_existente=resultado_existente)
                resultado_obj.metadata = resultado_obj.metadata or {}
                resultado_obj.metadata['fuente'] = fuente
                resultado_obj.procesamiento_estado = 'completado'
                resultado_obj.save(update_fields=['metadata', 'procesamiento_estado'])

                if resultado_existente:
                    actualizados += 1
                else:
                    creados += 1
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

        if nombres_sin_mapeo:
            self.stdout.write(self.style.WARNING(
                "Nombres de fuente sin equivalencia: " + ", ".join(sorted(nombres_sin_mapeo))
            ))
        if destinos_sin_sorteo:
            detalle = ", ".join(f"{origen} -> {destino}" for origen, destino in sorted(destinos_sin_sorteo))
            self.stdout.write(self.style.WARNING("Destinos inexistentes en Sorteo: " + detalle))

        self.stdout.write(self.style.SUCCESS(
            f"\nResumen Final -> Creados={creados}, Actualizados={actualizados}, Premios OK={premios_ok}, Errores={errores}, Sin mapeo={len(nombres_sin_mapeo)}, Sin destino={len(destinos_sin_sorteo)}"
        ))

if __name__ == "__main__":
    pass