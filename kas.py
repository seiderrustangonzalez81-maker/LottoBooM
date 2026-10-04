import os, sys
sys.path.insert(0, '/home/LottoBooM')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'LottoBooM.settings')
import django
django.setup()

from decimal import Decimal
from django.utils import timezone
from django.contrib.auth.models import User
from django.db.models import Q
from roles.models import Fondo, MovimientoFondo
from jugadas.models import Jugada
from resultados.models import Premio

kas = User.objects.get(username='Kasama')
hoy = timezone.localdate()

print('=' * 78)
print('KASAMA — FONDO RECONSTRUIDO POR MOVIMIENTOS')
print('=' * 78)

saldo = Decimal('0.00')
primera_hoy = None
print()
print('MOVIMIENTOS CRONOLÓGICOS:')
for m in MovimientoFondo.objects.filter(Q(receptor=kas) | Q(emisor=kas)).order_by('id'):
    delta = m.monto if m.receptor_id == kas.id else -m.monto
    antes = saldo
    saldo += delta
    fecha = getattr(m, 'fecha_creacion', None) or getattr(m, 'fecha', None)
    marca = ''
    if fecha and fecha.date() == hoy:
        marca = '  <<< HOY'
        if primera_hoy is None:
            primera_hoy = (m, antes, saldo)
    fecha_str = fecha.strftime('%d/%m %H:%M') if fecha else '?'
    print(f'  #{m.id:<5} {fecha_str} {m.tipo:<12} {delta:+.2f}  saldo: {antes:.2f} -> {saldo:.2f}{marca}')

print()
print(f'Fondo reconstruido final: ${saldo}')
fbd = Fondo.objects.filter(usuario=kas, activo=True).first()
print(f'Fondo en BD:              ${fbd.monto if fbd else 0}')
print(f'Diferencia:               ${saldo - (fbd.monto if fbd else 0)}')

print()
print('=' * 78)
print(f'FONDO ANTES DE LA PRIMERA APUESTA HOY')
print('=' * 78)
if primera_hoy:
    m, antes, desp = primera_hoy
    print(f'  Primer mov hoy: #{m.id} tipo={m.tipo} monto=${m.monto}')
    print(f'  Fondo ANTES:   ${antes}')
    print(f'  Fondo DESPUÉS: ${desp}')
else:
    print('  Sin movimientos hoy')

print()
print('=' * 78)
print('APUESTAS CREADAS HOY (campo fecha)')
print('=' * 78)
from datetime import datetime
inicio = timezone.make_aware(datetime.combine(hoy, datetime.min.time()))
fin = timezone.make_aware(datetime.combine(hoy, datetime.max.time()))
js = Jugada.objects.filter(usuario=kas, fecha__gte=inicio, fecha__lte=fin).order_by('fecha')
print(f'Total: {js.count()}')
tot = Decimal('0.00')
for j in js:
    print(f'  #{j.id} {j.fecha.strftime("%H:%M")} {j.sorteo.nombre:<20} {j.numero:<10} ${j.monto}')
    tot += j.monto
print(f'Total apostado hoy: ${tot}')

print()
print('=' * 78)
print('PREMIOS HOY')
print('=' * 78)
ps = Premio.objects.filter(jugada__usuario=kas, creado_en__date=hoy)
tp = Decimal('0.00')
for p in ps:
    print(f'  #{p.id} {p.jugada.sorteo.nombre:<20} ${p.monto_premio}')
    tp += p.monto_premio
print(f'Total premios hoy: ${tp}')
