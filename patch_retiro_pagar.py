from pathlib import Path
import re

p = Path("/home/LottoBooM/roles/models.py")
src = p.read_text(encoding="utf-8")

if "'motivo_tipo': self.motivo_tipo" in src:
    print("SKIP: ya aplicado")
    raise SystemExit(0)

# Buscar el bloque exacto dentro de SolicitudRetiro.pagar()
viejo = """        fondo.monto -= monto
        fondo.save(update_fields=['monto', 'actualizado_en'])

        MovimientoFondo.objects.create(
            emisor=self.cliente,
            receptor=self.gestor,
            forma_pago=self.forma_pago,
            monto=monto,
            tipo='retiro',
            estado='confirmado',
            datos_transferencia={
                'solicitud_retiro_id': self.id,
                'via_pago_id': self.via_pago.id if self.via_pago else None,
                'datos_via': self.datos_via_cliente or {},
            },
            nota=f"Retiro por solicitud #{self.id}"
        )"""

nuevo = """        saldo_antes = fondo.monto
        fondo.monto -= monto
        fondo.save(update_fields=['monto', 'actualizado_en'])

        # Motivo legible para el historial
        motivo_legible = self.get_motivo_tipo_display()
        if self.motivo_tipo == 'otro' and self.motivo_detalle:
            motivo_legible = self.motivo_detalle

        MovimientoFondo.objects.create(
            emisor=self.cliente,
            receptor=self.gestor,
            forma_pago=self.forma_pago,
            monto=monto,
            tipo='retiro',
            estado='confirmado',
            motivo=motivo_legible[:200],
            saldo_antes=saldo_antes,
            saldo_despues=fondo.monto,
            datos_transferencia={
                'solicitud_retiro_id': self.id,
                'via_pago_id': self.via_pago.id if self.via_pago else None,
                'datos_via': self.datos_via_cliente or {},
                'motivo_tipo': self.motivo_tipo,
                'motivo_detalle': self.motivo_detalle,
            },
            nota=f"Retiro por solicitud #{self.id}"
        )"""

if viejo not in src:
    print("ERROR: no encontre el bloque exacto en pagar()")
    print("Corre: grep -n 'def pagar' -A 50 roles/models.py | head -70")
    raise SystemExit(1)

src_new = src.replace(viejo, nuevo, 1)
p.write_text(src_new, encoding="utf-8")
print("OK modelo pagar() con motivo + saldos")

import ast
ast.parse(src_new)
print("OK sintaxis")
