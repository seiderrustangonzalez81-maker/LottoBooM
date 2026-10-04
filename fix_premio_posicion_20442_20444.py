"""
FIX_POSICION_V1_CORRECCION
Revierte los premios mal pagados de las jugadas #20442 y #20444
(Georgia 12:30 PM 2026-10-04, boleta BOL-20261004-0698).

Ejecutar primero con DRY_RUN=True para ver qué haría.
"""
DRY_RUN = True   # ← cambiar a False para aplicar

from decimal import Decimal
from django.db import transaction

from jugadas.models import Jugada, Boleta
from resultados.models import Premio
from roles.models import Fondo, MovimientoFondo

JUGADAS_A_REVERTIR = [20442, 20444]
BOLETA_ID = 481


def run():
    print(f"{'='*60}")
    print(f"  MODO: {'DRY-RUN (no cambia nada)' if DRY_RUN else '⚠️  APLICAR CAMBIOS'}")
    print(f"{'='*60}\n")

    with transaction.atomic():
        total_reverso = Decimal('0.00')

        for jid in JUGADAS_A_REVERTIR:
            j = Jugada.objects.select_for_update().filter(id=jid).select_related(
                'usuario', 'destinatario', 'forma_pago', 'sorteo'
            ).first()
            if not j:
                print(f"  #{jid}: NO EXISTE — skip")
                continue

            premio = Premio.objects.select_for_update().filter(
                jugada=j, estado='pagado'
            ).first()
            if not premio:
                print(f"  #{jid}: sin premio pagado — skip")
                continue

            monto_rev = premio.monto_premio
            cliente = j.usuario
            gestor = j.destinatario or cliente
            fp = j.forma_pago

            print(f"  #{jid}: cliente={cliente.username} fp={fp.nombre if fp else '?'}")
            print(f"        premio #{premio.id} ${monto_rev} → a revertir")

            # 1. Fondo: restar lo acreditado de más
            fondo = Fondo.objects.select_for_update().filter(
                usuario=cliente, forma_pago=fp, asignado_por=gestor, activo=True
            ).first() if fp else None

            if not fondo:
                print(f"        ⚠️  Fondo no encontrado — no se puede revertir del fondo")
            else:
                saldo_antes = fondo.monto
                fondo.monto = fondo.monto - monto_rev
                saldo_despues = fondo.monto
                print(f"        Fondo: ${saldo_antes} → ${saldo_despues}")
                if not DRY_RUN:
                    fondo.save(update_fields=['monto'])
                    MovimientoFondo.objects.create(
                        emisor=cliente,
                        receptor=gestor,
                        forma_pago=fp,
                        monto=-monto_rev,
                        tipo='ajuste',
                        estado='confirmado',
                        motivo=f"FIX_POSICION_V1 reverso jugada #{jid}",
                        datos_transferencia={
                            'jugada_id': jid,
                            'premio_id': premio.id,
                            'reverso_bug_posicion': True,
                        },
                        nota=f"Reverso por bug de posición (número {j.numero} en {j.sorteo.nombre})",
                        saldo_antes=saldo_antes,
                        saldo_despues=saldo_despues,
                    )

            # 2. Premio → anulado
            print(f"        Premio #{premio.id}: pagado → anulado")
            if not DRY_RUN:
                premio.estado = 'anulado'
                premio.cobrado = False
                premio.comentario = 'FIX_POSICION_V1: reverso por bug de posición (89 no salió en esta posición)'
                premio.save(update_fields=['estado', 'cobrado', 'comentario'])

            # 3. Jugada → perdedora
            print(f"        Jugada #{jid}: ganadora → perdedora, monto_premio → None")
            if not DRY_RUN:
                j.estado = 'perdedora'
                j.monto_premio = None
                j.save(update_fields=['estado', 'monto_premio'])

            total_reverso += monto_rev
            print()

        # 4. Recalcular boleta
        b = Boleta.objects.select_for_update().filter(id=BOLETA_ID).first()
        if b:
            print(f"  Boleta #{b.id}: premios_total antes=${b.premios_total}")
            if not DRY_RUN:
                b.recalcular_totales()
                b.refresh_from_db()
            print(f"  Boleta #{b.id}: premios_total después=${b.premios_total if not DRY_RUN else b.premios_total - total_reverso}")

        print(f"\n  TOTAL a revertir: ${total_reverso}")

        if DRY_RUN:
            print("\n  [DRY-RUN] Nada fue modificado. Cambia DRY_RUN=False y re-ejecuta.")
            transaction.set_rollback(True)


if __name__ == '__main__':
    run()
