import os, sys
sys.path.insert(0, '/home/LottoBooM')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'LottoBooM.settings')
import django
django.setup()

from decimal import Decimal
from django.contrib.auth.models import User
from roles.models import Fondo, MovimientoFondo, Postpago
from jugadas.models import Jugada
from resultados.models import Premio
from django.db.models import Sum

kas = User.objects.get(username='Kasama')

print('=' * 78)
print('ESTADO ACTUAL DE KASAMA')
print('=' * 78)

print()
print('FONDOS:')
for f in Fondo.objects.filter(usuario=kas, activo=True):
    print(f'  FP={f.forma_pago.nombre if f.forma_pago else "?"} monto=${f.monto}')

print()
print('POSTPAGOS:')
for pp in Postpago.objects.filter(cliente=kas):
    print(f'  saldo=${pp.saldo} FP={pp.forma_pago.nombre if pp.forma_pago else "?"}')

print()
print('ÚLTIMAS 5 RECARGAS (movimientos):')
for m in MovimientoFondo.objects.filter(receptor=kas, tipo='recarga').order_by('-id')[:5]:
    print(f'  #{m.id} ${m.monto} fecha={m.fecha_creacion.strftime("%d/%m %H:%M") if hasattr(m, "fecha_creacion") else "?"} nota={m.nota[:50] if m.nota else ""}')

print()
print('=' * 78)
print('RECÁLCULO')
print('=' * 78)
apuestas = Jugada.objects.filter(usuario=kas).aggregate(t=Sum('monto'))['t'] or Decimal('0')
premios = Premio.objects.filter(jugada__usuario=kas).aggregate(t=Sum('monto_premio'))['t'] or Decimal('0')

# Contar recargas
recargas = MovimientoFondo.objects.filter(receptor=kas, tipo='recarga').aggregate(t=Sum('monto'))['t'] or Decimal('0')

print(f'Recargas reales registradas: ${recargas}')
print(f'Apuestas:                    -${apuestas}')
print(f'Premios:                     +${premios}')
print(f'─────────────────────────────')
print(f'Fondo correcto:              ${recargas - apuestas + premios}')

f = Fondo.objects.filter(usuario=kas, activo=True).first()
print()
print(f'Fondo en BD:                 ${f.monto if f else 0}')
print(f'Diferencia a corregir:       ${(f.monto if f else 0) - (recargas - apuestas + premios)}')
