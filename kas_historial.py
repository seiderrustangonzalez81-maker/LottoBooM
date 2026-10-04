import os, sys
sys.path.insert(0, '/home/LottoBooM')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'LottoBooM.settings')
import django
django.setup()

from decimal import Decimal
from datetime import datetime
from django.utils import timezone
from django.contrib.auth.models import User
from django.db.models import Q
from roles.models import Fondo, MovimientoFondo
from jugadas.models import Jugada
from resultados.models import Premio

kas = User.objects.get(username='Kasama')
hoy = timezone.localdate()

print('=' * 80)
print('HISTORIAL COMPLETO DE KASAMA — ORDENADO POR FECHA')
print('=' * 80)

# Fondo inicial real (antes del primer movimiento)
primer_mov = MovimientoFondo.objects.filter(
    Q(receptor=kas) | Q(emisor=kas)
).order_by('id').first()

# Reconstruir saldo
saldo = Decimal('0.00')
print(f'\n{"ID":<6} {"FECHA":<17} {"TIPO":<14} {"MONTO":>12} {"SALDO ANTES":>14} {"SALDO DESPUÉS":>14}  HOY')
print('-' * 80)

for m in MovimientoFondo.objects.filter(Q(receptor=kas) | Q(emisor=kas)).order_by('id'):
    delta = m.monto if m.receptor_id == kas.id else -m.monto
    antes = saldo
    saldo += delta
    fecha = getattr(m, 'fecha_creacion', None) or getattr(m, 'fecha', None)
    fecha_str = fecha.strftime('%d/%m %H:%M') if fecha else '?'
    es_hoy = '  <<< HOY' if fecha and fecha.date() == hoy else ''
    print(f'{m.id:<6} {fecha_str:<17} {m.tipo:<14} {delta:>+12.2f} {antes:>14.2f} {saldo:>14.2f}{es_hoy}')

print('-' * 80)
print(f'{"RECONSTRUIDO POR MOVIMIENTOS:":<50} {saldo:>14.2f}')

fbd = Fondo.objects.filter(usuario=kas, activo=True).first()
fondo_bd = fbd.monto if fbd else Decimal('0')
print(f'{"FONDO ACTUAL EN BD:":<50} {fondo_bd:>14.2f}')
print(f'{"DIFERENCIA:":<50} {saldo - fondo_bd:>14.2f}')

# ═══════════════════════════════════════════════════════════
# Fondo al inicio del día
# ═══════════════════════════════════════════════════════════
print()
print('=' * 80)
print('FONDO AL INICIO DEL DÍA (antes del primer movimiento de hoy)')
print('=' * 80)

saldo = Decimal('0.00')
fondo_inicio_dia = None
for m in MovimientoFondo.objects.filter(Q(receptor=kas) | Q(emisor=kas)).order_by('id'):
    fecha = getattr(m, 'fecha_creacion', None) or getattr(m, 'fecha', None)
    if fecha and fecha.date() == hoy:
        fondo_inicio_dia = saldo
        break
    delta = m.monto if m.receptor_id == kas.id else -m.monto
    saldo += delta

if fondo_inicio_dia is not None:
    print(f'  📊 Fondo al inicio del día: ${fondo_inicio_dia}')
else:
    print(f'  📊 No hubo movimientos hoy. Fondo actual = ${saldo}')

# ═══════════════════════════════════════════════════════════
# Apuestas de HOY
# ═══════════════════════════════════════════════════════════
print()
print('=' * 80)
print('APUESTAS DE HOY (por fecha_sorteo)')
print('=' * 80)
js = Jugada.objects.filter(usuario=kas, fecha_sorteo=hoy).order_by('id')
print(f'Total: {js.count()}')
tot = Decimal('0.00')
for j in js:
    print(f'  #{j.id} {j.sorteo.nombre:<20} {j.numero:<14} ${j.monto:<10} {j.estado}')
    tot += j.monto
print(f'  Total apostado hoy: ${tot}')

# ═══════════════════════════════════════════════════════════
# PREMIOS DE HOY
# ═══════════════════════════════════════════════════════════
print()
print('=' * 80)
print('PREMIOS DE HOY')
print('=' * 80)
ps = Premio.objects.filter(jugada__usuario=kas, creado_en__date=hoy)
tp = Decimal('0.00')
for p in ps:
    print(f'  #{p.id} {p.jugada.sorteo.nombre:<20} ${p.monto_premio}')
    tp += p.monto_premio
print(f'  Total premios hoy: ${tp}')

# ═══════════════════════════════════════════════════════════
# RESUMEN
# ═══════════════════════════════════════════════════════════
print()
print('=' * 80)
print('RESUMEN')
print('=' * 80)
if fondo_inicio_dia is not None:
    print(f'  Fondo al inicio de hoy:   ${fondo_inicio_dia}')
    print(f'  Apuestas de hoy:          -${tot}')
    print(f'  Premios de hoy:           +${tp}')
    print(f'  ─────────────────────────────────')
    print(f'  Fondo esperado AHORA:     ${fondo_inicio_dia - tot + tp}')
print(f'  Fondo actual en BD:       ${fondo_bd}')
