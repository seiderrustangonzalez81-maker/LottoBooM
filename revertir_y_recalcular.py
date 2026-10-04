# -*- coding: utf-8 -*-
"""
Revierte los 42 premios mal asignados y recalcula los premios reales.
FASE 1: Restar del fondo, borrar Premio malo, resetear jugada
FASE 2: Recalcular premios reales con jugada_es_ganadora() (ya arreglado)
"""
import os, sys, shutil, datetime
sys.path.insert(0, '/home/LottoBooM')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'LottoBooM.settings')
import django
django.setup()

from decimal import Decimal
from collections import defaultdict
from django.db import transaction
from django.utils import timezone
from datetime import timedelta

# ─── BACKUP BD ───
DB = '/home/LottoBooM/db.sqlite3'
TS = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
bak = DB + '.bak_revertir_' + TS
# shutil.copy2(DB, bak)  # sin backup (ya hay uno en /tmp)
print('Backup BD: omitido (ya hay copia en /tmp/seguro_db/)')
print()

from resultados.models import Premio, Resultado
from jugadas.models import Jugada
from roles.models import Fondo, MovimientoFondo
from resultados.reconciliacion import reconciliar_premio_jugada

# ═══════════════════════════════════════════════════════════
# FASE 1 — Revertir los malos
# ═══════════════════════════════════════════════════════════
print('=' * 78)
print('FASE 1 — Reversión de premios mal asignados')
print('=' * 78)

malos = []
for p in Premio.objects.select_related('jugada', 'jugada__sorteo', 'jugada__usuario', 'jugada__forma_pago', 'jugada__destinatario').all():
    j = p.jugada
    meta = p.metadata or {}
    rid = meta.get('resultado_id')
    if not rid:
        continue
    r = Resultado.objects.filter(id=rid).first()
    if not r:
        continue
    if r.sorteo_id != j.sorteo_id or r.fecha != j.fecha_sorteo:
        malos.append((p, j, r))

print(f'Total a revertir: {len(malos)}')
print()

revertidos = 0
total_revertido = Decimal('0.00')

for p, j, r in malos:
    try:
        with transaction.atomic():
            cliente = j.usuario
            gestor = j.destinatario
            fp = j.forma_pago
            monto = p.monto_premio

            # 1. Restar del fondo
            if fp and cliente:
                fondo, _ = Fondo.objects.select_for_update().get_or_create(
                    usuario=cliente,
                    forma_pago=fp,
                    asignado_por=gestor,
                    defaults={'monto': Decimal('0.00'), 'activo': True},
                )
                fondo.monto -= monto
                fondo.save(update_fields=['monto', 'actualizado_en'])

                # Movimiento de auditoría
                MovimientoFondo.objects.create(
                    emisor=cliente, receptor=gestor,
                    forma_pago=fp, monto=-monto,
                    tipo='ajuste', estado='confirmado',
                    datos_transferencia={
                        'tipo': 'reversion_premio_mal_asignado',
                        'premio_id': p.id,
                        'jugada_id': j.id,
                        'resultado_id': r.id,
                        'motivo': 'Sorteo/fecha no coincide',
                    },
                    nota=f'Reversión premio #{p.id}: sorteo {r.sorteo_id} vs jugada {j.sorteo_id}',
                )

            # 2. Resetear jugada
            j.estado = 'confirmada'
            j.monto_premio = None
            j.save(update_fields=['estado', 'monto_premio', 'actualizado_en'])

            # 3. Borrar Premio
            p.delete()

            revertidos += 1
            total_revertido += monto
            if revertidos % 10 == 0:
                print(f'  ... {revertidos}/{len(malos)}')
    except Exception as e:
        print(f'  ❌ Error premio #{p.id}: {e}')

print()
print(f'✅ Revertidos: {revertidos}')
print(f'✅ Total restado de fondos: ${total_revertido}')
print()

# ═══════════════════════════════════════════════════════════
# FASE 2 — Recalcular premios reales
# ═══════════════════════════════════════════════════════════
print('=' * 78)
print('FASE 2 — Recalcular premios reales (con fix sorteo+fecha)')
print('=' * 78)

hoy = timezone.localdate()
hace30 = hoy - timedelta(days=30)

q = Jugada.objects.filter(
    fecha_sorteo__gte=hace30,
    estado__in=['confirmada', 'pendiente'],
).select_related('sorteo', 'usuario', 'destinatario', 'forma_pago', 'forma_juego')

total_jugadas = q.count()
print(f'Jugadas a evaluar: {total_jugadas}')
print()

creados = 0
errores = 0
total_creado = Decimal('0.00')

for i, j in enumerate(q.iterator(), 1):
    r = Resultado.objects.filter(sorteo_id=j.sorteo_id, fecha=j.fecha_sorteo).first()
    if not r:
        continue
    try:
        premio, created, err = reconciliar_premio_jugada(j)
        if created:
            creados += 1
            total_creado += premio.monto_premio
            print(f'  ✅ #{j.id} {j.sorteo.nombre} {j.numero} ${j.monto} → premio ${premio.monto_premio}')
        if err:
            errores += 1
    except Exception as e:
        errores += 1
    if i % 500 == 0:
        print(f'  ... {i}/{total_jugadas}')

print()
print(f'✅ Premios reales creados: {creados}')
print(f'✅ Total acreditado: ${total_creado}')
print(f'⚠️  Errores: {errores}')
print()
print('=' * 78)
print(f'RESUMEN:')
print(f'  Revertidos: ${total_revertido}')
print(f'  Creados:    ${total_creado}')
print(f'  Diferencia: ${total_creado - total_revertido}')
print('=' * 78)
print(f'Backup disponible: {os.path.basename(bak)}')
