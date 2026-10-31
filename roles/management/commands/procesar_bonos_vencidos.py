"""
Cron diario: procesa bonos vencidos.

Reglas:
- Si el cliente aposto >=750 por tarjeta -> aplica $50 al fondo, agota el bono,
  notifica a cliente + gestor, y suma $50 al descuento_bono del cuadre del gestor.
- Si no cumplio -> anula el bono y notifica al cliente.
- Idempotente via metadata.
- Soporta --dry-run.
"""
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from roles.models import Bono, CuadreDiario, Fondo
from roles.utils import crear_notificacion
from jugadas.models import Jugada
from pagos.models import FormaPago


class Command(BaseCommand):
    help = 'Procesa bonos vencidos: aplica o anula segun actividad'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Solo simula, no escribe')

    def handle(self, *args, **opts):
        dry = opts['dry_run']
        ahora = timezone.now()
        hoy = timezone.localdate()
        fp_tarjeta = FormaPago.objects.filter(nombre='Tarjeta').first()
        if not fp_tarjeta:
            self.stdout.write(self.style.ERROR('No hay forma de pago Tarjeta'))
            return

        vencidos = Bono.objects.filter(
            estado='activo', saldo_restante__gt=0,
            fecha_vencimiento__lt=ahora,
            # FIX_REFERIDOS_V1: recomendacion_gestor NO vence, se omite
            tipo__in=['registro', 'bienvenida', 'recomendacion',
                      'recomendacion_cliente'],
        ).order_by('id')

        aplicados, anulados, saltados = [], [], []

        with transaction.atomic():
            for b in vencidos:
                u = b.usuario

                if (b.metadata or {}).get('procesado_vencimiento'):
                    saltados.append((u.username, b.id, 'ya procesado'))
                    continue

                suma_t = (Jugada.objects
                          .filter(usuario=u, forma_pago=fp_tarjeta)
                          .exclude(estado='cancelada')
                          .aggregate(t=Sum('monto'))['t'] or Decimal('0'))

                if suma_t < Decimal('750'):
                    if not dry:
                        b.saldo_restante = Decimal('0.00')
                        b.estado = 'anulado'
                        b.metadata = {**(b.metadata or {}),
                                      'procesado_vencimiento': True,
                                      'motivo_anulacion': 'vencido_sin_750',
                                      'fecha_proceso': ahora.isoformat()}
                        b.save(update_fields=['saldo_restante', 'estado',
                                              'metadata', 'actualizado_en'])
                        crear_notificacion(
                            u, 'info',
                            'Bono de bienvenida expirado y anulado (no alcanzaste $750 en apuestas).',
                            datos={'bono_id': b.id},
                            prioridad='media', categoria='bono')
                    anulados.append((u.username, b.id, float(suma_t)))
                    continue

                ft = Fondo.objects.filter(usuario=u, forma_pago=fp_tarjeta,
                                          activo=True).first()
                if not ft:
                    saltados.append((u.username, b.id, 'sin_fondo_tarjeta'))
                    continue

                gid, gname = None, None
                acum = Decimal('0')
                for row in (Jugada.objects
                            .filter(usuario=u, forma_pago=fp_tarjeta)
                            .exclude(estado='cancelada')
                            .values('destinatario__id', 'destinatario__username')
                            .annotate(total=Sum('monto'))
                            .order_by('destinatario__id')):
                    acum += row['total'] or Decimal('0')
                    if acum >= Decimal('750'):
                        gid = row['destinatario__id']
                        gname = row['destinatario__username']
                        break

                if not dry:
                    ft.monto = ft.monto + Decimal('50.00')
                    ft.save(update_fields=['monto', 'actualizado_en'])

                    b.saldo_restante = Decimal('0.00')
                    b.estado = 'agotado'
                    b.metadata = {**(b.metadata or {}),
                                  'procesado_vencimiento': True,
                                  'bono_aplicado': True,
                                  'monto_aplicado': '50.00',
                                  'gestor_750_id': gid,
                                  'fecha_proceso': ahora.isoformat()}
                    b.save(update_fields=['saldo_restante', 'estado',
                                          'metadata', 'actualizado_en'])

                    if gid:
                        cuadre, _ = CuadreDiario.objects.get_or_create(
                            usuario_id=gid, fecha=hoy, defaults={})
                        cuadre.descuento_bono = (
                            cuadre.descuento_bono or Decimal('0')
                        ) + Decimal('50.00')
                        cuadre.save(update_fields=['descuento_bono'])

                    crear_notificacion(
                        u, 'recarga',
                        'Bono de bienvenida aplicado: $50 al fondo de Tarjeta.',
                        datos={'bono_id': b.id, 'monto': 50},
                        prioridad='alta', categoria='bono')
                    if gid:
                        g = User.objects.filter(id=gid).first()
                        if g:
                            crear_notificacion(
                                g, 'recarga',
                                f'Bono de {u.username}: $50 descontados de tu comision.',
                                datos={'bono_id': b.id, 'cliente': u.username,
                                       'monto': 50},
                                prioridad='media', categoria='bono')

                aplicados.append((u.username, b.id, gname, float(suma_t)))

        pre = '[DRY_RUN] ' if dry else '[PROCESADO] '
        self.stdout.write(f'\n{pre}Bonos vencidos: {vencidos.count()}')
        self.stdout.write(f'\n> APLICADOS ({len(aplicados)}):')
        for u, bid, g, s in aplicados:
            self.stdout.write(f'   {u:25s} bono={bid:3d} gestor={g} suma_t=${s:.2f}')
        self.stdout.write(f'\n> ANULADOS ({len(anulados)}):')
        for u, bid, s in anulados:
            self.stdout.write(f'   {u:25s} bono={bid:3d} suma_t=${s:.2f}')
        self.stdout.write(f'\n> SALTADOS ({len(saltados)}):')
        for u, bid, r in saltados:
            self.stdout.write(f'   {u:25s} bono={bid:3d} {r}')
        if dry:
            self.stdout.write('\n[DRY_RUN] Nada se escribio.')
