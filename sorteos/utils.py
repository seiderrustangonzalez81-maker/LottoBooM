from LottoBooM.utils import es_verano_cuba
# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
from django.utils import timezone
from .models import Sorteo


from datetime import timezone as _dt_tz

def _tz_cuba(fecha):
    """tzinfo con el offset correcto de Cuba según es_verano_cuba(fecha)."""
    from LottoBooM.utils import es_verano_cuba
    return _dt_tz(timedelta(hours=-4 if es_verano_cuba(fecha) else -5))

MAPA_DIAS = {
    'monday': 'lunes',
    'tuesday': 'martes',
    'wednesday': 'miercoles',
    'thursday': 'jueves',
    'friday': 'viernes',
    'saturday': 'sabado',
    'sunday': 'domingo',
}


def _ahora_local():
    """Ahora, aware, en hora Cuba (America/Havana)."""
    return timezone.localtime(timezone.now())


def _fecha_local(fecha=None):
    if fecha is None:
        return _ahora_local().date()
    return fecha


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
    dia_es = MAPA_DIAS.get(fecha.strftime('%A').lower())
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


def get_hora_salida(sorteo, fecha=None):
    """Hora de salida efectiva. Prioridad: hora_salida manual > horarios[día][temp] > None."""
    if sorteo.hora_salida:
        return sorteo.hora_salida
    return obtener_hora_desde_horarios(sorteo, fecha)


def get_hora_cierre(sorteo, fecha=None):
    """Momento de cierre (salida - minutos_cierre) como datetime aware Cuba, o None."""
    fecha = _fecha_local(fecha)
    hora_salida = get_hora_salida(sorteo, fecha)
    if not hora_salida:
        return None
    minutos = sorteo.minutos_cierre if sorteo.minutos_cierre is not None else 60
    salida_dt = datetime.combine(fecha, hora_salida).replace(tzinfo=_tz_cuba(fecha))
    return salida_dt - timedelta(minutes=minutos)


def calcular_estado_sorteo(sorteo, ahora=None, fecha_consulta=None):
    """
    Enriquece el sorteo con atributos calculados SIEMPRE en hora Cuba.

    Atributos que setea:
      - estado_actual: 'abierto' | 'cerrado' | 'salido' | 'no_programado'
      - segundos_restantes: segundos hacia el próximo evento
          · abierto → segundos hasta el CIERRE
          · cerrado → segundos hasta la SALIDA
          · salido / no_programado → 0
      - segundos_para_salida: segundos hasta la SALIDA (0 si ya salió)
      - hora_salida: time o None
      - hora_cierre: datetime aware o None
      - hora_salida_str: "01:35 PM" o "—"
    """
    if ahora is None:
        ahora = timezone.now()

    ahora_local = ahora.astimezone(_tz_cuba(fecha_consulta if fecha_consulta else ahora.date()))
    if fecha_consulta is None:
        fecha_consulta = ahora_local.date()

    # Determinar hora de salida para HOY (Cuba)
    if sorteo.horarios:
        hora_salida = obtener_hora_desde_horarios(sorteo, fecha_consulta)
    else:
        hora_salida = sorteo.hora_salida

    # Sorteo no programado para hoy
    if not hora_salida:
        sorteo.estado_actual = 'no_programado'
        sorteo.segundos_restantes = 0
        sorteo.segundos_para_salida = 0
        sorteo.hora_salida = None
        sorteo.hora_cierre = None
        sorteo.hora_salida_str = '—'
        return sorteo

    minutos_cierre = sorteo.minutos_cierre if sorteo.minutos_cierre is not None else 60

    dt_salida = datetime.combine(fecha_consulta, hora_salida).replace(tzinfo=_tz_cuba(fecha_consulta))
    dt_cierre = dt_salida - timedelta(minutes=minutos_cierre)

    # ── Estado ──
    if ahora_local < dt_cierre:
        estado = 'abierto'
        segundos = int((dt_cierre - ahora_local).total_seconds())
    elif ahora_local < dt_salida:
        estado = 'cerrado'
        segundos = int((dt_salida - ahora_local).total_seconds())
    else:
        estado = 'salido'
        segundos = 0

    segundos_para_salida = (
        int((dt_salida - ahora_local).total_seconds())
        if ahora_local < dt_salida else 0
    )

    sorteo.estado_actual = estado
    sorteo.segundos_restantes = max(0, segundos)
    sorteo.segundos_para_salida = max(0, segundos_para_salida)
    sorteo.hora_salida = hora_salida
    sorteo.hora_cierre = dt_cierre
    sorteo.hora_salida_str = hora_salida.strftime('%I:%M %p')

    # FIX_PROXIMO_EN_LISTA_V1: si ya salió, calcular segundos al próximo día
    sorteo.segundos_proximo = 0
    if estado == 'salido':
        try:
            sorteo.segundos_proximo = segundos_hasta_proximo(sorteo, ahora) or 0
        except Exception:
            sorteo.segundos_proximo = 0

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
    """
    Devuelve (dt_salida, es_hoy) del PRÓXIMO sorteo a partir de `ahora`.
    Busca desde hoy hasta +7 días. None si no hay programación en la semana.
    """
    if ahora is None:
        ahora = timezone.localtime(timezone.now())

    hoy = ahora.date()
    for offset in range(0, 8):
        fecha = hoy + timedelta(days=offset)
        hora = obtener_hora_desde_horarios(sorteo, fecha)
        if not hora:
            continue
        dt = timezone.make_aware(
            datetime.combine(fecha, hora),
            timezone.get_current_timezone(),
        )
        if dt > ahora:
            return dt, (offset == 0)
    return None, None


def segundos_hasta_proximo(sorteo, ahora=None):
    """Segundos hasta la próxima salida (aunque sea mañana o pasado)."""
    if ahora is None:
        ahora = timezone.localtime(timezone.now())
    dt, _ = get_proximo_datetime_sorteo(sorteo, ahora)
    if not dt:
        return None
    return int((dt - ahora).total_seconds())
