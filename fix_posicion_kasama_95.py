"""
Reversa el premio #95 (Kasama, jugada #8307, Leidsa 8:55 PM 2026-09-28).
El 33 salio en pos 2, la apuesta era a pos 1 → premio falso.
"""
DRY_RUN = False

from decimal import Decimal
from django.db import transaction

from jugadas.models import Jugada, Boleta
from resultados.models import Premio
from roles.models import Fondo, MovimientoFondo

JUGADA_ID = 8307
PREMIO_ID = 95
BOLETA_ID = 221

def run():
    print("=" * 60)
    print("  MODO:", "DRY-RUN (no cambia nada)" if DRY_RUN else "APLICAR")
    print("=" * 60)

    with transaction.atomic():
        j = Jugada.objects.select_for_update().filter(id=JUGADA_ID).select_related(
            'usuario', 'destinatario', 'forma_pago', 'sorteo'
        ).first()
        if not j:
            print(f"  Jugada #{JUGADA_ID}: NO EXISTE"); return

        premio = Premio.objects.select_for_update().filter(id=PREMIO_ID).first()
        if not premio:
            print(f"  Premio #{PREMIO_ID}: NO EXISTE"); return
        if premio.estado != 'pagado':
            print(f"  Premio #{PREMIO_ID}: estado={premio.estado} (no pagado) — skip"); return

        monto_rev = premio.monto_premio
        cliente = j.usuario
        gestor = j.destinatario or cliente
        fp = j.forma_pago

        print(f"\n  Jugada #{j.id}: {cliente.username} -> {gestor.username if gestor else '?'}")
        print(f"    forma_pago: {fp.nombre if fp else '?'}")
        print(f"    numero='{j.numero}' · monto=${j.monto}")
        print(f"    premio #{premio.id} ${monto_rev} -> a revertir")

        fondo = None
        if fp:
            fondo = Fondo.objects.select_for_update().filter(
                usuario=cliente, forma_pago=fp, asignado_por=gestor, activo=True
            ).first()

        if fondo:
            antes = fondo.monto
            despues = antes - monto_rev
            print(f"    Fondo: ${antes} -> ${despues}")
            if despues < 0:
                print(f"    ⚠️  El fondo queda en NEGATIVO (${despues}) — Kasama ya gasto parte del premio falso")

            if not DRY_RUN:
                fondo.monto = despues
                fondo.save(update_fields=['monto'])
                MovimientoFondo.objects.create(
                    emisor=cliente, receptor=gestor, forma_pago=fp,
                    monto=-monto_rev, tipo='ajuste', estado='confirmado',
                    motivo=f"FIX_POSICION_V1 reverso jugada #{j.id}",
                    datos_transferencia={
                        'jugada_id': j.id, 'premio_id': premio.id,
                        'reverso_bug_posicion': True,
                    },
                    nota=f"Reverso por bug de posicion ({j.numero} en {j.sorteo.nombre})",
                    saldo_antes=antes, saldo_despues=despues,
                )
        else:
            print(f"    ⚠️  Fondo NO encontrado — solo se corrige premio/jugada")

        if not DRY_RUN:
            premio.estado = 'anulado'
            premio.cobrado = False
            premio.comentario = 'FIX_POSICION_V1: 33 salio en pos 2, la apuesta era pos 1'
            premio.save(update_fields=['estado', 'cobrado', 'comentario'])

            j.estado = 'perdedora'
            j.monto_premio = None
            j.save(update_fields=['estado', 'monto_premio'])

        b = Boleta.objects.select_for_update().filter(id=BOLETA_ID).first()
        if b:
            print(f"\n  Boleta #{b.id}: premios_total antes=${b.premios_total}")
            if not DRY_RUN:
                b.recalcular_totales()
                b.refresh_from_db()
                print(f"  Boleta #{b.id}: premios_total despues=${b.premios_total}")

        print(f"\n  TOTAL REVERTIDO: ${monto_rev}")

        if DRY_RUN:
            print("\n  [DRY-RUN] Nada modificado.")
            transaction.set_rollback(True)

run()

