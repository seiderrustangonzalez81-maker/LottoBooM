# pagos/utils.py
# -*- coding: utf-8 -*-
"""
Fuente unica de formas de pago activas.
Todos los flujos (recarga, postpago, apuestas) usan esta funcion.
Sin filtros por nombre. Todas las formas activas, siempre.
"""


def get_formas_pago_activas():
    """Devuelve TODAS las formas de pago activas, ordenadas por nombre."""
    from .models import FormaPago
    return FormaPago.objects.filter(activo=True).order_by('nombre')
