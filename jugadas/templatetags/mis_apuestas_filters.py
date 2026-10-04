# jugadas/templatetags/mis_apuestas_filters.py
from django import template

register = template.Library()

@register.filter
def sum_attribute(value, arg):
    """
    Suma un atributo de una lista de objetos.
    Uso: {{ lista|sum_attribute:'monto_total' }}
    """
    if not value:
        return 0
    try:
        return sum(getattr(item, arg, 0) for item in value)
    except (TypeError, AttributeError):
        return 0