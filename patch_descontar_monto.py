from pathlib import Path
import re

p = Path("/home/LottoBooM/roles/views.py")
src = p.read_text(encoding="utf-8")

if "def descontar_monto(cliente, monto, bonos_disponibles=None, motivo=" in src:
    print("SKIP: ya aplicado")
    raise SystemExit(0)

patron = re.compile(
    r"def descontar_monto\(cliente,\s*monto,\s*bonos_disponibles=None\):.*?(?=\ndef |\Z)",
    re.DOTALL,
)

nuevo = '''def descontar_monto(cliente, monto, bonos_disponibles=None, motivo='', emisor=None):
    """
    Descuenta del fondo (y bonos si hace falta) del cliente.
    Registra MovimientoFondo por cada descuento (auditoria).
    """
    if monto <= 0:
        return True, ""
    with transaction.atomic():
        fondos = list(Fondo.objects.filter(usuario=cliente, activo=True).select_for_update())
        if bonos_disponibles is None:
            bonos = list(Bono.objects.filter(usuario=cliente, estado='activo').select_for_update())
        else:
            bonos = bonos_disponibles
        monto_restante = monto
        for fondo in fondos:
            if monto_restante <= 0:
                break
            if fondo.monto > 0:
                descuento = min(fondo.monto, monto_restante)
                saldo_antes = fondo.monto
                fondo.monto -= descuento
                fondo.save()
                monto_restante -= descuento
                try:
                    MovimientoFondo.objects.create(
                        emisor=emisor,
                        receptor=cliente,
                        forma_pago=fondo.forma_pago,
                        monto=-descuento,
                        tipo='ajuste',
                        estado='confirmado',
                        motivo=motivo or 'Descuento de fondo',
                        saldo_antes=saldo_antes,
                        saldo_despues=fondo.monto,
                        datos_transferencia={'helper': 'descontar_monto'},
                    )
                except Exception:
                    pass
        if monto_restante > 0:
            for bono in bonos:
                if monto_restante <= 0:
                    break
                if bono.saldo_restante > 0:
                    descuento = min(bono.saldo_restante, monto_restante)
                    bono.saldo_restante -= descuento
                    if bono.saldo_restante <= 0:
                        bono.estado = 'agotado'
                    bono.save()
                    monto_restante -= descuento
        if monto_restante > 0:
            return False, f"No hay suficiente saldo para descontar ${monto:.2f}. Faltan ${monto_restante:.2f}."
        return True, ""
'''

src_new, n = patron.subn(nuevo, src, count=1)
if n == 0:
    print("ERROR: no encontre descontar_monto")
    raise SystemExit(1)

p.write_text(src_new, encoding="utf-8")
print("OK descontar_monto con auditoria")

import ast
ast.parse(src_new)
print("OK sintaxis")
