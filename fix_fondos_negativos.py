# -*- coding: utf-8 -*-
"""Convierte Fondos negativos en Postpago (nueva semántica Fase 1)."""
import os, sys
sys.path.insert(0, '/home/LottoBooM')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'LottoBooM.settings')
import django
django.setup()

from decimal import Decimal
from django.db import transaction
from roles.models import Fondo, Postpago, MovimientoFondo

print('=' * 78)
print('CONVERSIÓN DE FONDOS NEGATIVOS A POSTPAGO')
print('=' * 78)

# 1. Detectar todos los fondos negativos
negativos = Fondo.objects.filter(monto__lt=0, activo=True).select_related('usuario', 'forma_pago', 'asignado_por')
print(f'\nFondos negativos encontrados: {negativos.count()}\n')

for f in negativos:
    print(f'  Usuario={f.usuario.username:<20} FP={f.forma_pago.nombre if f.forma_pago else "?":<15} monto=${f.monto}')

if not negativos.exists():
    print('\n✅ No hay fondos negativos. Nada que convertir.')
    raise SystemExit(0)

print()
resp = input('¿Convertir todos a Postpago? (si/no): ').strip().lower()
if resp != 'si':
    print('Cancelado.')
    raise SystemExit(0)

# 2. Convertir cada fondo negativo
convertidos = 0
for f in negativos:
    with transaction.atomic():
        deuda = abs(f.monto)  # ej: 4940
        
        # Fondo → 0
        f.monto = Decimal('0.00')
        f.save(update_fields=['monto', 'actualizado_en'])
        
        # Postpago de esa FP → sumar deuda
        pp, created = Postpago.objects.select_for_update().get_or_create(
            cliente=f.usuario,
            gestor=f.asignado_por,
            forma_pago=f.forma_pago,
            defaults={'saldo': Decimal('0.00'), 'activo': True},
        )
        pp.saldo -= deuda
        pp.activo = True
        pp.save(update_fields=['saldo', 'activo', 'actualizado_en'])
        
        # Movimiento de auditoría
        MovimientoFondo.objects.create(
            emisor=f.usuario,
            receptor=f.asignado_por,
            forma_pago=f.forma_pago,
            monto=-deuda,
            tipo='ajuste',
            estado='confirmado',
            datos_transferencia={
                'tipo': 'conversion_fondo_negativo_a_postpago',
                'fondo_original': str(-deuda),
            },
            nota=f'Conversión de fondo negativo (${deuda}) a Postpago',
        )
        
        convertidos += 1
        print(f'  ✓ {f.usuario.username}: Fondo ${deuda} → Postpago -${deuda}')

print()
print(f'✅ Convertidos: {convertidos}')
print()
print('=' * 78)
print('VERIFICACIÓN FINAL')
print('=' * 78)
neg = Fondo.objects.filter(monto__lt=0, activo=True).count()
print(f'Fondos negativos restantes: {neg}')
