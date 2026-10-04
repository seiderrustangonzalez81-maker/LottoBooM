# roles/templatetags/roles_extras.py
# -*- coding: utf-8 -*-
"""
Filtros personalizados para templates de la app roles.
Incluye filtros de roles, formato, operaciones matemáticas y más.
"""
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from django import template
from django.utils import timezone

register = template.Library()


# ============================================================
# FILTROS DE COMISIONES
# ============================================================

@register.filter
def buscar_fp(desglose, fp_id):
    """Busca en una lista de dicts el que tenga forma_pago_id == fp_id."""
    if not desglose:
        return None
    try:
        fp_id_int = int(fp_id)
    except (TypeError, ValueError):
        fp_id_int = fp_id
    for item in desglose:
        if item.get('forma_pago_id') == fp_id_int:
            return item
    return None


# ============================================================
# FILTROS DE ROLES Y PERMISOS
# ============================================================

@register.filter
def has_role(user, role_name):
    """Verifica si el usuario tiene el rol especificado activo."""
    if not user or not user.is_authenticated:
        return False
    return user.roles.filter(tipo=role_name, activo=True).exists()


@register.filter
def has_only_role(user, role_name):
    """Verifica que el usuario tenga EXACTAMENTE un rol activo y que sea el solicitado."""
    if not user or not user.is_authenticated:
        return False
    roles_activos = user.roles.filter(activo=True)
    return roles_activos.count() == 1 and roles_activos.filter(tipo=role_name).exists()


@register.filter
def get_active_role(user):
    """Devuelve el objeto Rol activo del usuario, o None si no tiene."""
    if not user or not user.is_authenticated:
        return None
    return user.roles.filter(activo=True).first()


@register.filter
def get_active_roles(user):
    """Devuelve un queryset con todos los roles activos del usuario."""
    if not user or not user.is_authenticated:
        return []
    return user.roles.filter(activo=True)


@register.filter
def has_any_role(user, roles):
    """Verifica si el usuario tiene al menos uno de los roles especificados."""
    if not user or not user.is_authenticated:
        return False
    roles_list = [r.strip() for r in str(roles).split(',') if r.strip()]
    if not roles_list:
        return False
    return user.roles.filter(tipo__in=roles_list, activo=True).exists()


@register.filter
def has_all_roles(user, roles):
    """Verifica si el usuario tiene todos los roles especificados."""
    if not user or not user.is_authenticated:
        return False
    roles_list = [r.strip() for r in str(roles).split(',') if r.strip()]
    if not roles_list:
        return False
    user_roles = set(
        user.roles.filter(tipo__in=roles_list, activo=True)
        .values_list('tipo', flat=True)
    )
    return all(r in user_roles for r in roles_list)


@register.filter
def role_display(rol_obj):
    """Devuelve el display legible del tipo de rol."""
    if not rol_obj:
        return ''
    try:
        return rol_obj.get_tipo_display()
    except AttributeError:
        return getattr(rol_obj, 'tipo', '')


# ============================================================
# FILTROS DE DICCIONARIOS Y LISTAS
# ============================================================

@register.filter
def get_item(dictionary, key):
    """Obtiene un valor de un diccionario. Devuelve None si no existe."""
    if dictionary is None:
        return None
    try:
        return dictionary.get(key)
    except AttributeError:
        return None


@register.filter
def dict_key(dictionary, key):
    """Alias de get_item."""
    if not dictionary:
        return None
    try:
        return dictionary.get(key)
    except AttributeError:
        return None


@register.filter
def values_list(queryset, field):
    """Devuelve una lista de valores de un campo de un queryset."""
    if not queryset:
        return []
    try:
        return list(queryset.values_list(field, flat=True))
    except (AttributeError, TypeError):
        return [getattr(obj, field, None) for obj in queryset]


# ============================================================
# FILTROS DE MAP Y SUM_ATTR
# ============================================================

@register.filter(name='map')
def map_filter(value, arg):
    """Aplica un atributo a cada elemento de una lista o queryset."""
    if not value:
        return []
    try:
        return [getattr(item, arg, None) for item in value]
    except (AttributeError, TypeError):
        return value


@register.filter(name='sum_attr')
def sum_attr_filter(value, arg):
    """Suma un atributo de cada elemento de una lista o queryset."""
    if not value:
        return Decimal('0.00')
    total = Decimal('0.00')
    for item in value:
        try:
            v = getattr(item, arg, Decimal('0.00'))
            if v is None:
                v = Decimal('0.00')
            total += Decimal(str(v))
        except (AttributeError, TypeError, InvalidOperation, ValueError):
            continue
    return total


# ============================================================
# FILTROS DE SUMA Y OPERACIONES MATEMÁTICAS
# ============================================================

@register.filter
def sum_values(iterable, attr=None):
    """Suma los valores de un iterable."""
    if not iterable:
        return Decimal('0.00')
    total = Decimal('0.00')
    for item in iterable:
        if attr:
            val = getattr(item, attr, Decimal('0.00'))
        else:
            val = item
        if val is None:
            continue
        try:
            total += Decimal(str(val))
        except (InvalidOperation, TypeError, ValueError):
            continue
    return total


@register.filter
def sum_queryset(queryset, field):
    """Suma los valores de un campo en un queryset."""
    if not queryset:
        return Decimal('0.00')
    total = Decimal('0.00')
    for obj in queryset:
        try:
            val = getattr(obj, field, Decimal('0.00'))
            if val is None:
                val = Decimal('0.00')
            total += Decimal(str(val))
        except (InvalidOperation, TypeError, ValueError, AttributeError):
            continue
    return total


@register.filter
def subtract(value, arg):
    """Resta arg de value."""
    try:
        return Decimal(str(value)) - Decimal(str(arg))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal('0.00')


@register.filter
def multiply(value, arg):
    """Multiplica value por arg."""
    try:
        return Decimal(str(value)) * Decimal(str(arg))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal('0.00')


@register.filter
def divide(value, arg):
    """Divide value entre arg, con manejo de división por cero."""
    try:
        arg_dec = Decimal(str(arg))
        if arg_dec == 0:
            return Decimal('0.00')
        return Decimal(str(value)) / arg_dec
    except (InvalidOperation, TypeError, ValueError, ZeroDivisionError):
        return Decimal('0.00')


# ============================================================
# FILTROS DE FORMATO
# ============================================================

@register.filter
def currency(value, decimals=2):
    """Formatea un número como moneda (ej: $1,234.56)."""
    if value is None:
        return "$0.00"
    try:
        v = Decimal(str(value))
        try:
            d = int(decimals)
        except (TypeError, ValueError):
            d = 2
        return "${:,.{}f}".format(v, d)
    except (InvalidOperation, TypeError, ValueError):
        return "$0.00"


@register.filter
def percentage(value, decimals=1):
    """Formatea un número como porcentaje (ej: 12.3%)."""
    if value is None:
        return "0.0%"
    try:
        v = Decimal(str(value)) * 100
        try:
            d = int(decimals)
        except (TypeError, ValueError):
            d = 1
        return "{:,.{}f}%".format(v, d)
    except (InvalidOperation, TypeError, ValueError):
        return "0.0%"


@register.filter
def truncate_chars(value, max_length=50):
    """Trunca un texto a max_length caracteres y añade '...'."""
    if not value:
        return ''
    try:
        max_length = int(max_length)
    except (TypeError, ValueError):
        max_length = 50
    text = str(value)
    if len(text) <= max_length:
        return text
    return text[:max_length] + '...'


# ============================================================
# FILTROS DE ESTADO PARA BADGES
# ============================================================

@register.filter
def status_badge(status):
    """Devuelve clases CSS para badges según estado común."""
    status_map = {
        'activo': 'bg-success',
        'inactivo': 'bg-secondary',
        'pendiente': 'bg-warning text-dark',
        'pagado': 'bg-success',
        'pagada': 'bg-success',
        'rechazado': 'bg-danger',
        'rechazada': 'bg-danger',
        'cancelado': 'bg-danger',
        'cancelada': 'bg-danger',
        'completado': 'bg-primary',
        'completada': 'bg-primary',
        'ganador': 'bg-success',
        'ganadora': 'bg-success',
        'perdedor': 'bg-danger',
        'perdedora': 'bg-danger',
        'procesando': 'bg-info',
        'entregado': 'bg-success',
        'enviado': 'bg-info',
        'leido': 'bg-secondary',
        'no_leido': 'bg-primary',
        'confirmado': 'bg-success',
        'confirmada': 'bg-success',
        'autorizado': 'bg-primary',
        'autorizada': 'bg-primary',
        'vencido': 'bg-danger',
        'vencida': 'bg-danger',
        'parcial': 'bg-warning text-dark',
        'anulado': 'bg-secondary',
        'anulada': 'bg-secondary',
        'aceptado': 'bg-info',
        'aceptada': 'bg-info',
        'solicitado': 'bg-warning text-dark',
        'aprobado': 'bg-success',
        'aprobada': 'bg-success',
        'expirado': 'bg-secondary',
        'expirada': 'bg-secondary',
        'borrador': 'bg-secondary',
        'en_proceso': 'bg-info',
        'pendiente_pago': 'bg-warning text-dark',
    }
    return status_map.get(str(status).lower(), 'bg-secondary')


# ============================================================
# FILTROS DE ATRIBUTOS Y UTILIDADES
# ============================================================

@register.filter
def get_attr(obj, attr):
    """Obtiene un atributo de un objeto de forma segura."""
    if not obj:
        return None
    try:
        return getattr(obj, attr, None)
    except (AttributeError, TypeError):
        return None


@register.filter
def is_none(value):
    """Verifica si el valor es None o vacío."""
    return value is None or value == ''


@register.filter
def natural_time(value):
    """Devuelve un tiempo natural (hace X minutos, hace X horas)."""
    if not value:
        return ''
    if not isinstance(value, (datetime, date)):
        return value

    if isinstance(value, date) and not isinstance(value, datetime):
        value = datetime(value.year, value.month, value.day,
                         tzinfo=timezone.get_current_timezone())

    if timezone.is_naive(value):
        value = timezone.make_aware(value, timezone.get_current_timezone())

    now = timezone.now()
    delta = now - value

    if delta.total_seconds() < 0:
        return 'en el futuro'

    if delta.days > 0:
        if delta.days == 1:
            return 'ayer'
        elif delta.days < 30:
            return f'hace {delta.days} días'
        else:
            return value.strftime('%d/%m/%Y')

    seconds = int(delta.total_seconds())
    if seconds > 3600:
        hours = seconds // 3600
        return f'hace {hours} horas'
    if seconds > 60:
        minutes = seconds // 60
        return f'hace {minutes} minutos'
    return 'hace un momento'


# ============================================================
# FILTROS PARA RANGOS Y LOOPS
# ============================================================

@register.filter
def get_range(value):
    """Devuelve un rango para usar en loops."""
    try:
        return range(int(value))
    except (TypeError, ValueError):
        return range(0)


@register.filter
def get_class(value):
    """Devuelve el nombre de la clase de un objeto (útil para debugging)."""
    if not value:
        return ''
    return value.__class__.__name__


@register.filter
def negativo(value):
    """Convierte un número a su negativo preservando decimales."""
    if value is None:
        return Decimal('0.00')
    try:
        return -Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal('0.00')
