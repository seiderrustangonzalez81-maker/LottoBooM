# -*- coding: utf-8 -*-
"""
Reconciliación EXTRA — 26 y 28/09/2026.
Paga 6 premios 'corridos como fijo' que quedaron sin pagar.
Luego regenera cuadres 26→29 en orden cronológico.
"""
import os, sys, django
from datetime import date, timedelta
from decimal import Decimal

sys.path.insert(0, '/home/LottoBooM')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'LottoBooM.settings')
django.setup()

from django.db import transaction
from django.utils import timezone
from jugadas.models import Jugada
from resultados.models import Resultado, Premio
from resultados.views import jugada_es_ganadora
from roles.models import MovimientoFondo, Fondo, CuadreDiario
from roles.utils import _aplicar_ingreso_a_fondo, crear_notificacion
from roles.services import CuadreService


# ══════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN
# ══════════════════════════════════════════════════════════════════════
DRY_RUN = False   # ← cambiar a False para aplicar

JUGADAS_IDS = [1002, 1868, 2093, 4150, 7281, 9090]
FECHA_INI_REGENERAR = date(2026, 9, 26)
FECHA_FIN_REGENERAR = date(2026, 9, 29)


def log(msg=""):
    print(msg)


# ══════════════════════════════════════════════════════════════════════
# 1. Pago retroactivo
# ══════════════════════════════════════════════════════════════════════
def construir_plan():
    plan = []
    for jid in JUGADAS_IDS:
        j = (Jugada.objects
             .select_related('usuario','destinatario','forma_juego','forma_pago','sorteo')
             .get(id=jid))
        res = Resultado.objects.filter(sorteo=j.sorteo, fecha=j.fecha_sorteo).first()
        if not res:
            plan.append({'jid': jid, 'error': 'sin Resultado'})
            continue
        gana, mult = jugada_es_ganadora(j, res)
        if not gana:
            plan.append({'jid': jid, 'error': f'no gana (mult={mult})'})
            continue
        monto_premio = j.monto * Decimal(mult)
        plan.append({
            'jid': j.id,
            'jugada': j,
            'resultado': res,
            'multiplicador': mult,
            'monto_premio': monto_premio,
            'cliente': j.usuario,
            'gestor': j.destinatario,
            'forma_pago': j.forma_pago,
            'sorteo': j.sorteo.nombre,
            'fecha_sorteo': j.fecha_sorteo,
        })
    return plan


def aplicar_pago(item):
    j = item['jugada']
    monto_premio = item['monto_premio']
    mult = item['multiplicador']
    res = item['resultado']

    if Premio.objects.filter(jugada=j).exists():
        return ('SKIP', 'Premio ya existía')

    j.estado = 'ganadora'
    j.monto_premio = monto_premio
    j.save(update_fields=['estado', 'monto_premio', 'actualizado_en'])

    premio = Premio.objects.create(
        jugada=j,
        monto_premio=monto_premio,
        multiplicador_aplicado=mult,
        estado='pendiente',
        cobrado=False,
        metadata={'resultado_id': res.id, 'retroactivo': True, 'fix': 'pagar_fijo_como_corrido'},
    )

    descuento_postpago = Decimal('0.00')
    monto_al_fondo = monto_premio
    if j.forma_pago:
        monto_al_fondo, descuento_postpago = _aplicar_ingreso_a_fondo(
            cliente=j.usuario,
            gestor=j.destinatario or j.usuario,
            forma_pago=j.forma_pago,
            monto=monto_premio,
        )

    premio.cobrado = True
    premio.estado = 'pagado'
    premio.fecha_pago = timezone.now()
    premio.save(update_fields=['cobrado', 'estado', 'fecha_pago'])

    fp_pre = Fondo.objects.filter(
        usuario=j.usuario, forma_pago=j.forma_pago, activo=True
    ).first()
    saldo_post = fp_pre.monto if fp_pre else Decimal('0.00')
    saldo_pre = saldo_post - monto_al_fondo

    MovimientoFondo.objects.create(
        emisor=None,
        receptor=j.usuario,
        forma_pago=j.forma_pago,
        monto=monto_premio,
        tipo='premio',
        estado='confirmado',
        motivo=f"Premio retroactivo {res.sorteo.nombre} · jugada #{j.id}",
        saldo_antes=saldo_pre,
        saldo_despues=saldo_post,
        datos_transferencia={
            'tipo': 'premio_retroactivo',
            'premio_id': premio.id,
            'jugada_id': j.id,
            'sorteo': res.sorteo.nombre,
            'postpago_descontado': float(descuento_postpago),
            'fecha': timezone.now().isoformat(),
        },
        nota=f"Premio retroactivo jugada #{j.id} (fix pagar_fijo_como_corrido)",
    )

    msg = f"🎉 Premio retroactivo ${monto_premio} en {res.sorteo.nombre} (jugada #{j.id}, corridos ganó como fijo)"
    if descuento_postpago > 0:
        msg += f" — se descontaron ${descuento_postpago} de tu postpago"
    msg += " El premio ya está en tu saldo."

    crear_notificacion(
        usuario=j.usuario,
        tipo='premio',
        mensaje=msg,
        datos={
            'premio_id': premio.id,
            'monto': float(monto_premio),
            'postpago_descontado': float(descuento_postpago),
            'sorteo': res.sorteo.nombre,
            'retroactivo': True,
            'url_detalle': '/resultados/mis-premios/',
        },
    )

    return ('OK', f"${monto_premio} (postpago={descuento_postpago})")


# ══════════════════════════════════════════════════════════════════════
# 2. MAIN
# ══════════════════════════════════════════════════════════════════════
def main():
    log("=" * 78)
    log(f"RECONCILIACIÓN EXTRA 26-28/09 — pago + regeneración")
    log(f"Modo: {'🔍 DRY-RUN' if DRY_RUN else '🔥 APLICANDO'}")
    log("=" * 78)

    # ─── FASE 1: Pago ───
    log("\n[FASE 1] PREMIOS A PAGAR")
    plan = construir_plan()
    total = Decimal('0.00')
    usuarios_afectados = set()
    fechas_afectadas = set()
    for it in plan:
        if 'error' in it:
            log(f"  ⚠️ #{it['jid']} ERROR: {it['error']}")
            continue
        log(f"  • #{it['jid']:<6} | {it['fecha_sorteo']} | {it['cliente'].username:<10} → "
            f"{it['gestor'].username:<10} | ${it['jugada'].monto:<7} × {it['multiplicador']} = ${it['monto_premio']:<9}")
        total += it['monto_premio']
        usuarios_afectados.add(it['cliente'].id)
        fechas_afectadas.add(it['fecha_sorteo'])
    log(f"\n  💰 TOTAL: ${total}")
    log(f"  👥 Clientes: {len(usuarios_afectados)}")
    log(f"  📅 Fechas afectadas: {sorted(str(f) for f in fechas_afectadas)}")

    if DRY_RUN:
        log("\n[DRY-RUN] No se aplican cambios.")
        log("Cambia DRY_RUN=False y vuelve a ejecutar.")
        return

    log("\n[APLICANDO PAGOS]")
    exitos = 0
    for it in plan:
        if 'error' in it:
            continue
        try:
            with transaction.atomic():
                estado, info = aplicar_pago(it)
                log(f"  {estado} #{it['jid']} → {info}")
                exitos += 1
        except Exception as e:
            log(f"  ❌ #{it['jid']} ERROR: {e}")
    log(f"\n  ✅ {exitos} pagos aplicados")

    # ─── FASE 2: Regenerar cuadres 26→29 en orden ───
    log("\n[FASE 2] REGENERANDO CUADRES 26→29 EN ORDEN")
    from django.contrib.auth.models import User
    seider = User.objects.filter(username__iexact='seider').first()

    d = FECHA_INI_REGENERAR
    while d <= FECHA_FIN_REGENERAR:
        c_before = CuadreDiario.objects.filter(usuario=seider, fecha=d).first()
        ini_b = c_before.fondo_inicial_snapshot.get('Tarjeta') if c_before else '—'
        fin_b = c_before.fondo_final_snapshot.get('Tarjeta') if c_before else '—'
        CuadreService.generar_cuadre_completo(seider, d)
        c_after = CuadreDiario.objects.get(usuario=seider, fecha=d)
        ini_a = c_after.fondo_inicial_snapshot.get('Tarjeta')
        fin_a = c_after.fondo_final_snapshot.get('Tarjeta')
        log(f"  {d} | ini: {ini_b} → {ini_a} | fin: {fin_b} → {fin_a}")
        d += timedelta(days=1)

    # ─── FASE 3: Verificación ───
    log("\n[FASE 3] VERIFICACIÓN")
    d = FECHA_INI_REGENERAR
    ok = True
    while d < FECHA_FIN_REGENERAR:
        c1 = CuadreDiario.objects.get(usuario=seider, fecha=d)
        c2 = CuadreDiario.objects.get(usuario=seider, fecha=d + timedelta(days=1))
        fin1 = c1.fondo_final_snapshot.get('Tarjeta')
        ini2 = c2.fondo_inicial_snapshot.get('Tarjeta')
        mismo = str(fin1) == str(ini2)
        log(f"  {'✅' if mismo else '❌'} fin({d})={fin1} == ini({d+timedelta(days=1)})={ini2}")
        if not mismo:
            ok = False
        d += timedelta(days=1)

    log()
    if ok:
        log("🎉 RECONCILIACIÓN EXTRA COMPLETADA — cadena consistente")
    else:
        log("⚠️  Cadena rota — revisar")


if __name__ == '__main__':
    main()
