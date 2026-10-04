from pathlib import Path
import re
import sys

# ═══════════════════════════════════════════════════════════════
# PASO 1: Añadir helper global _jugada_duplicada
# ═══════════════════════════════════════════════════════════════
p = Path("/home/LottoBooM/jugadas/views.py")
src = p.read_text(encoding="utf-8")
original = src

if "def _jugada_duplicada(" in src:
    print("PASO 1: SKIP (helper ya existe)")
else:
    helper = '''

# ═══════════════════════════════════════════════════════════════
# Helper · Detecta si una jugada ya existe en BD
# Campos que se comparan: cliente + sorteo + fecha + forma_juego + forma_pago + numero + monto
# ═══════════════════════════════════════════════════════════════
def _jugada_duplicada(cliente_id, sorteo_id, forma_juego_id, forma_pago_id, numero, monto, fecha_sorteo):
    """Devuelve True si ya existe una jugada identica en BD (no cancelada)."""
    from decimal import Decimal, InvalidOperation
    try:
        monto_dec = Decimal(str(monto)).quantize(Decimal('0.01'))
    except (InvalidOperation, ValueError, TypeError):
        return False

    num_norm = str(numero or '').strip().upper()
    if not num_norm:
        return False

    return Jugada.objects.filter(
        usuario_id=cliente_id,
        sorteo_id=sorteo_id,
        fecha_sorteo=fecha_sorteo,
        forma_juego_id=forma_juego_id,
        forma_pago_id=forma_pago_id,
        numero__iexact=num_norm,
        monto=monto_dec,
        estado__in=['confirmada', 'pendiente'],
    ).exists()

'''
    # Insertar después de la última función de utilidades (antes de guardar_apuesta o similar)
    # Buscar un anchor confiable: "def guardar_apuesta(request):" del wrapper nuevo
    anchor = "def _guardar_apuesta_impl(request):"
    if anchor in src:
        idx = src.find(anchor)
        src = src[:idx] + helper + "\n" + src[idx:]
        print("PASO 1: OK (helper insertado antes de _guardar_apuesta_impl)")
    else:
        # Fallback: al final del archivo
        src = src + helper
        print("PASO 1: OK (helper insertado al final)")

p.write_text(src, encoding="utf-8")

import ast
try:
    ast.parse(src)
    print("OK: sintaxis correcta")
except SyntaxError as e:
    print(f"ERROR: sintaxis linea {e.lineno}: {e.msg}")
    p.write_text(original, encoding="utf-8")
    sys.exit(1)

# ═══════════════════════════════════════════════════════════════
# PASO 2: Insertar check en items_normales
# ═══════════════════════════════════════════════════════════════
viejo_norm = """                        monto_final = disponible

                    if jugada_id and modo_edicion not in ('duplicar', 'editar_boleta'):"""

nuevo_norm = """                        monto_final = disponible

                    # ═══ Check duplicados ═══
                    if _jugada_duplicada(cliente.id, sorteo.id, forma_juego.id, forma_pago.id, numero, monto_final, fecha_apuesta):
                        advertencias.append(
                            f'⚠️ {numero} ({forma_juego.nombre}) ${monto_final} en {sorteo.nombre} ya existe para este cliente. Se omitió.'
                        )
                        continue

                    if jugada_id and modo_edicion not in ('duplicar', 'editar_boleta'):"""

if "# ═══ Check duplicados ═══" in src:
    print("PASO 2: SKIP (check ya en items_normales)")
elif viejo_norm in src:
    src = src.replace(viejo_norm, nuevo_norm, 1)
    p.write_text(src, encoding="utf-8")
    print("PASO 2: OK (check en items_normales)")
else:
    print("PASO 2: WARN (no matcheo items_normales — buscar alternativa)")
    # Alternativa: buscar solo por el "if jugada_id and modo_edicion" que sigue al primer monto_final
    patron_alt = re.compile(
        r"(\n\s+monto_final = disponible\s*\n\s*\n)(\s+if jugada_id and modo_edicion not in \('duplicar', 'editar_boleta'\):)",
        re.MULTILINE,
    )
    m = patron_alt.search(src)
    if m:
        indent = "                    "
        check = f"{indent}# ═══ Check duplicados ═══\n{indent}if _jugada_duplicada(cliente.id, sorteo.id, forma_juego.id, forma_pago.id, numero, monto_final, fecha_apuesta):\n{indent}    advertencias.append(\n{indent}        f'⚠️ {{numero}} ({{forma_juego.nombre}}) ${{monto_final}} en {{sorteo.nombre}} ya existe. Se omitió.'\n{indent}    )\n{indent}    continue\n\n"
        src = src[:m.end(1)] + check + src[m.end(1):]
        p.write_text(src, encoding="utf-8")
        print("PASO 2: OK (via regex alternativa)")
    else:
        print("PASO 2: ERROR — no pude insertar el check")

# ═══════════════════════════════════════════════════════════════
# PASO 3: Insertar check en items_super (Superparlet)
# ═══════════════════════════════════════════════════════════════
viejo_sup = """                        monto_final = disponible

                    if jugada_id and modo_edicion not in ('duplicar', 'editar_boleta'):
                        try:
                            jugada = Jugada.objects.get(id=jugada_id)
                            jugada.usuario = cliente
                            jugada.destinatario = destinatario
                            jugada.comercial = usuario if usuario != cliente else None
                            jugada.forma_juego = forma_juego
                            jugada.sorteo = sorteo_principal"""

nuevo_sup = """                        monto_final = disponible

                    # ═══ Check duplicados (superparlet) ═══
                    if _jugada_duplicada(cliente.id, sorteo_principal.id, forma_juego.id, forma_pago.id, numero, monto_final, fecha_apuesta):
                        advertencias.append(
                            f'⚠️ {numero} (Superparlet) ${monto_final} ya existe para este cliente. Se omitió.'
                        )
                        continue

                    if jugada_id and modo_edicion not in ('duplicar', 'editar_boleta'):
                        try:
                            jugada = Jugada.objects.get(id=jugada_id)
                            jugada.usuario = cliente
                            jugada.destinatario = destinatario
                            jugada.comercial = usuario if usuario != cliente else None
                            jugada.forma_juego = forma_juego
                            jugada.sorteo = sorteo_principal"""

if "# ═══ Check duplicados (superparlet) ═══" in src:
    print("PASO 3: SKIP (check ya en items_super)")
elif viejo_sup in src:
    src = src.replace(viejo_sup, nuevo_sup, 1)
    p.write_text(src, encoding="utf-8")
    print("PASO 3: OK (check en items_super)")
else:
    print("PASO 3: WARN — no encontre el bloque de Superparlet exacto")
    print("         (verificar manualmente)")

# ═══════════════════════════════════════════════════════════════
# PASO 4: Mejorar mensaje cuando TODAS las jugadas fueron descartadas
# ═══════════════════════════════════════════════════════════════
viejo_msg = """            if not jugadas_creadas:
                return JsonResponse({
                    'success': False,
                    'message': 'No se pudo crear ninguna jugada (todos los números están agotados o sin pool).',
                    'advertencias': advertencias
                }, status=400)"""

nuevo_msg = """            if not jugadas_creadas:
                # Determinar la causa principal
                hay_duplicados = any('ya existe' in adv for adv in advertencias)
                if hay_duplicados:
                    msg = '⚠️ Todas las jugadas ya existen en la base de datos para este cliente/sorteo/fecha. Modifica los números, montos o forma de pago.'
                else:
                    msg = 'No se pudo crear ninguna jugada (todos los números están agotados o sin pool).'
                return JsonResponse({
                    'success': False,
                    'message': msg,
                    'advertencias': advertencias
                }, status=400)"""

if "hay_duplicados = any('ya existe' in adv" in src:
    print("PASO 4: SKIP")
elif viejo_msg in src:
    src = src.replace(viejo_msg, nuevo_msg, 1)
    p.write_text(src, encoding="utf-8")
    print("PASO 4: OK (mensaje mejorado para duplicados)")
else:
    print("PASO 4: WARN — no encontre el bloque 'if not jugadas_creadas'")

# ═══════════════════════════════════════════════════════════════
# VERIFICACIÓN FINAL
# ═══════════════════════════════════════════════════════════════
try:
    ast.parse(src)
    print("\nOK: sintaxis final correcta")
except SyntaxError as e:
    print(f"\nERROR final: {e.lineno}: {e.msg}")
    p.write_text(original, encoding="utf-8")
    print("REVERTIDO al estado original")
    sys.exit(1)

print(f"_jugada_duplicada: {src.count('_jugada_duplicada')} ocurrencias")
print(f"Check duplicados normales: {src.count('# ═══ Check duplicados ═══')}")
print(f"Check duplicados super: {src.count('# ═══ Check duplicados (superparlet) ═══')}")
