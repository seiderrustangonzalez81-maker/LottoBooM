"""
Correccion manual — reversa los premios mal pagados de posicion.
Jugadas #20442 y #20444 (Georgia 12:30 PM 2026-10-04, boleta #481).
"""
DRY_RUN = False

from decimal import Decimal
from django.db import transaction

from jugadas.models import Jugada, Boleta
from resultados.models import Premio
from roles.models import Fondo, MovimientoFondo

JUGADAS = [20442, 20444]
BOLETA_ID = 481

def run():
    print("=" * 60)
    print("  MODO:", "DRY-RUN (no cambia nada)" if DRY_RUN else "APLICAR")
    print("=" * 60)

    with transaction.atomic():
        total = Decimal('0.00')

        for jid in JUGADAS:
            j = Jugada.objects.select_for_update().filter(id=jid).select_related(
                'usuario', 'destinatario', 'forma_pago', 'sorteo'
            ).first()
            if not j:
                print(f"  #{jid}: NO EXISTE"); continue

            premio = Premio.objects.select_for_update().filter(
                jugada=j, estado='pagado'
            ).first()
            if not premio:
                print(f"  #{jid}: sin premio pagado"); continue

            monto_rev = premio.monto_premio
            cliente = j.usuario
            gestor = j.destinatario or cliente
            fp = j.forma_pago

            print(f"\n  Jugada #{jid}: {cliente.username} -> {gestor.username if gestor else '?'}")
            print(f"    forma_pago: {fp.nombre if fp else '?'}")
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
                if not DRY_RUN:
                    fondo.monto = despues
                    fondo.save(update_fields=['monto'])
                    MovimientoFondo.objects.create(
                        emisor=cliente, receptor=gestor, forma_pago=fp,
                        monto=-monto_rev, tipo='ajuste', estado='confirmado',
                        motivo=f"FIX_POSICION_V1 reverso jugada #{jid}",
                        datos_transferencia={
                            'jugada_id': jid, 'premio_id': premio.id,
                            'reverso_bug_posicion': True,
                        },
                        nota=f"Reverso por bug de posicion ({j.numero} en {j.sorteo.nombre})",
                        saldo_antes=antes, saldo_despues=despues,
                    )
            else:
                print(f"    AVISO: Fondo NO encontrado — solo se corrige premio/jugada")

            if not DRY_RUN:
                premio.estado = 'anulado'
                premio.cobrado = False
                premio.comentario = 'FIX_POSICION_V1: 89 no salio en esta posicion'
                premio.save(update_fields=['estado', 'cobrado', 'comentario'])

                j.estado = 'perdedora'
                j.monto_premio = None
                j.save(update_fields=['estado', 'monto_premio'])

            total += monto_rev

        b = Boleta.objects.select_for_update().filter(id=BOLETA_ID).first()
        if b:
            print(f"\n  Boleta #{b.id}: premios_total antes=${b.premios_total}")
            if not DRY_RUN:
                b.recalcular_totales()
                b.refresh_from_db()
                print(f"  Boleta #{b.id}: premios_total despues=${b.premios_total}")

        print(f"\n  TOTAL REVERTIDO: ${total}")

        if DRY_RUN:
            print("\n  [DRY-RUN] Nada modificado.")
            transaction.set_rollback(True)

run()
