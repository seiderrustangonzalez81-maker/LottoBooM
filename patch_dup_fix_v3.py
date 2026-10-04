import re
from pathlib import Path

p = Path("/home/LottoBooM/jugadas/views.py")
src = p.read_text(encoding="utf-8")
original = src

# Reemplazar el helper _boleta_duplicada por la versión correcta
patron = re.compile(
    r"def _boleta_duplicada\(cliente_id, forma_pago_id, fecha_sorteo, items\):.*?(?=\n# ═+|\n@login_required|\ndef _guardar_apuesta_impl)",
    re.DOTALL,
)

nuevo_helper = '''def _boleta_duplicada(cliente_id, forma_pago_id, fecha_sorteo, items):
    """
    Detecta si los items forman una boleta IDENTICA a una ya existente.
    Compara por BOLETA (no mezcla jugadas de boletas distintas).
    Firma = (cliente, sorteo, fecha, FP, sorted[(numero, forma_juego, monto)])
    """
    from decimal import Decimal, InvalidOperation
    from collections import defaultdict

    if not items or not cliente_id or not forma_pago_id or not fecha_sorteo:
        return []

    # ─── Agrupar items nuevos por sorteo_id ───
    por_sorteo = defaultdict(list)
    for it in items:
        sid = it.get('sorteo_id')
        if not sid:
            continue
        try:
            num_norm = str(it.get('numero', '')).strip().upper()
            tipo_norm = str(it.get('tipo', '')).strip().lower()
            monto_dec = Decimal(str(it.get('monto', 0))).quantize(Decimal('0.01'))
        except (InvalidOperation, ValueError, TypeError):
            continue
        if not num_norm:
            continue
        por_sorteo[sid].append((num_norm, tipo_norm, str(monto_dec)))

    # ─── Para cada sorteo, comparar contra CADA boleta existente ───
    duplicados = []
    for sid, firma_nueva in por_sorteo.items():
        firma_nueva_set = set(firma_nueva)
        if not firma_nueva_set:
            continue

        # Traer boletas del cliente para ese sorteo/fecha/FP
        boletas = Boleta.objects.filter(
            usuario_id=cliente_id,
            fecha_sorteo=fecha_sorteo,
            forma_pago_id=forma_pago_id,
            jugadas__sorteo_id=sid,
            jugadas__estado__in=['confirmada', 'pendiente'],
        ).distinct()

        for b in boletas:
            # Jugadas SOLO de esta boleta y este sorteo
            jugadas = b.jugadas.filter(
                sorteo_id=sid,
                estado__in=['confirmada', 'pendiente'],
            ).values('numero', 'forma_juego__nombre', 'monto')

            firma_existente = set()
            for j in jugadas:
                num_norm = str(j['numero'] or '').strip().upper()
                tipo_norm = str(j['forma_juego__nombre'] or '').strip().lower()
                try:
                    monto_norm = str(Decimal(str(j['monto'])).quantize(Decimal('0.01')))
                except (InvalidOperation, ValueError, TypeError):
                    monto_norm = str(j['monto'])
                firma_existente.add((num_norm, tipo_norm, monto_norm))

            if firma_nueva_set == firma_existente:
                duplicados.append({
                    'sorteo_id': sid,
                    'boleta_id': b.id,
                    'boleta_ref': b.referencia,
                    'cantidad': len(firma_nueva_set),
                })
                break  # con 1 match es suficiente

    return duplicados
'''

src_new, n = patron.subn(nuevo_helper + "\n", src, count=1)
if n == 0:
    print("ERROR: no pude reemplazar el helper")
    raise SystemExit(1)

src = src_new
p.write_text(src, encoding="utf-8")
print("OK: helper _boleta_duplicada refactorizado (agrupa por boleta)")

import ast
try:
    ast.parse(src)
    print("OK: sintaxis correcta")
except SyntaxError as e:
    print(f"ERROR: {e}")
    p.write_text(original, encoding="utf-8")
    raise SystemExit(1)
