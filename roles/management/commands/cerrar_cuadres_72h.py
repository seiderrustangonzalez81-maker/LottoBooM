# -*- coding: utf-8 -*-
"""Cierra automáticamente cuadres abiertos hace más de 72 horas."""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta


class Command(BaseCommand):
    help = 'Cierra cuadres diarios abiertos hace más de 72 horas'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                           help='Solo muestra, no cierra')

    def handle(self, *args, **options):
        from roles.models import CuadreDiario

        hace_72h = timezone.now() - timedelta(hours=72)
        qs = CuadreDiario.objects.filter(
            cerrado=False,
            fecha__lt=hace_72h.date(),
        )

        n = qs.count()
        if n == 0:
            self.stdout.write(self.style.SUCCESS('No hay cuadres vencidos'))
            return

        self.stdout.write(f'Encontrados {n} cuadres abiertos >72h')

        for c in qs:
            if options['dry_run']:
                self.stdout.write(f'  [DRY] {c}')
            else:
                c.cerrado = True
                c.notas = (c.notas or '') + f'\n[auto] Cerrado por 72h el {timezone.now()}'
                c.save(update_fields=['cerrado', 'notas'])
                self.stdout.write(f'  ✅ Cerrado: {c}')

        if not options['dry_run']:
            self.stdout.write(self.style.SUCCESS(f'{n} cuadres cerrados'))
