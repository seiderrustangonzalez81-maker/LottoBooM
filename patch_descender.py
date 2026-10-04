from pathlib import Path
import re

p = Path("/home/LottoBooM/roles/views.py")
src = p.read_text(encoding="utf-8")

patron = re.compile(
    r"def ajustar_fondos_al_descender\(usuario\):.*?(?=\n\ndef |\Z)",
    re.DOTALL,
)

nuevo = '''def ajustar_fondos_al_descender(usuario):
    """Convierte los fondos de un usuario a negativos (modulares) al ser descendido a cliente.
    Registra MovimientoFondo por cada fondo ajustado."""
    fondos = Fondo.objects.filter(usuario=usuario, activo=True)
    for fondo in fondos:
        if fondo.monto > 0:
            saldo_antes = fondo.monto
            fondo.monto = -fondo.monto
            fondo.save()
            delta = fondo.monto - saldo_antes
            try:
                MovimientoFondo.objects.create(
                    emisor=None,
                    receptor=usuario,
                    forma_pago=fondo.forma_pago,
                    monto=delta,
                    tipo='ajuste',
                    estado='confirmado',
                    motivo='Descenso de gestor a cliente - fondo convertido a negativo',
                    nota='Ajuste por cambio de rol',
                    saldo_antes=saldo_antes,
                    saldo_despues=fondo.monto,
                    datos_transferencia={'tipo_cambio': 'descenso', 'ajuste_rol': True},
                )
            except Exception:
                pass
    crear_notificacion(
        usuario=usuario, tipo='info',
        mensaje='Has sido descendido a cliente. Tus fondos son modulares (negativos) y se anularan con recargas.',
        datos={'tipo_cambio': 'descenso', 'fecha': timezone.now().isoformat(), 'url_detalle': '/usuarios/mis-fondos/'},
        prioridad='alta', categoria='sistema'
    )
'''

src_new, n = patron.subn(nuevo, src, count=1)
if n == 0:
    print("ERROR: no encontre la funcion")
    raise SystemExit(1)

p.write_text(src_new, encoding="utf-8")
print("OK roles/views.py ajustar_fondos_al_descender con auditoria")

import ast
ast.parse(src_new)
print("OK sintaxis")

