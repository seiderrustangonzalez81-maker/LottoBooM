from django import template
from pagos.models import FormaPago

register = template.Library()

@register.simple_tag
def get_formas_pago():
    """Devuelve todas las formas de pago activas excluyendo Bono (ID=2) y otras excluidas."""
    return FormaPago.objects.filter(activo=True)
