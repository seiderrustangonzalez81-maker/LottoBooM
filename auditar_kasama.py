# -*- coding: utf-8 -*-
"""Auditoría completa de Kasama: fondos, movimientos, jugadas, premios."""
import os, sys
sys.path.insert(0, '/home/LottoBooM')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'LottoBooM.settings')
import django
django.setup()

from decimal import Decimal
from django.contrib.auth.models import User
from django.db.models import Sum, Q

from roles.models import Fondo, MovimientoFondo, Bono, Postpago
from jugadas.models import Jugada
from resultados.models import Premio

# Buscar Kasama (puede haber varios)
candidatos = User.objects.filter(username__icontains='kasama')
print('=' * 78)
print('USUARIOS CON "kasama" EN USERNAME')
print('=' * 78)
for u in candidatos:
    rol = u.roles.filter(activo=True).first()
    print(f'  id={u.id} username={u.username} rol={rol.tipo if rol else "?"} activo={u.is_active}')

if not candidatos:
    print('❌ No hay Kasama')
    raise SystemExit(1)

# Tomar el primero (o el que sea cliente)
kas = None
for u in candidatos:
    if u.roles.filter(tipo='cliente', activo=True).exists():
        kas = u
        break
if not kas:
    kas = candidatos.first()

print()
print('=' * 78)
print(f'AUDITORÍA DE: {kas.username} (id={kas.id})')
print('=' * 78)

# ═══════════════════════════════════════════════════════════
# 1. FONDOS ACTUALES
# =═══════════════════════════════════════════════════════════
print()
print('1. FONDOS ACTUALES (por FP)')
print('-' * 78)
fondos = Fondo.objects.filter(usuario=kas, activo=True).select_related('forma_pago', 'asignado_por')
total_fondos = Decimal('0.00')
for f in fondos:
    fp_nombre = f.forma_pago.nombre if f.forma_pago else '?'
    gestor = f.asignado_por.username if f.asignado_por else '?'
    print(f'  FP={fp_nombre:<20} gestor={gestor:<15} monto=${f.monto}')
    total_fondos += f.monto

print(f'  ─────────────────────────────────────────────')
print(f'  TOTAL FONDOS: ${total_fondos}')

# ═══════════════════════════════════════════════════════════
# 2. BONOS
# ═══════════════════════════════════════════════════════════
print()
print('2. BONOS')
print('-' * 78)
bonos = Bono.objects.filter(usuario=kas).order_by('-id')
total_bonos = Decimal('0.00')
for b in bonos:
    gestor = b.asignado_por.username if b.asignado_por else '?'
    print(f'  #{b.id} tipo={b.tipo:<12} estado={b.estado:<10} saldo=${b.saldo_restante} gestor={gestor}')
    if b.estado == 'activo':
        total_bonos += b.saldo_restante or Decimal('0')
print(f'  ─────────────────────────────────────────────')
print(f'  TOTAL BONOS ACTIVOS: ${total_bonos}')

# ═══════════════════════════════════════════════════════════
# 3. POSTPAGOS
# ═══════════════════════════════════════════════════════════
print()
print('3. POSTPAGOS')
print('-' * 78)
pps = Postpago.objects.filter(cliente=kas)
total_pp = Decimal('0.00')
for p in pps:
    fp = p.forma_pago.nombre if p.forma_pago else '?'
    gestor = p.gestor.username if p.gestor else '?'
    print(f'  #{p.id} FP={fp:<15} gestor={gestor:<15} saldo=${p.saldo}')
    total_pp += p.saldo or Decimal('0')
print(f'  ─────────────────────────────────────────────')
print(f'  TOTAL POSTPAGO (saldo): ${total_pp}')

# ═══════════════════════════════════════════════════════════
# 4. MOVIMIENTOS DE FONDO (últimos 50)
# ═══════════════════════════════════════════════════════════
print()
print('4. MOVIMIENTOS DE FONDO (últimos 50)')
print('-' * 78)
movs = MovimientoFondo.objects.filter(
    Q(receptor=kas) | Q(emisor=kas)
).select_related('forma_pago', 'emisor', 'receptor').order_by('-id')[:50]

suma_in = Decimal('0.00')
suma_out = Decimal('0.00')
for m in movs:
    tipo = m.tipo
    emisor = m.emisor.username if m.emisor else '-'
    receptor = m.receptor.username if m.receptor else '-'
    fp = m.forma_pago.nombre if m.forma_pago else '-'
    signo = '+' if m.receptor_id == kas.id else '-'
    print(f'  #{m.id} {m.fecha.strftime("%d/%m %H:%M") if hasattr(m,"fecha") else ""} '
          f'tipo={tipo:<12} {signo}${m.monto:<10} FP={fp:<12} '
          f'de={emisor:<12} para={receptor}')
    if m.receptor_id == kas.id:
        suma_in += m.monto
    else:
        suma_out += m.monto

print(f'  ─────────────────────────────────────────────')
print(f'  IN (receptor=Kasama): ${suma_in}')
print(f'  OUT (emisor=Kasama): ${suma_out}')

# ═══════════════════════════════════════════════════════════
# 5. JUGADAS (resumen)
# ═══════════════════════════════════════════════════════════
print()
print('5. JUGADAS DE KASAMA')
print('-' * 78)
jugadas = Jugada.objects.filter(usuario=kas)
print(f'  Total jugadas: {jugadas.count()}')
agg = jugadas.aggregate(total=Sum('monto'), premios=Sum('monto_premio'))
total_jug = agg['total'] or Decimal('0')
total_prem = agg['premios'] or Decimal('0')
print(f'  Total apostado: ${total_jug}')
print(f'  Total premios: ${total_prem}')

# Desglose por estado
for est in ['confirmada', 'ganadora', 'perdedora', 'pendiente', 'cancelada']:
    n = jugadas.filter(estado=est).count()
    if n:
        print(f'    {est}: {n}')

# ═══════════════════════════════════════════════════════════
# 6. PREMIOS
# ═══════════════════════════════════════════════════════════
print()
print('6. PREMIOS DE KASAMA')
print('-' * 78)
premios = Premio.objects.filter(jugada__usuario=kas).select_related('jugada', 'jugada__sorteo')
print(f'  Total premios: {premios.count()}')
total_prem_prem = Decimal('0.00')
for p in premios.order_by('-id')[:30]:
    j = p.jugada
    print(f'  #{p.id} jugada#{j.id} {j.sorteo.nombre:<22} {j.fecha_sorteo} '
          f'num={j.numero:<12} monto=${p.monto_premio:<10} cobrado={p.cobrado}')
    total_prem_prem += p.monto_premio
print(f'  ─────────────────────────────────────────────')
print(f'  TOTAL PREMIOS (últimos 30): ${total_prem_prem}')

# ═══════════════════════════════════════════════════════════
# 7. CÁLCULO DE FONDO ESPERADO
# ═══════════════════════════════════════════════════════════
print()
print('=' * 78)
print('7. CÁLCULO DE FONDO ESPERADO')
print('=' * 78)
print()
print(f'  Fondos actuales en BD:       ${total_fondos}')
print(f'  Bonos activos:               ${total_bonos}')
print(f'  Postpago (saldo):            ${total_pp}')
print()
print(f'  Total apostado histórico:    ${total_jug}')
print(f'  Total premios recibidos:     ${total_prem}')
print()
print('  ⚠️  El fondo esperado depende de:')
print('     fondo_inicial + recargas - apuestas + premios - retiros + transferencias')
print('     Necesito ver los movimientos IN/OUT para calcularlo')
print()
print(f'  IN (recargas/transferencias): ${suma_in}')
print(f'  OUT (apuestas/retiros):       ${suma_out}')
print()
print(f'  💰 SALDO NETO POR MOVIMIENTOS: ${suma_in - suma_out}')
print(f'  💰 FONDOS ACTUALES EN BD:      ${total_fondos}')
print(f'  📊 DIFERENCIA:                 ${(suma_in - suma_out) - total_fondos}')
print()
print('AUDITORIA COMPLETA')
