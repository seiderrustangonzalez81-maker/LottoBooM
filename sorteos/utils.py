# -*- coding: utf-8 -*-
from datetime import datetime, timedelta, time, timezone as dt_timezone
from zoneinfo import ZoneInfo
from django.utils import timezone
from LottoBooM.utils import es_verano_cuba
from .models import Sorteo


def _tz_cuba(fecha=None):
    """Offset civil de Cuba; acepta instante aware o fecha/hora local programada."""
    if fecha is None:
        fecha = timezone.now()
    return dt_timezone(timedelta(hours=-4 if es_verano_cuba(fecha) else -5))

MAPA_DIAS = {
    'monday': 'lunes',
    'tuesday': 'martes',
    'wednesday': 'miercoles',
    'thursday': 'jueves',
    'friday': 'viernes',
    'saturday': 'sabado',
    'sunday': 'domingo',
}

DIAS_SEMANA_ES = (
    'lunes', 'martes', 'miercoles', 'jueves', 'viernes', 'sabado', 'domingo',
)


def _ahora_local():
    """Ahora, aware, en hora Cuba (America/Havana)."""
    ahora_utc = timezone.now()
    return ahora_utc.astimezone(_tz_cuba(ahora_utc))


def _fecha_local(fecha=None):
    """Fecha operativa Cuba: 01:00–00:59 del día siguiente."""
    if fecha is not None:
        return fecha.date() if isinstance(fecha, datetime) else fecha
    ahora = _ahora_local()
    return (ahora - timedelta(hours=1)).date()


def _temporada(fecha):
    """Verano: abril–octubre. Invierno: noviembre–marzo."""
    return 'verano' if es_verano_cuba(fecha) else 'invierno'


def obtener_hora_desde_horarios(sorteo, fecha=None):
    """
    Hora de salida para el día/temporada de `fecha` (hora Cuba).
    Sin fallback: si el día no está en la temporada actual → None.
    """
    if not sorteo.horarios:
        return None

    fecha = _fecha_local(fecha)
    dia_es = DIAS_SEMANA_ES[fecha.weekday()]
    if not dia_es:
        return None

    temp = _temporada(fecha)
    if temp not in sorteo.horarios:
        return None

    hora_str = (sorteo.horarios.get(temp) or {}).get(dia_es)
    if not hora_str:
        return None

    try:
        return datetime.strptime(hora_str, '%H:%M').time()
    except (ValueError, TypeError):
        return None


# Los horarios estadounidenses están guardados en hora local del estado.
# Los sorteos dominicanos/haitianos ya están normalizados a hora Cuba en la matriz.
ZONAS_SORTEOS_USA = {
    "new york": "America/New_York",
    "new jersey": "America/New_York",
    "new yol real": "America/New_York",
    "florida": "America/New_York",
    "georgia": "America/New_York",
    "texas": "America/Chicago",
    "tennessee": "America/Chicago",
}


def _zona_fuente_sorteo(sorteo):
    # El nombre del sorteo identifica su estado incluso en bases antiguas
    # donde el campo origen todavía no estaba poblado.
    nombre = str(getattr(sorteo, "nombre", "") or "").casefold()
    for prefijo, zona in ZONAS_SORTEOS_USA.items():
        if nombre.startswith(prefijo):
            return ZoneInfo(zona)
    return None


def _fecha_operativa_cuba(instante):
    local = instante.astimezone(_tz_cuba(instante))
    return (local - timedelta(hours=1)).date()


def _convertir_fuente_a_cuba(instante_fuente):
    instante_utc = instante_fuente.astimezone(dt_timezone.utc)
    return instante_utc.astimezone(_tz_cuba(instante_utc))


def get_datetime_salida_cuba(sorteo, fecha=None):
    """Devuelve la salida como datetime aware en hora Cuba."""
    fecha = _fecha_local(fecha)
    zona_fuente = _zona_fuente_sorteo(sorteo)

    if zona_fuente:
        # Un sorteo estadounidense puede caer en el día calendario siguiente de Cuba.
        for fecha_fuente in (
            fecha,
            fecha - timedelta(days=1),
            fecha + timedelta(days=1),
        ):
            hora = obtener_hora_desde_horarios(sorteo, fecha_fuente)
            if not hora:
                continue
            dt_fuente = datetime.combine(fecha_fuente, hora).replace(tzinfo=zona_fuente)
            dt_cuba = _convertir_fuente_a_cuba(dt_fuente)
            if _fecha_operativa_cuba(dt_cuba) == fecha:
                return dt_cuba
        return None

    hora = obtener_hora_desde_horarios(sorteo, fecha)
    if not hora:
        return None
    salida_naive = datetime.combine(fecha, hora)
    return salida_naive.replace(tzinfo=_tz_cuba(salida_naive))


def get_hora_salida(sorteo, fecha=None):
    """Hora de salida convertida a Cuba para guardar y mostrar el resultado."""
    dt_salida = get_datetime_salida_cuba(sorteo, fecha)
    return dt_salida.timetz().replace(tzinfo=None) if dt_salida else None


def get_hora_cierre(sorteo, fecha=None):
    """Cierre exacto: salida real menos los minutos configurados."""
    dt_salida = get_datetime_salida_cuba(sorteo, fecha)
    if not dt_salida:
        return None
    # Política única del sistema: cerrar exactamente 10 minutos antes.
    return dt_salida - timedelta(minutes=10)


def calcular_estado_sorteo(sorteo, ahora=None, fecha_consulta=None):
    """Calcula el estado usando la próxima salida real en hora Cuba."""
    if ahora is None:
        ahora = timezone.now()
    ahora_local = ahora.astimezone(_tz_cuba(ahora))

    if fecha_consulta is None:
        dt_salida, _ = get_proximo_datetime_sorteo(sorteo, ahora_local)
        if not dt_salida:
            sorteo.estado_actual = "no_programado"
            sorteo.hora_salida_str = "No programado"
            sorteo.hora_salida = None
            sorteo.hora_cierre = None
            sorteo.hora_cierre_datetime = None
            sorteo.proximo_datetime = None
            sorteo.hora_cierre_str = "—"
            sorteo.segundos_proximo = None
            sorteo.segundos_restantes = None
            return sorteo
        fecha_consulta = _fecha_operativa_cuba(dt_salida)
    else:
        fecha_consulta = _fecha_local(fecha_consulta)
        dt_salida = get_datetime_salida_cuba(sorteo, fecha_consulta)

    if not dt_salida:
        sorteo.estado_actual = "no_programado"
        sorteo.hora_salida_str = "No programado"
        sorteo.hora_salida = None
        sorteo.hora_cierre = None
        sorteo.hora_cierre_datetime = None
        sorteo.proximo_datetime = None
        sorteo.hora_cierre_str = "—"
        sorteo.segundos_proximo = None
        sorteo.segundos_restantes = None
        return sorteo

    # Política única: ningún registro antiguo puede reducir el margen a 5 minutos.
    dt_cierre = dt_salida - timedelta(minutes=10)
    sorteo.proximo_datetime = dt_salida
    sorteo.hora_cierre_datetime = dt_cierre
    sorteo.hora_cierre = dt_cierre
    sorteo.fecha_operativa_salida = _fecha_operativa_cuba(dt_salida)

    sorteo.hora_salida = dt_salida.timetz().replace(tzinfo=None)
    sorteo.hora_salida_str = dt_salida.strftime("%I:%M %p").lstrip("0")
    sorteo.hora_cierre_str = dt_cierre.strftime("%I:%M %p").lstrip("0")

    if ahora_local < dt_cierre:
        sorteo.estado_actual = "abierto"
        sorteo.segundos_proximo = max(0, int((dt_cierre - ahora_local).total_seconds()))
        sorteo.segundos_restantes = sorteo.segundos_proximo
    elif ahora_local < dt_salida:
        sorteo.estado_actual = "cerrado"
        sorteo.segundos_proximo = max(0, int((dt_salida - ahora_local).total_seconds()))
        sorteo.segundos_restantes = sorteo.segundos_proximo
    else:
        sorteo.estado_actual = "salido"
        sorteo.segundos_proximo = segundos_hasta_proximo(sorteo, ahora_local)
        sorteo.segundos_restantes = sorteo.segundos_proximo

    return sorteo


def get_sorteos_hoy(fecha=None):
    """
    Devuelve (sorteos_ordenados, totales) para la fecha dada (Cuba).
    Excluye 'no_programado'.
    Orden: abiertos → cerrados → salidos.
    """
    if fecha is None:
        fecha = _fecha_local()

    ahora = timezone.now()
    abiertos, cerrados, salidos = [], [], []

    for s in Sorteo.objects.filter(activo=True):
        s = calcular_estado_sorteo(s, ahora, fecha)
        if s.estado_actual == 'abierto':
            abiertos.append(s)
        elif s.estado_actual == 'cerrado':
            cerrados.append(s)
        elif s.estado_actual == 'salido':
            salidos.append(s)

    abiertos.sort(key=lambda x: x.segundos_restantes)
    cerrados.sort(key=lambda x: x.segundos_restantes)
    salidos.sort(key=lambda x: x.hora_salida or datetime.min.time())

    ordenados = abiertos + cerrados + salidos
    totales = {
        'total': len(ordenados),
        'abiertos': len(abiertos),
        'cerrados': len(cerrados),
        'salidos': len(salidos),
    }
    return ordenados, totales


# ── Compatibilidad con código existente ──
def get_sorteos_abiertos(fecha=None):
    if fecha is None:
        fecha = _fecha_local()
    ahora = timezone.now()
    resultado = []
    for s in Sorteo.objects.filter(activo=True):
        s = calcular_estado_sorteo(s, ahora, fecha)
        if s.estado_actual == 'abierto':
            resultado.append(s)
    return resultado


def get_sorteos_del_dia(fecha=None):
    if fecha is None:
        fecha = _fecha_local()
    ahora = timezone.now()
    resultado = []
    for s in Sorteo.objects.filter(activo=True):
        s = calcular_estado_sorteo(s, ahora, fecha)
        if s.estado_actual != 'no_programado':
            resultado.append(s)
    return resultado

# ═══════════════════════════════════════════════════════════════
# FIX_PROXIMO_DIA_V1 — Countdown extendido al próximo día
# ═══════════════════════════════════════════════════════════════
def get_proximo_datetime_sorteo(sorteo, ahora=None):
    """Busca la próxima salida real en Cuba, incluso si cruza la medianoche."""
    if ahora is None:
        ahora = _ahora_local()
    ahora_local = ahora.astimezone(_tz_cuba(ahora))
    zona_fuente = _zona_fuente_sorteo(sorteo)
    candidatos = []

    if zona_fuente:
        ahora_fuente = ahora_local.astimezone(zona_fuente)
        fechas_fuente = [
            ahora_fuente.date() + timedelta(days=i)
            for i in (-1, 0, 1, 2)
        ]
        for fecha_fuente in fechas_fuente:
            hora = obtener_hora_desde_horarios(sorteo, fecha_fuente)
            if not hora:
                continue
            dt_fuente = datetime.combine(fecha_fuente, hora).replace(tzinfo=zona_fuente)
            dt_cuba = _convertir_fuente_a_cuba(dt_fuente)
            if dt_cuba > ahora_local:
                candidatos.append(dt_cuba)
    else:
        for offset in range(0, 8):
            fecha = ahora_local.date() + timedelta(days=offset)
            hora = obtener_hora_desde_horarios(sorteo, fecha)
            if not hora:
                continue
            dt_cuba = datetime.combine(fecha, hora).replace(tzinfo=_tz_cuba(fecha))
            if dt_cuba > ahora_local:
                candidatos.append(dt_cuba)

    if not candidatos:
        return None, False
    proximo = min(candidatos)
    es_hoy = _fecha_operativa_cuba(proximo) == _fecha_operativa_cuba(ahora_local)
    return proximo, es_hoy


def segundos_hasta_proximo(sorteo, ahora=None):
    """Segundos hasta la próxima salida (aunque sea mañana o pasado)."""
    if ahora is None:
        ahora = _ahora_local()
    dt, _ = get_proximo_datetime_sorteo(sorteo, ahora)
    if not dt:
        return None
    return int((dt - ahora).total_seconds())
