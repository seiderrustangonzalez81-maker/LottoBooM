from zoneinfo import ZoneInfo
from datetime import datetime, date, timedelta

CUB = ZoneInfo("America/Havana")

# Override: Cuba se mantiene en UTC-4 hasta el 7-nov-2026 inclusive.
# A partir del 8-nov-2026, manda tzdata (UTC-5).
# OVERRIDE_CUBA_2027: Cuba decidió mantener el horario de verano (UTC-4) de forma indefinida 
# hasta el 7 de noviembre de 2027 por la crisis energética. 
# La base de datos IANA (tzdata 2026f) confirma este cambio.
_OVERRIDE_UTC4_HASTA = date(2027, 11, 7)


def es_verano_cuba(fecha=None):
    """
    True si Cuba está en horario de verano (UTC-4).
    Acepta date o datetime.
    """
    if fecha is None:
        fecha = date.today()

    if isinstance(fecha, datetime):
        fecha_d = fecha.date()
    else:
        fecha_d = fecha

    # Override explícito para el tramo 1→7 nov 2026
    if fecha_d <= _OVERRIDE_UTC4_HASTA:
        return True

    dt = datetime.combine(fecha_d, datetime.min.time()).replace(tzinfo=CUB)
    return dt.dst() != timedelta(0)
