from pathlib import Path
import re

p = Path("/home/LottoBooM/roles/utils.py")
src = p.read_text(encoding="utf-8")

patron = re.compile(
    r"def _aplicar_ingreso_a_fondo\(cliente, gestor, forma_pago, monto\):.*?(?=\n# ==|\n\ndef |\Z)",
    re.DOTALL,
)

nuevo = '''def _aplicar_ingreso_a_fondo(cliente, gestor, forma_pago, monto):
    """
    Aplica un ingreso (recarga/premio) al cliente:
    1. Si hay Postpago con saldo < 0 para (gestor, forma_pago), paga la deuda.
    2. El resto va al Fondo.
    3. Registra MovimientoFondo de recarga + pago_deuda (si aplica).
    Devuelve (monto_al_fondo, monto_pagado_postpago).
    """
    from decimal import Decimal
    from django.db import transaction
    from roles.models import Postpago, Fondo, MovimientoFondo

    monto = Decimal(str(monto))
    if monto <= 0:
        return Decimal('0.00'), Decimal('0.00')

    with transaction.atomic():
        fondo_pre = Fondo.objects.filter(
            usuario=cliente, forma_pago=forma_pago, activo=True
        ).first()
        saldo_antes_fondo = fondo_pre.monto if fondo_pre else Decimal('0.00')

        pagado = Decimal('0.00')
        pp = Postpago.objects.select_for_update().filter(
            cliente=cliente, gestor=gestor, forma_pago=forma_pago,
        ).first()
        if pp and pp.saldo < 0:
            deuda = -pp.saldo
            pagado = min(monto, deuda)
            pp.saldo += pagado
            if pp.saldo == 0:
                pp.activo = False
            pp.save(update_fields=['saldo', 'activo', 'actualizado_en'])
            monto -= pagado
            try:
                MovimientoFondo.objects.create(
                    emisor=gestor, receptor=cliente, forma_pago=forma_pago,
                    monto=pagado, tipo='pago_deuda', estado='confirmado',
                    motivo='Abono a deuda pendiente con ' + gestor.username,
                    nota='Abono desde ingreso',
                    datos_transferencia={
                        'postpago_id': pp.id,
                        'gestor': gestor.username,
                        'deuda_restante': float(-pp.saldo) if pp.saldo < 0 else 0.0,
                    },
                )
            except Exception:
                pass

        al_fondo = monto
        if al_fondo > 0:
            fondo, _ = Fondo.objects.select_for_update().get_or_create(
                usuario=cliente, forma_pago=forma_pago,
                defaults={'monto': Decimal('0.00'), 'activo': True, 'asignado_por': gestor},
            )
            fondo.monto += al_fondo
            fondo.activo = True
            if not fondo.asignado_por_id and gestor:
                fondo.asignado_por = gestor
            fondo.save(update_fields=['monto', 'activo', 'asignado_por'] if fondo.asignado_por_id else ['monto', 'activo'])
            try:
                MovimientoFondo.objects.create(
                    emisor=gestor, receptor=cliente, forma_pago=forma_pago,
                    monto=al_fondo, tipo='recarga', estado='confirmado',
                    motivo='Ingreso aplicado a fondo por ' + gestor.username,
                    nota='Al fondo: ' + str(al_fondo),
                    saldo_antes=saldo_antes_fondo,
                    saldo_despues=fondo.monto,
                    datos_transferencia={
                        'gestor': gestor.username,
                        'monto_bruto': float(al_fondo + pagado),
                        'postpago_descontado': float(pagado),
                    },
                )
            except Exception:
                pass

        return al_fondo, pagado
'''

src_new, n = patron.subn(nuevo, src, count=1)
if n == 0:
    print("ERROR: no encontre la funcion")
    raise SystemExit(1)

p.write_text(src_new, encoding="utf-8")
print("OK roles/utils.py _aplicar_ingreso_a_fondo con auditoria")

import ast
ast.parse(src_new)
print("OK sintaxis")
