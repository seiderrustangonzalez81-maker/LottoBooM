"""
Cierra los cuadres del día anterior.

Uso en cron: 0 6 * * * python manage.py cerrar_cuadres

Regla:
- A las 06:00 hora Cuba se cierra el cuadre del día anterior.
- Los cuadres cerrados no se pueden editar.
- Se ejecuta por cada gestor activo (banco, comercial, superadmin).
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

from django.contrib.auth.models import User
from roles.models import CuadreDiario, Notificacion


class Command(BaseCommand):
    help = 'Cierra los cuadres del día anterior'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Solo mostrar, no modificar')

    def handle(self, *args, **options):
        ahora = timezone.now()
        hoy = timezone.localdate()
        ayer = hoy - timedelta(days=1)

        cuadres = CuadreDiario.objects.filter(
            fecha=ayer,
            cerrado=False,
        ).select_related('usuario')

        total = cuadres.count()

        if options['dry_run']:
            self.stdout.write(f'[DRY-RUN] {total} cuadres por cerrar del {ayer}')
            for c in cuadres[:20]:
                self.stdout.write(f'  {c.usuario.username} — {c.fecha}')
            return

        cerrados = 0
        for cuadre in cuadres:
            cuadre.cerrado = True
            cuadre.save(update_fields=['cerrado'])
            cerrados += 1

            try:
                Notificacion.objects.create(
                    usuario=cuadre.usuario,
                    tipo='info',
                    mensaje=f"🔒 Tu cuadre del {cuadre.fecha.strftime('%d/%m/%Y')} ha sido cerrado automáticamente.",
                    datos={'cuadre_id': cuadre.id, 'fecha': str(cuadre.fecha)},
                    leido=False,
                    prioridad='baja',
                    categoria='sistema',
                )
            except Exception:
                pass

        self.stdout.write(self.style.SUCCESS(
            f'✅ {cerrados} cuadres cerrados del {ayer}'
        ))
