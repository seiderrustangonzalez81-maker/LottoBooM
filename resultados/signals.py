# -*- coding: utf-8 -*-
"""Señales de Resultado: auto-cierre de cuadres comerciales al insertar
el resultado del último sorteo de Georgia del día."""
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender='resultados.Resultado')
def cerrar_cuadres_si_ultimo_georgia(sender, instance, created, **kwargs):
    """Al crear un Resultado, si es el último sorteo de Georgia del día,
    cierra los cuadres comerciales de esa fecha."""
    if not created:
        return

    try:
        from roles.cuadre_cascade import auto_cerrar_si_ultimo_georgia
        auto_cerrar_si_ultimo_georgia(instance)
        logger.info(
            f"[cuadre] Verificación de cierre Georgia procesada para "
            f"resultado #{instance.id}"
        )
    except Exception as e:
        logger.exception(f"[cuadre] Error en cierre Georgia: {e}")
