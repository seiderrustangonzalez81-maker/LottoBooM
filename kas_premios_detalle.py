import os, sys
sys.path.insert(0, '/home/LottoBooM')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'LottoBooM.settings')
import django
django.setup()

from decimal import Decimal
from django.contrib.auth.models import User
from roles.models import MovimientoFondo
from jugadas.models import Jugada
from resultados.models import Premio

kas = User.objects.get(username='Kasama')

print('PREMIOS EN MOVIMIENTOS (uno por uno):')
total = Decimal('0.00')
for m in MovimientoFondo.objects.filter(receptor=kas, tipo='premio').order_by('id'):
    print(f'  #{m.id} monto=${m.monto}')
    total += m.monto
print(f'  TOTAL: ${total}')

print()
print('PREMIOS REALES EN TABLA Premio:')
tr = Decimal('0.00')
for p in Premio.objects.filter(jugada__usuario=kas).order_by('id'):
    print(f'  #{p.id} jugada#{p.jugada.id} sorteo={p.jugada.sorteo.nombre} fecha={p.jugada.fecha_sorteo} num={p.jugada.numero} monto=${p.monto_premio}')
    tr += p.monto_premio
print(f'  TOTAL: ${tr}')

print()
print(f'DIFERENCIA (movs - tabla Premio): ${total - tr}')
print(f'  → Esto es lo que hay que investigar/revertir')
