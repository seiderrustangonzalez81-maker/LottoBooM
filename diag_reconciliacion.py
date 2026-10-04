import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'LottoBooM.settings')
django.setup()

from decimal import Decimal
from django.db.models import Sum
from roles.models import Fondo, MovimientoFondo

print("═" * 70)
print("  DIAGNOSTICO COMPLETO DE RECONCILIACION")
print("═" * 70)
print()

# Traer todos los fondos activos
fondos = Fondo.objects.filter(activo=True).select_related('usuario', 'forma_pago')

total_fondos = fondos.count()
desincronizados = []
suma_diff_pos = Decimal('0.00')
suma_diff_neg = Decimal('0.00')
sin_movimientos = 0

for f in fondos:
    fondo_monto = f.monto or Decimal('0.00')

    # Suma teorica de movimientos para ese user + FP
    movs = MovimientoFondo.objects.filter(
        receptor=f.usuario,
        forma_pago=f.forma_pago,
    ).aggregate(t=Sum('monto'))['t'] or Decimal('0.00')

    # Si la FP tiene movimientos tipo 'aporte'/'retiro' con emisor=user tambien cuentan como negativos para el
    movs_emisor = MovimientoFondo.objects.filter(
        emisor=f.usuario,
        forma_pago=f.forma_pago,
    ).aggregate(t=Sum('monto'))['t'] or Decimal('0.00')

    # Saldo teorico total del user en esa FP = movs donde es receptor - movs donde es emisor
    # Pero ojo: en nuestro modelo el monto YA viene con signo, y el receptor siempre es el dueno del fondo
    # Solo contamos los que tienen receptor=user (los emisor=user son salidas del mismo)
    # Simplificacion: sumamos TODOS los movimientos donde el user es receptor
    teorico = movs

    diff = fondo_monto - teorico

    if abs(diff) > Decimal('0.01'):
        desincronizados.append({
            'cliente': f.usuario.username,
            'cliente_id': f.usuario.id,
            'fp': f.forma_pago.nombre if f.forma_pago else 'SIN FP',
            'fondo': fondo_monto,
            'movs': teorico,
            'diff': diff,
        })
        if diff > 0:
            suma_diff_pos += diff
        else:
            suma_diff_neg += diff

    # Contar fondos sin ningun movimiento
    if not MovimientoFondo.objects.filter(receptor=f.usuario, forma_pago=f.forma_pago).exists():
        sin_movimientos += 1

print(f"Total fondos activos:            {total_fondos}")
print(f"Fondos SIN movimientos:          {sin_movimientos}")
print(f"Fondos desincronizados:          {len(desincronizados)}")
print(f"Suma de diffs positivos:         +${suma_diff_pos}")
print(f"Suma de diffs negativos:         ${suma_diff_neg}")
print(f"Neto:                            ${suma_diff_pos + suma_diff_neg}")
print()

# Top 20 peores
print("═" * 70)
print("  TOP 20 DESINCRONIZADOS (por |diff| descendente)")
print("═" * 70)
desincronizados.sort(key=lambda x: abs(x['diff']), reverse=True)
for d in desincronizados[:20]:
    print(f"  {d['cliente']:<20} FP={d['fp']:<15} Fondo=${d['fondo']:<12} Movs=${d['movs']:<12} diff=${d['diff']}")

print()
print("═" * 70)
print("  AGRUPADO POR CLIENTE (top 10 por suma de |diff|)")
print("═" * 70)
por_cliente = {}
for d in desincronizados:
    c = d['cliente']
    if c not in por_cliente:
        por_cliente[c] = {'total_diff': Decimal('0.00'), 'count': 0, 'cliente_id': d['cliente_id']}
    por_cliente[c]['total_diff'] += abs(d['diff'])
    por_cliente[c]['count'] += 1

top_clientes = sorted(por_cliente.items(), key=lambda x: x[1]['total_diff'], reverse=True)[:10]
for c, info in top_clientes:
    print(f"  {c:<20} (id={info['cliente_id']}) · {info['count']} FP desincronizadas · |diff total|=${info['total_diff']}")
