# -*- coding: utf-8 -*-
"""Corrección definitiva de Kasama: fondo → $0, Postpago con deuda real."""
import os, sys
sys.path.insert(0, '/home/LottoBooM')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'LottoBooM.settings')
import django
django.setup()

from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from django.db.models import Sum
from django.contrib.auth.models import User
from roles.models import Fondo, Postpago, MovimientoFondo, Bono
from jugadas.models import Jugada
from resultados.models import Premio

kas = User.objects.get(username='Kasama')
seider = User.objects.get(username='Seider')

# 1. Calcular fondo correcto
apuestas = Jugada.objects.filter(usuario=kas).aggregate(t=Sum('monto'))['t'] or Decimal('0')
premios = Premio.objects.filter(jugada__usuario=kas).aggregate(t=Sum('monto_premio'))['t'] or Decimal('0')
bonos_activos = Bono.objects.filter(usuario=kas, estado='activo').aggregate(t=Sum('saldo_restante'))['t'] or Decimal('0')
recargas = Decimal('0')  # No hay recargas registradas

fondo_correcto = recargas - apuestas + premios + bonos_activos

print('=' * 78)
print('CORRECCIÓN DEFINITIVA DE KASAMA')
print('=' * 78)
print()
print(f'Apuestas:      ${apuestas}')
print(f'Premios:       +${premios}')
print(f'Bonos:         +${bonos_activos}')
print(f'Recargas:      ${recargas}')
print(f'────────────────────')
print(f'Fondo real:    ${fondo_correcto}')
print()

fondo_actual = Fondo.objects.filter(usuario=kas, activo=True).first()
print(f'Fondo actual en BD:  ${fondo_actual.monto if fondo_actual else 0}')
print(f'Postpago actual:     ${Postpago.objects.filter(cliente=kas).aggregate(t=Sum("saldo"))["t"] or 0}')
print()

if fondo_correcto >= 0:
    print(f'✅ Fondo positivo. Se dejará como fondo: ${fondo_correcto}')
    print('   NO se crea Postpago.')
    accion = 'solo_fondo'
    deuda = Decimal('0')
    fondo_nuevo = fondo_correcto
else:
    deuda = abs(fondo_correcto)
    fondo_nuevo = Decimal('0')
    print(f'⚠️  Fondo NEGATIVO: ${fondo_correcto}')
    print(f'   → Fondo = $0')
    print(f'   → Postpago = -${deuda}')
    accion = 'fondo_y_postpago'

resp = input('\n¿Aplicar? (si/no): ').strip().lower()
if resp != 'si':
    print('Cancelado.')
    raise SystemExit(0)

with transaction.atomic():
    # Ajustar fondo
    if not fondo_actual:
        fondo_actual, _ = Fondo.objects.get_or_create(
            usuario=kas, forma_pago_id=1, asignado_por=seider,
            defaults={'monto': Decimal('0'), 'activo': True}
        )
    fondo_actual.monto = fondo_nuevo
    fondo_actual.activo = True
    fondo_actual.save(update_fields=['monto', 'activo', 'actualizado_en'])
    
    if accion == 'fondo_y_postpago':
        # Crear/actualizar Postpago
        from pagos.models import FormaPago
        fp = FormaPago.objects.filter(id=1).first() or FormaPago.objects.filter(activo=True).first()
        pp, created = Postpago.objects.get_or_create(
            cliente=kas, gestor=seider, forma_pago=fp,
            defaults={'saldo': Decimal('0'), 'activo': True},
        )
        pp.saldo = -deuda
        pp.activo = True
        pp.save(update_fields=['saldo', 'activo', 'actualizado_en'])
        print(f'  Postpago {"creado" if created else "actualizado"}: -${deuda}')
    
    # Movimiento de auditoría
    MovimientoFondo.objects.create(
        emisor=kas if accion == 'fondo_y_postpago' else None,
        receptor=seider if accion == 'fondo_y_postpago' else kas,
        forma_pago=fondo_actual.forma_pago,
        monto=fondo_nuevo - fondo_actual.monto if accion == 'solo_fondo' else Decimal('0'),
        tipo='ajuste',
        estado='confirmado',
        datos_transferencia={
            'tipo': 'correccion_manual_kasama',
            'fecha': timezone.now().isoformat(),
            'apuestas': str(apuestas),
            'premios': str(premios),
            'fondo_anterior': '-4940.00',
            'fondo_nuevo': str(fondo_nuevo),
            'deuda_postpago': str(deuda),
        },
        nota=f'Corrección manual: fondo negativo convertido a Postpago. Kasama debe ${deuda}',
    )

print()
print('=' * 78)
print('CORRECCIÓN COMPLETA')
print('=' * 78)
print(f'  Fondo: ${fondo_actual.monto}')
if accion == 'fondo_y_postpago':
    print(f'  Postpago: -${deuda}')
