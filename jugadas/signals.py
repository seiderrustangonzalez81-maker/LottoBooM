# -*- coding: utf-8 -*-
"""Señales de Jugada: apertura automática de cuadre al crear la primera jugada."""
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

logger = logging.getLogger(__name__)


@receiver(post_save, sender='jugadas.Jugada')
def abrir_cuadre_en_primera_jugada(sender, instance, created, **kwargs):
    """Asegura que exista un CuadreDiario para el destinatario y la fecha
    del sorteo. Si es retroactiva (fecha_sorteo < hoy), valida permisos y
    cascadea hacia adelante."""
    if not created:
        return

    try:
        from roles.services import CuadreService
        from roles.cuadre_cascade import cascadear_retroactivas, validar_retroactiva

        fecha_sorteo = getattr(instance, 'fecha_sorteo', None)
        destinatario = getattr(instance, 'destinatario', None)
        if not fecha_sorteo or not destinatario:
            return

        hoy = timezone.localdate()
        es_retro = fecha_sorteo < hoy

        if es_retro:
            # Firma real: validar_retroactiva(user, fecha_sorteo) -> (bool, msg)
            autor = (
                getattr(instance, 'usuario', None)
                or getattr(instance, 'autorizada_por', None)
            )
            permitido, msg = validar_retroactiva(autor, fecha_sorteo)
            if not permitido:
                logger.warning(
                    f"[cuadre] Jugada retroactiva #{instance.id} bloqueada: {msg}"
                )
                # Igual abrimos el cuadre (el cuadre del destinatario debe existir)
                # para que se vea el movimiento; solo no cascadea
                CuadreService.generar_cuadre_completo(destinatario, fecha_sorteo)
                return

        # Generar/abrir cuadre (idempotente vía get_or_create + herencia V4)
        CuadreService.generar_cuadre_completo(destinatario, fecha_sorteo)
        logger.info(
            f"[cuadre] Apertura asegurada para {destinatario.username} "
            f"en {fecha_sorteo} (jugada #{instance.id})"
        )

        # Cascadear si retroactiva — la firma real recibe LISTA
        if es_retro:
            try:
                cascadear_retroactivas([instance])
            except Exception as e:
                logger.exception(f"[cuadre] cascadear_retroactivas falló: {e}")

    except Exception as e:
        # Nunca romper la inserción de la jugada por un fallo de cuadre
        logger.exception(f"[cuadre] Error en apertura automática: {e}")


# ═══════════════════════════════════════════════════════════════
# NOTIFICACIÓN DE PREMIO — captura estado anterior + crea Notif
# ═══════════════════════════════════════════════════════════════
from django.db.models.signals import pre_save


@receiver(pre_save, sender='jugadas.Jugada')
def _capturar_estado_anterior(sender, instance, **kwargs):
    """Guarda el estado previo para detectar transiciones a ganadora."""
    if not instance.pk:
        instance._estado_anterior = None
        return
    try:
        instance._estado_anterior = sender.objects.only('estado').get(
            pk=instance.pk
        ).estado
    except sender.DoesNotExist:
        instance._estado_anterior = None


def _build_razon_premio(jugada):
    """Construye la razón legible del premio."""
    partes = []
    if jugada.numero:
        partes.append(f"número {jugada.numero}")
    if getattr(jugada, 'forma_juego', None):
        partes.append(jugada.forma_juego.nombre)
    if getattr(jugada, 'sorteo', None):
        partes.append(f"en {jugada.sorteo.nombre}")
    return " · ".join(partes) if partes else "Jugada ganadora"


@receiver(post_save, sender='jugadas.Jugada')
def notificar_premio(sender, instance, created, **kwargs):
    """Crea Notificacion cuando una jugada pasa a estado=ganadora."""
    if instance.estado != 'ganadora':
        return
    if not instance.monto_premio or instance.monto_premio <= 0:
        return

    anterior = getattr(instance, '_estado_anterior', None)
    if anterior == 'ganadora' and not created:
        return  # ya estaba ganadora, no duplicar

    try:
        from roles.models import Notificacion

        razon = _build_razon_premio(instance)
        sorteo_nombre = instance.sorteo.nombre if instance.sorteo else 'sorteo'
        monto_str = f"${instance.monto_premio:,.2f}"

        mensaje = (
            f"🏆 ¡Felicitaciones! Fuiste premiado con {monto_str} "
            f"en {sorteo_nombre}. Ganaste por: {razon}."
        )

        datos = {
            'jugada_id': instance.id,
            'monto': str(instance.monto_premio),
            'sorteo': sorteo_nombre,
            'numero': instance.numero or '',
            'forma_juego': (
                instance.forma_juego.nombre
                if getattr(instance, 'forma_juego', None) else ''
            ),
            'razon': razon,
        }

        # Dedupe compatible con SQLite/MariaDB (sin JSON contains)
        existente = False
        for d in Notificacion.objects.filter(
            usuario=instance.usuario, tipo='premio'
        ).values_list('datos', flat=True)[:200]:
            if d and d.get('jugada_id') == instance.id:
                existente = True
                break
        if existente:
            return

        Notificacion.objects.create(
            usuario=instance.usuario,
            tipo='premio',
            categoria='premio',
            mensaje=mensaje,
            prioridad='alta',
            con_sonido=True,
            datos=datos,
        )
        logger.info(
            f"[premio] Notificación creada para {instance.usuario.username} "
            f"(jugada #{instance.id}, ${instance.monto_premio})"
        )
    except Exception as e:
        logger.exception(f"[premio] Error creando notificación: {e}")
