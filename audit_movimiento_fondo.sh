#!/bin/bash
set -euo pipefail
PROJECT="/home/LottoBooM"; cd "$PROJECT"
G='\033[0;32m'; Y='\033[0;33m'; B='\033[1;34m'; NC='\033[0m'
step(){ echo -e "\n${B}═══ $* ═══${NC}"; }

step "1/4 · ¿Cuántos movimientos tenemos y de qué tipos?"
python3 manage.py shell << 'PYEOF'
from roles.models import MovimientoFondo
from django.db.models import Count, Sum

qs = MovimientoFondo.objects.all()
print(f"Total movimientos: {qs.count()}\n")

print("Por tipo:")
for row in qs.values('tipo').annotate(n=Count('id'), total=Sum('monto')).order_by('-n'):
    print(f"  {row['tipo']:>15} · n={row['n']:>5} · Σ=${row['total'] or 0:.2f}")
PYEOF

step "2/4 · ¿Cuántos tienen saldo_antes/saldo_despues?"
python3 manage.py shell << 'PYEOF'
from roles.models import MovimientoFondo
qs = MovimientoFondo.objects.all()
total = qs.count()
con_saldos = qs.exclude(saldo_antes__isnull=True).exclude(saldo_despues__isnull=True).count()
con_motivo = qs.exclude(motivo='').count()
print(f"Total: {total}")
print(f"  Con saldo_antes+despues: {con_saldos} ({100*con_saldos/total:.1f}%)")
print(f"  Con motivo:              {con_motivo} ({100*con_motivo/total:.1f}%)")
print(f"  Sin motivo (legacy):     {total - con_motivo}")
PYEOF

step "3/4 · Reconciliación: Fondo.monto vs suma de Movimientos por FP"
python3 manage.py shell << 'PYEOF'
from roles.models import Fondo, MovimientoFondo
from django.db.models import Sum

# Tomar 10 clientes aleatorios con fondos
clientes_ids = list(Fondo.objects.filter(activo=True).values_list('usuario_id', flat=True).distinct()[:10])
print(f"Reconciliando {len(clientes_ids)} clientes...\n")

inconsistencias = 0
for cid in clientes_ids:
    fondos = Fondo.objects.filter(usuario_id=cid, activo=True)
    for f in fondos:
        # Fondo.monto = fuente de verdad
        fondo_monto = float(f.monto)

        # Suma teórica de MovimientoFondo con esa FP
        mov_suma = MovimientoFondo.objects.filter(
            receptor_id=cid,
            forma_pago=f.forma_pago,
        ).aggregate(t=Sum('monto'))['t']
        mov_suma = float(mov_suma or 0)

        diff = abs(fondo_monto - mov_suma)
        if diff > 0.01:
            inconsistencias += 1
            print(f"  ⚠ user={cid} FP={f.forma_pago.nombre if f.forma_pago else '-'}: Fondo=${fondo_monto:.2f} vs Movs=${mov_suma:.2f} (diff=${diff:.2f})")

print(f"\nTotal inconsistencias en muestra: {inconsistencias}")
PYEOF

step "4/4 · ¿Dónde se crean movimientos? (grep)"
echo "Archivos que crean MovimientoFondo:"
grep -rn "MovimientoFondo.objects.create" --include="*.py" . 2>/dev/null | grep -v "__pycache__\|.pyc\|venv" | sed 's|^\./||' | head -30

echo ""
echo "Archivos que modifican Fondo.monto directamente (sospechosos):"
grep -rn "\.monto\s*+=\|\.monto\s*-=\|fondo\.monto" --include="*.py" . 2>/dev/null | grep -v "__pycache__\|.pyc\|venv\|movimiento\|Movimiento" | sed 's|^\./||' | head -30
