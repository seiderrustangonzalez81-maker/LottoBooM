import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'LottoBooM.settings')
django.setup()

from decimal import Decimal
from django.db.models import Sum
from roles.models import Fondo, MovimientoFondo

# ═══════════════════════════════════════════════════════════════
# SOLO tipos que AFECTAN el Fondo
# ═══════════════════════════════════════════════════════════════
TIPOS_FONDO = ['recarga', 'apuesta', 'premio', 'retiro', 'ajuste']

print("═" * 70)
print("  DIAGNOSTICO v2 — Solo tipos que afectan Fondo")
print("  Tipos considerados:", TIPOS_FONDO)
print("═" * 70)
print()

fondos = Fondo.objects.filter(activo=True).select_related('usuario', 'forma_pago')

total_fondos = fondos.count()
desincronizados = []
suma_diff_pos = Decimal('0.00')
suma_diff_neg = Decimal('0.00')
sin_movs_con_saldo = 0
sin_movs_sin_saldo = 0

# Debug counters por tipo
tipos_encontrados = {}

for f in fondos:
    fondo_monto = f.monto or Decimal('0.00')

    # Solo tipos que afectan Fondo
    movs_qs = MovimientoFondo.objects.filter(
        receptor=f.usuario,
        forma_pago=f.forma_pago,
        tipo__in=TIPOS_FONDO,
    )
    for m in movs_qs.values('tipo'):
        tipos_encontrados[m['tipo']] = tipos_encontrados.get(m['tipo'], 0) + 1

    teorico = movs_qs.aggregate(t=Sum('monto'))['t'] or Decimal('0.00')
    diff = fondo_monto - teorico

    # Contar fondos SIN movimientos de estos tipos
    if not movs_qs.exists():
        if fondo_monto != 0:
            sin_movs_con_saldo += 1
        else:
            sin_movs_sin_saldo += 1

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

print(f"Total fondos activos:            {total_fondos}")
print(f"Fondos SIN movs relevantes:")
print(f"  con saldo != 0:                {sin_movs_con_saldo}")
print(f"  con saldo == 0:                {sin_movs_sin_saldo}")
print(f"Fondos desincronizados:          {len(desincronizados)}")
print(f"Suma de diffs positivos:         +${suma_diff_pos}")
print(f"Suma de diffs negativos:         ${suma_diff_neg}")
print(f"Neto:                            ${suma_diff_pos + suma_diff_neg}")
print()

# ═══════════════════════════════════════════════════════════════
# TOP 20 peores
# ═══════════════════════════════════════════════════════════════
print("═" * 70)
print("  TOP 20 DESINCRONIZADOS")
print("═" * 70)
desincronizados.sort(key=lambda x: abs(x['diff']), reverse=True)
for d in desincronizados[:20]:
    print(f"  {d['cliente']:<20} FP={d['fp']:<15} Fondo=${d['fondo']:<12} Movs=${d['movs']:<12} diff=${d['diff']}")

print()
print("═" * 70)
print("  ESTADISTICAS")
print("═" * 70)

# Histograma de diffs
rangos = {'<$10': 0, '$10-100': 0, '$100-1K': 0, '$1K-10K': 0, '>$10K': 0}
for d in desincronizados:
    a = abs(d['diff'])
    if a < 10: rangos['<$10'] += 1
    elif a < 100: rangos['$10-100'] += 1
    elif a < 1000: rangos['$100-1K'] += 1
    elif a < 10000: rangos['$1K-10K'] += 1
    else: rangos['>$10K'] += 1

for r, n in rangos.items():
    print(f"  diff {r:<10}: {n} fondos")

print()
print("Movimientos por tipo (contados durante el analisis):")
for t, n in sorted(tipos_encontrados.items()):
    print(f"  {t:<15}: {n}")
