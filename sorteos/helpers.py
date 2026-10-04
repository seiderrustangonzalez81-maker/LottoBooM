# sorteos/helpers.py
from django.utils import timezone

def get_hora_cierre(sorteo, fecha=None):
    """
    Calcula la hora de cierre de apuestas para un sorteo en una fecha dada.
    Si no se proporciona fecha, usa la fecha actual.
    """
    from .models import Sorteo  # importación perezosa para evitar circular

    if fecha is None:
        fecha = timezone.now().date()

    # Obtener horarios del sorteo
    horarios = sorteo.horarios if hasattr(sorteo, 'horarios') else {}

    # Determinar día de la semana (0=lunes, 6=domingo) - ajusta según tu lógica
    dia_semana = fecha.weekday()
    dias_map = ['lunes', 'martes', 'miercoles', 'jueves', 'viernes', 'sabado', 'domingo']
    dia_nombre = dias_map[dia_semana]

    # Buscar horario para este día
    horario_dia = horarios.get(dia_nombre)

    if horario_dia:
        # Si el horario es un string, convertirlo a time
        if isinstance(horario_dia, str):
            from datetime import datetime
            hora_obj = datetime.strptime(horario_dia, '%H:%M').time()
        else:
            hora_obj = horario_dia
    else:
        # Si no hay horario específico, usar hora_salida del sorteo
        hora_obj = sorteo.hora_salida

    if hora_obj:
        # Restar minutos de cierre
        minutos_cierre = getattr(sorteo, 'minutos_cierre', 5)
        from datetime import timedelta
        hora_cierre = (datetime.combine(fecha, hora_obj) - timedelta(minutes=minutos_cierre)).time()
        return hora_cierre

    return None
