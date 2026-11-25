from zoneinfo import ZoneInfo
from datetime import datetime, date, time as dt_time, timedelta, timezone as dt_timezone

CUB = ZoneInfo("America/Havana")

# Cuba mantuvo UTC-4 al cancelar el cambio del 01-nov-2026.
# IANA tzdata 2026f fija el regreso a UTC-5 el 07-nov-2027 a las 05:00 UTC.
# El intervalo es semiabierto y se compara por instante, no por fecha del servidor.
CUBA_UTC4_START_UTC = datetime(2026, 11, 1, 5, 0, tzinfo=dt_timezone.utc)
CUBA_UTC4_END_UTC = datetime(2027, 11, 7, 5, 0, tzinfo=dt_timezone.utc)
_OVERRIDE_UTC4_DESDE = CUBA_UTC4_START_UTC.date()
_OVERRIDE_UTC4_HASTA = CUBA_UTC4_END_UTC.date()


def es_verano_cuba(fecha=None):
    """
    True si el instante/horario local de Cuba usa UTC-4.

    - datetime aware: compara el instante UTC con los límites oficiales.
    - datetime naive: se interpreta como hora civil de Cuba; en el día del
      cambio, 00:00–00:59 corresponde a la primera hora UTC-4.
    - date: usa el estado de mediodía para seleccionar el calendario del día.
      Así, el 07-nov-2027 se considera invierno, después del cambio de las 01:00.
    """
    if fecha is None:
        fecha = datetime.now(dt_timezone.utc)

    if isinstance(fecha, datetime):
        if fecha.tzinfo is not None:
            instante_utc = fecha.astimezone(dt_timezone.utc)
            if CUBA_UTC4_START_UTC <= instante_utc < CUBA_UTC4_END_UTC:
                return True
            return instante_utc.astimezone(CUB).dst() != timedelta(0)

        fecha_d = fecha.date()
        if _OVERRIDE_UTC4_DESDE <= fecha_d < _OVERRIDE_UTC4_HASTA:
            return True
        if fecha_d == _OVERRIDE_UTC4_HASTA and fecha.time() < dt_time(1, 0):
            return True
        return fecha.replace(tzinfo=CUB).dst() != timedelta(0)

    if isinstance(fecha, date):
        if _OVERRIDE_UTC4_DESDE <= fecha < _OVERRIDE_UTC4_HASTA:
            return True
        mediodia_local = datetime.combine(fecha, dt_time(12)).replace(tzinfo=CUB)
        return mediodia_local.dst() != timedelta(0)

    raise TypeError("es_verano_cuba espera date, datetime o None")
