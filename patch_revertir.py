from pathlib import Path
import re

p = Path("/home/LottoBooM/resultados/views.py")
src = p.read_text(encoding="utf-8")

viejo = """                    if f_ant:
                        f_ant.monto -= p_ant.monto_premio
                        f_ant.save(update_fields=['monto', 'actualizado_en'])"""

nuevo = """                    if f_ant:
                        saldo_ant_r = f_ant.monto
                        f_ant.monto -= p_ant.monto_premio
                        f_ant.save(update_fields=['monto', 'actualizado_en'])
                        try:
                            MovimientoFondo.objects.create(
                                emisor=None,
                                receptor=p_ant.jugada.usuario,
                                forma_pago=fp_ant,
                                monto=-p_ant.monto_premio,
                                tipo='ajuste',
                                estado='confirmado',
                                motivo='Reversion premio #' + str(p_ant.id),
                                saldo_antes=saldo_ant_r,
                                saldo_despues=f_ant.monto,
                                datos_transferencia={
                                    'premio_id': p_ant.id,
                                    'resultado_id': resultado.id,
                                    'reversion': True,
                                },
                            )
                        except Exception:
                            pass"""

if "Reversion premio #" in src:
    print("SKIP: ya aplicado")
    raise SystemExit(0)

if viejo not in src:
    print("ERROR: no encontre el bloque exacto")
    raise SystemExit(1)

src_new = src.replace(viejo, nuevo, 1)
p.write_text(src_new, encoding="utf-8")
print("OK resultados/views.py revertir premio con auditoria")

import ast
ast.parse(src_new)
print("OK sintaxis")
