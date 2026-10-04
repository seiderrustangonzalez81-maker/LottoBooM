from django import template

register = template.Library()

@register.filter
def to_12h(value):
    """Convierte hora en formato 24h a 12h (ej: 14:30 -> 02:30 PM)"""
    if value:
        try:
            from datetime import datetime
            dt = datetime.strptime(value, '%H:%M')
            return dt.strftime('%I:%M %p')
        except:
            return value
    return value