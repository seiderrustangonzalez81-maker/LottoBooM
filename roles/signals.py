"""
Signals de la app 'roles'.

Notifica a superadmins y bancos cuando se registra un usuario nuevo.
"""

import logging
from django.db.models.signals import post_save
from django.contrib.auth.models import User
from django.dispatch import receiver

from .models import Notificacion, Rol


logger = logging.getLogger(__name__)


# Roles que reciben las notificaciones de nuevos registros
ROLES_ADMIN = ['superadmin', 'banco']


def _obtener_destinatarios():
    """Devuelve los Users con rol admin activo."""
    ids = (
        Rol.objects
        .filter(tipo__in=ROLES_ADMIN, activo=True)
        .values_list('usuario_id', flat=True)
        .distinct()
    )
    return User.objects.filter(id__in=ids, is_active=True)

@receiver(post_save, sender=User)
def notificar_nuevo_usuario(sender, instance, created, **kwargs):
    """Cuando se crea un User, notifica a los administradores."""
    if not created:
        return

    if instance.is_superuser and instance.username.lower() in ('admin', 'root'):
        return

    try:
        destinatarios = _obtener_destinatarios()
        if not destinatarios.exists():
            return

        # ── Mensaje principal ──
        mensaje = f"👤 Nuevo usuario: {instance.username}"
        if instance.email:
            mensaje += f" · {instance.email}"

        # ── Datos estructurados ──
        from django.urls import reverse
        try:
            url_ver = reverse('roles:lista_clientes')   # ajustar si tu URL se llama distinto
        except Exception:
            url_ver = '/roles/lista-clientes/'

        datos = {
            'accion': 'nuevo_registro',
            'usuario_id': instance.id,
            'username': instance.username,
            'email': instance.email or '',
            'fecha_registro': instance.date_joined.isoformat() if instance.date_joined else '',
            'url_detalle': f'{url_ver}?q={instance.username}',
        }

        for admin in destinatarios:
            Notificacion.objects.create(
                usuario=admin,
                tipo='sistema',
                mensaje=mensaje,
                prioridad='media',
                categoria='sistema',
                datos=datos,
            )

        logger.info(
            "Notificación de nuevo usuario '%s' enviada a %d admins.",
            instance.username, destinatarios.count()
        )

    except Exception as e:
        logger.exception("Error al notificar nuevo usuario: %s", e)