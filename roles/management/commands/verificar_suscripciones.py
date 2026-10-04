"""
Verifica suscripciones vencidas y propaga la desactivación.

Reglas:
- Al vencer: se desactivan banco + sus comerciales (is_active=False y rol.activo=False)
- Se guardan los IDs en suscripcion.usuarios_desactivados para poder reactivar
- Los clientes NO se desactivan (siguen pudiendo loguearse)
- Al renovar, el Superadmin reactiva todo desde registrar_pago_banco
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth.models import User
from roles.models import SuscripcionBanco, Subordinacion, Notificacion, Rol


class Command(BaseCommand):
    help = 'Verifica suscripciones vencidas y desactiva banco + comerciales'

    def handle(self, *args, **options):
        ahora = timezone.now()
        vencidas = SuscripcionBanco.objects.filter(
            activo=True, fecha_vencimiento__lte=ahora
        )

        procesadas = 0
        for sus in vencidas:
            banco = sus.banco

            # Recolectar IDs: banco + comerciales activos
            ids_a_desactivar = [banco.id]
            comerciales_ids = list(
                Subordinacion.objects.filter(
                    jefe=banco, activo=True
                ).values_list('subordinado_id', flat=True)
            )
            ids_a_desactivar.extend(comerciales_ids)

            # 1. Guardar IDs para reactivación futura
            sus.usuarios_desactivados = ids_a_desactivar
            sus.activo = False
            sus.save(update_fields=['activo', 'usuarios_desactivados'])

            # 2. Desactivar User
            User.objects.filter(id__in=ids_a_desactivar).update(is_active=False)

            # 3. Desactivar Rol (banco + comercial)
            Rol.objects.filter(
                usuario_id__in=ids_a_desactivar,
                tipo__in=['banco', 'comercial']
            ).update(activo=False)

            # 4. Notificar al banco
            Notificacion.objects.create(
                usuario=banco,
                tipo='suscripcion',
                mensaje=(
                    f"❌ Tu suscripción ha vencido. Tu cuenta y la de tus "
                    f"{len(comerciales_ids)} comerciales han sido desactivadas. "
                    f"Contacta al Superadmin para reactivar."
                ),
                datos={
                    'fecha_vencimiento': sus.fecha_vencimiento.isoformat(),
                    'comerciales_desactivados': len(comerciales_ids),
                    'url_detalle': '/roles/panel-suscripcion/',
                },
                leido=False,
                prioridad='alta',
                categoria='financiera',
            )

            self.stdout.write(self.style.SUCCESS(
                f"✅ Suscripción de {banco.username} desactivada "
                f"({len(ids_a_desactivar)} usuarios afectados)"
            ))
            procesadas += 1

        if procesadas == 0:
            self.stdout.write('ℹ️  No hay suscripciones vencidas por procesar.')
        else:
            self.stdout.write(self.style.SUCCESS(
                f"✅ {procesadas} suscripción(es) procesada(s)."
            ))
