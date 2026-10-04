from django.core.management.base import BaseCommand
from django.utils import timezone
from jugadas.models import Jugada
from sorteos.utils import get_hora_cierre
from roles.models import Notificacion
from django.contrib.auth.models import User
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Cancela jugadas con sobrelímite pendiente que hayan superado la hora de cierre'

    def handle(self, *args, **options):
        ahora = timezone.now()
        # Buscar jugadas pendientes con sobrelímite
        jugadas = Jugada.objects.filter(
            estado='pendiente_sobrelimite',
            sobrelimite=True
        ).select_related('sorteo', 'usuario', 'destinatario')

        canceladas = 0
        for jugada in jugadas:
            cierre = get_hora_cierre(jugada.sorteo.horarios, jugada.sorteo)
            if cierre and cierre < ahora:
                # Cancelar la jugada
                jugada.estado = 'cancelada'
                jugada.save()

                # Notificar al cliente
                if jugada.usuario:
                    Notificacion.objects.create(
                        usuario=jugada.usuario,
                        tipo='sobrelimite',
                        mensaje=f"❌ Tu jugada en {jugada.sorteo.nombre} por ${jugada.monto:.2f} ha sido cancelada por no recibir validación a tiempo.",
                        datos={'jugada_id': jugada.id, 'sorteo': jugada.sorteo.nombre, 'monto': float(jugada.monto)},
                        leido=False,
                        prioridad='alta',
                        categoria='sobrelimite'
                    )

                # Notificar al comercial si existe
                if jugada.comercial:
                    Notificacion.objects.create(
                        usuario=jugada.comercial,
                        tipo='sobrelimite',
                        mensaje=f"❌ El sobrelímite de {jugada.usuario.username} en {jugada.sorteo.nombre} ha sido cancelado automáticamente.",
                        datos={'jugada_id': jugada.id, 'cliente': jugada.usuario.username},
                        leido=False,
                        prioridad='media',
                        categoria='sobrelimite'
                    )

                # Notificar al banco/superadmin
                superadmins = User.objects.filter(roles__tipo='superadmin', roles__activo=True)
                for admin in superadmins:
                    Notificacion.objects.create(
                        usuario=admin,
                        tipo='sobrelimite',
                        mensaje=f"❌ Sobrelímite cancelado automáticamente: {jugada.usuario.username} en {jugada.sorteo.nombre}.",
                        datos={'jugada_id': jugada.id},
                        leido=False,
                        prioridad='media',
                        categoria='sobrelimite'
                    )

                canceladas += 1
                self.stdout.write(f"Cancelada jugada #{jugada.id} - {jugada.sorteo.nombre}")

        self.stdout.write(self.style.SUCCESS(f'✅ {canceladas} jugadas con sobrelímite canceladas.'))
