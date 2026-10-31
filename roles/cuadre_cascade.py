# roles/cuadre_cascade.py
"""FIX_CUADRE_CASCADE_V1"""
import re
from datetime import date as _date, timedelta as _td


def _hora_efectiva(s):
    """Hora (h, m) de un sorteo. Prioriza hora_salida; si no, parsea el nombre."""
    if s.hora_salida:
        return (s.hora_salida.hour, s.hora_salida.minute)
    m = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(AM|PM)", s.nombre or "", re.IGNORECASE)
    if not m:
        return (0, 0)
    h = int(m.group(1))
    mi = int(m.group(2)) if m.group(2) else 0
    ampm = m.group(3).upper()
    if ampm == "PM" and h != 12:
        h += 12
    elif ampm == "AM" and h == 12:
        h = 0
    return (h, mi)


def es_ultimo_georgia_del_dia(sorteo):
    from sorteos.models import Sorteo
    if not sorteo or not sorteo.activo:
        return False
    if "georgia" not in (sorteo.nombre or "").lower():
        return False
    georgias = list(Sorteo.objects.filter(activo=True, nombre__icontains="georgia"))
    if not georgias:
        return False
    ultimo = max(georgias, key=_hora_efectiva)
    return ultimo.id == sorteo.id


def cerrar_cuadres_comerciales_fecha(fecha):
    from roles.models import Rol, CuadreDiario
    comerciales_ids = Rol.objects.filter(
        tipo="comercial", activo=True
    ).values_list("usuario_id", flat=True)
    return CuadreDiario.objects.filter(
        usuario_id__in=comerciales_ids, fecha=fecha, cerrado=False
    ).update(cerrado=True)


def auto_cerrar_si_ultimo_georgia(resultado):
    # FIX_RESULTADO_FECHA_V2: el modelo Resultado tiene campo `fecha`, no `fecha_sorteo`
    if not resultado or not resultado.sorteo_id:
        return 0
    fecha = getattr(resultado, 'fecha', None) or getattr(resultado, 'fecha_sorteo', None)
    if not fecha:
        return 0
    if es_ultimo_georgia_del_dia(resultado.sorteo):
        return cerrar_cuadres_comerciales_fecha(fecha)
    return 0


def puede_insertar_retroactiva(user):
    from roles.models import Rol
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return Rol.objects.filter(
        usuario=user, tipo__in=["superadmin", "banco"], activo=True
    ).exists()


def validar_retroactiva(user, fecha_sorteo):
    if fecha_sorteo is None or fecha_sorteo >= _date.today():
        return True, None
    if not puede_insertar_retroactiva(user):
        return False, "Solo banco o superadmin pueden insertar jugadas con fecha pasada."
    return True, None


def cascadear_retroactivas(jugadas_creadas):
    from roles.services import CuadreService
    from django.contrib.auth import get_user_model
    User = get_user_model()
    hoy = _date.today()
    pendientes = {}
    for j in jugadas_creadas or []:
        if not j or not j.destinatario_id or not j.fecha_sorteo:
            continue
        if j.fecha_sorteo >= hoy:
            continue
        prev = pendientes.get(j.destinatario_id)
        if prev is None or j.fecha_sorteo < prev:
            pendientes[j.destinatario_id] = j.fecha_sorteo
    if not pendientes:
        return []
    afectados = []
    for uid, fecha_min in pendientes.items():
        usuario = User.objects.filter(id=uid).first()
        if usuario:
            afectados.extend(
                CuadreService.recomputar_cuadres_desde(usuario, fecha_min)
            )
    return afectados
