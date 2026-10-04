"""
Uso: python manage.py expirar_bonos
Marca como 'expirado' todos los bonos activos cuya fecha_vencimiento ya pasó.
Pensado para ejecutarse como cron diario.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from roles.models import Bono


class Command(BaseCommand):
    help = 'Marca como expirados los bonos vencidos'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Solo mostrar, no modificar')

    def handle(self, *args, **options):
        ahora = timezone.now()
        qs = Bono.objects.filter(
            estado='activo',
            fecha_vencimiento__isnull=False,
            fecha_vencimiento__lte=ahora,
        )
        total = qs.count()

        if options['dry_run']:
            self.stdout.write(f'[DRY-RUN] {total} bonos vencidos')
            for b in qs[:20]:
                self.stdout.write(
                    f'  id={b.id} user={b.usuario.username} '
                    f'tipo={b.tipo} venc={b.fecha_vencimiento}'
                )
            return

        modificados = qs.update(estado='expirado', actualizado_en=ahora)
        self.stdout.write(self.style.SUCCESS(
            f'✅ {modificados} bonos marcados como expirados'
        ))
