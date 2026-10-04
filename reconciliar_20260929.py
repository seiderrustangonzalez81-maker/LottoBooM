# -*- coding: utf-8 -*-
"""
Reconciliación de premios 2026-09-29 — fix 'pagar corrido como fijo'.
Paga los 6 falsos negativos detectados, actualiza CuadreDiario y verifica.
"""
import os, sys, django
from datetime import date
from decimal import Decimal

sys.path.insert(0, '/home/LottoBooM')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'LottoBooM.settings')
django.setup()

from django.db import transaction
from django.utils import timezone
from jugadas.models import Jugada
from resultados.models import Resultado, Premio
from resultados.views import jugada_es_ganadora
from roles.models import (
    MovimientoFondo, Fondo, CuadreDiario,
    PostpagoCliente,
)
from roles.utils import _aplicar_ingreso_a_fondo, crear_notificacion


# ══════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN
# ══════════════════════════════════════════════════════════════════════
FECHA = date(2026, 9, 29)
DRY_RUN = False   # ← cambiar a False cuando confirmes el plan

# IDs a reconciliar (los 6 detectados por el diagnóstico)
JUGADAS_IDS = [12180, 10594, 10585, 10386, 10145, 10136]


def log(msg=""):
    print(msg)


# ══════════════════════════════════════════════════════════════════════
# 1. PLAN — arma la lista de lo que se va a hacer (sin tocar DB)
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
        })
    return plan


# ══════════════════════════════════════════════════════════════════════
# 2. APLICAR UN PAGO (en transacción)
# ══════════════════════════════════════════════════════════════════════
def aplicar_pago(item, request_user=None):
    j = item['jugada']
    monto_premio = item['monto_premio']
    mult = item['multiplicador']
    res = item['resultado']

    # Guard de idempotencia: si ya existe Premio, no repetir
    if Premio.objects.filter(jugada=j).exists():
        return ('SKIP', 'Premio ya existía')

    # 2.1 Marcar jugada como ganadora
    j.estado = 'ganadora'
    j.monto_premio = monto_premio
    j.save(update_fields=['estado', 'monto_premio', 'actualizado_en'])

    # 2.2 Crear Premio
    premio = Premio.objects.create(
        jugada=j,
        monto_premio=monto_premio,
        multiplicador_aplicado=mult,
        estado='pendiente',
        cobrado=False,
        metadata={'resultado_id': res.id, 'retroactivo': True, 'fix': 'pagar_fijo_como_corrido'},
    )

    # 2.3 Acreditar al fondo (con descuento de postpago si aplica)
    descuento_postpago = Decimal('0.00')
    monto_al_fondo = monto_premio
    if j.forma_pago:
        monto_al_fondo, descuento_postpago = _aplicar_ingreso_a_fondo(
            cliente=j.usuario,
            gestor=j.destinatario or j.usuario,
            forma_pago=j.forma_pago,
            monto=monto_premio,
        )

    # 2.4 Marcar Premio como pagado
    premio.cobrado = True
    premio.estado = 'pagado'
    premio.fecha_pago = timezone.now()
    premio.pagado_por = request_user
    premio.save(update_fields=['cobrado', 'estado', 'fecha_pago', 'pagado_por'])

    # 2.5 MovimientoFondo (con saldos antes/después)
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
        nota=(
            f"Premio retroactivo por jugada #{j.id} "
            f"(fix pagar_fijo_como_corrido)"
            + (f" — postpago descontado: ${descuento_postpago}" if descuento_postpago > 0 else "")
        ),
    )

    # 2.6 Notificar al cliente
    msg = (
        f"🎉 Premio retroactivo ${monto_premio} en {res.sorteo.nombre} "
        f"(jugada #{j.id}, forma: corridos ganó como fijo)"
    )
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
            'fecha': timezone.now().isoformat(),
            'url_detalle': '/resultados/mis-premios/',
        },
    )

    return ('OK', f"${monto_premio} (al_fondo={monto_al_fondo}, postpago={descuento_postpago})")


# ══════════════════════════════════════════════════════════════════════
# 3. RECALCULAR CuadreDiario de los usuarios afectados
# ══════════════════════════════════════════════════════════════════════
def recalcular_cuadre(usuario):
    """
    Recalcula fondo_final_snapshot del CuadreDiario del usuario para FECHA,
    leyendo el estado ACTUAL de Fondos. No toca cerrado/inicial.
    """
    cuadre = CuadreDiario.objects.filter(usuario=usuario, fecha=FECHA).first()
    if not cuadre:
        return None, 'sin CuadreDiario'

    if cuadre.cerrado:
        return cuadre, 'CERRADO — no se toca'

    # Snapshot actual de fondos por forma de pago
    fondos = Fondo.objects.filter(usuario=usuario, activo=True).select_related('forma_pago')
    nuevo_snap = {}
    for f in fondos:
        fp_nombre = f.forma_pago.nombre if f.forma_pago else 'SinFP'
        nuevo_snap[fp_nombre] = str(f.monto)

    antes = dict(cuadre.fondo_final_snapshot or {})
    cuadre.fondo_final_snapshot = nuevo_snap
    cuadre.save(update_fields=['fondo_final_snapshot'])
    return cuadre, ('actualizado', antes, nuevo_snap)


# ══════════════════════════════════════════════════════════════════════
# 4. VERIFICACIÓN POST-FIX
# ══════════════════════════════════════════════════════════════════════
def verificar():
    log("\n" + "=" * 78)
    log("VERIFICACIÓN POST-FIX")
    log("=" * 78)

    fallos = 0
    for jid in JUGADAS_IDS:
        j = Jugada.objects.get(id=jid)
        p = Premio.objects.filter(jugada=j).first()
        mov = MovimientoFondo.objects.filter(
            receptor=j.usuario, tipo='premio',
            datos_transferencia__jugada_id=j.id,
        ).first()
        estado_ok = j.estado == 'ganadora'
        premio_ok = p is not None and p.estado == 'pagado'
        mov_ok = mov is not None
        marca = "✅" if (estado_ok and premio_ok and mov_ok) else "❌"
        if not (estado_ok and premio_ok and mov_ok):
            fallos += 1
        log(f"  {marca} #{jid} | estado={j.estado} | premio={'#'+str(p.id) if p else 'NO'} "
            f"({p.estado if p else '-'}) | mov_fondo={mov.id if mov else 'NO'} | monto={j.monto_premio}")

    log()
    if fallos == 0:
        log("  ✅ Todas las jugadas verificadas correctamente")
    else:
        log(f"  ❌ {fallos} jugadas con problemas")
    return fallos


# ══════════════════════════════════════════════════════════════════════
# 5. MAIN
# ══════════════════════════════════════════════════════════════════════
def main():
    log("=" * 78)
    log(f"RECONCILIACIÓN PREMIOS — fecha_sorteo = {FECHA}")
    log(f"Modo: {'🔍 DRY-RUN (sin cambios)' if DRY_RUN else '🔥 APLICANDO CAMBIOS'}")
    log("=" * 78)

    plan = construir_plan()

    log(f"\n[PLAN] {len(plan)} items")
    total = Decimal('0.00')
    usuarios_afectados = set()
    for it in plan:
        if 'error' in it:
            log(f"  ⚠️ #{it['jid']} | ERROR: {it['error']}")
            continue
        log(f"  • #{it['jid']:<6} | {it['cliente'].username:<10} → {it['gestor'].username:<10} | "
            f"{it['sorteo']:<22} | ${it['jugada'].monto:<7} × {it['multiplicador']} = "
            f"${it['monto_premio']:<9} | fp={it['forma_pago'].nombre if it['forma_pago'] else '—'}")
        total += it['monto_premio']
        usuarios_afectados.add(it['cliente'].id)

    log(f"\n  💰 TOTAL: ${total}")
    log(f"  👥 Clientes afectados: {len(usuarios_afectados)}")

    if DRY_RUN:
        log("\n[DRY-RUN] No se aplican cambios. Cambia DRY_RUN=False para ejecutar.")
        # Igual mostramos el estado actual del Cuadre
        log("\n[CuadreDiario actual de los afectados]")
        for uid in usuarios_afectados:
            from django.contrib.auth.models import User
            u = User.objects.get(id=uid)
            c = CuadreDiario.objects.filter(usuario=u, fecha=FECHA).first()
            if c:
                log(f"  {u.username:<12} | cerrado={c.cerrado} | "
                    f"fondo_final['Tarjeta']={c.fondo_final_snapshot.get('Tarjeta')}")
            else:
                log(f"  {u.username:<12} | SIN CuadreDiario para {FECHA}")
        return

    # ─── APLICAR ───
    log("\n[APLICANDO]")
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

    # ─── RECALCULAR CUADRES ───
    log("\n[RECALCULANDO CuadreDiario]")
    from django.contrib.auth.models import User
    for uid in usuarios_afectados:
        u = User.objects.get(id=uid)
        c, info = recalcular_cuadre(u)
        if isinstance(info, tuple) and info[0] == 'actualizado':
            log(f"  ✅ {u.username:<12} | antes['Tarjeta']={info[1].get('Tarjeta')} → después['Tarjeta']={info[2].get('Tarjeta')}")
        else:
            log(f"  ⚠️ {u.username:<12} | {info if isinstance(info, str) else info}")

    # ─── VERIFICAR ───
    fallos = verificar()

    log("\n" + "=" * 78)
    if fallos == 0:
        log("🎉 RECONCILIACIÓN COMPLETADA SIN ERRORES")
    else:
        log(f"⚠️  Reconciliación completada con {fallos} problemas — revisar")
    log("=" * 78)


if __name__ == '__main__':
    main()
