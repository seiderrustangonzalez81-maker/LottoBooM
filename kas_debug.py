import os, sys
sys.path.insert(0, '/home/LottoBooM')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'LottoBooM.settings')
import django
django.setup()

from decimal import Decimal
from django.db.models import Q, Sum
from django.contrib.auth.models import User
from roles.models import Fondo, MovimientoFondo
from jugadas.models import Jugada
from resultados.models import Premio

kas = User.objects.get(username='Kasama')

print('=' * 78)
print('1. MOVIMIENTOS POR TIPO (con suma y signo)')
print('=' * 78)
for tipo in ['recarga', 'apuesta', 'premio', 'ajuste', 'cancelacion']:
    qs = MovimientoFondo.objects.filter(
        Q(receptor=kas) | Q(emisor=kas), tipo=tipo
    )
    n = qs.count()
    total_monto = qs.aggregate(t=Sum('monto'))['t'] or 0
    # Cuánto afecta a Kasama
    total_kasama = Decimal('0.00')
    for m in qs:
        if m.receptor_id == kas.id:
            total_kasama += m.monto
        else:
            total_kasama -= m.monto
    print(f'  {tipo:<15} n={n:<5} monto_sum={total_monto:<15} efecto_kasama={total_kasama}')

print()
print('=' * 78)
print('2. FONDO ACTUAL EN BD')
print('=' * 78)
for f in Fondo.objects.filter(usuario=kas):
    print(f'  FP={f.forma_pago.nombre if f.forma_pago else "?"} gestor={f.asignado_por.username if f.asignado_por else "?"} monto=${f.monto} activo={f.activo}')

print()
print('=' * 78)
print('3. APUESTAS vs PREMIOS LEGÍTIMOS (Premio table)')
print('=' * 78)
j_tot = Jugada.objects.filter(usuario=kas).aggregate(t=Sum('monto'))['t'] or 0
p_tot = Premio.objects.filter(jugada__usuario=kas).aggregate(t=Sum('monto_premio'))['t'] or 0
print(f'  Total apostado (Jugada):     ${j_tot}')
print(f'  Total premios (Premio):      ${p_tot}')
print(f'  Balance:                     ${Decimal(str(p_tot)) - Decimal(str(j_tot))}')

print()
print('=' * 78)
print('4. PREMIOS MALOS REVERTIDOS (los que causaron el bug)')
print('=' * 78)
ajustes = MovimientoFondo.objects.filter(
    Q(receptor=kas) | Q(emisor=kas), tipo='ajuste'
).order_by('id')
for a in ajustes:
    quien = 'receptor' if a.receptor_id == kas.id else 'emisor'
    print(f'  #{a.id} monto={a.monto} kasama_es={quien} de={a.emisor.username if a.emisor else "-"} para={a.receptor.username if a.receptor else "-"}')
