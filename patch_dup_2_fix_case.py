from pathlib import Path
import re

p = Path("/home/LottoBooM/jugadas/views.py")
src = p.read_text(encoding="utf-8")
original = src
cambios = []

# ═══════════════════════════════════════════════════════════════
# FIX 1: Búsqueda de FormaJuego con __iexact (case-insensitive)
# ═══════════════════════════════════════════════════════════════
viejo1 = """                if nombre_tipo not in tipo_a_forma:
                    try:
                        forma = FormaJuego.objects.get(nombre=nombre_tipo)
                    except FormaJuego.DoesNotExist:
                        forma = FormaJuego.objects.create(nombre=nombre_tipo, digitos_esperados=2, activo=True)
                    tipo_a_forma[nombre_tipo] = forma"""

nuevo1 = """                if nombre_tipo not in tipo_a_forma:
                    # Buscar con case-insensitive para evitar crear duplicados 'Fijo'/'fijo'
                    forma = FormaJuego.objects.filter(nombre__iexact=nombre_tipo).first()
                    if not forma:
                        forma = FormaJuego.objects.create(nombre=nombre_tipo.lower(), digitos_esperados=2, activo=True)
                    tipo_a_forma[nombre_tipo] = forma"""

if "__iexact=nombre_tipo" in src and "if nombre_tipo not in tipo_a_forma" in src:
    print("FIX 1: SKIP (ya aplicado)")
elif viejo1 in src:
    src = src.replace(viejo1, nuevo1, 1)
    cambios.append("FIX 1: OK (búsqueda case-insensitive de FormaJuego)")
else:
    cambios.append("FIX 1: ERROR (no encontre el bloque exacto)")

p.write_text(src, encoding="utf-8")
print(cambios[-1])

# Verificar sintaxis
import ast
try:
    ast.parse(src)
    print("OK: sintaxis correcta")
except SyntaxError as e:
    print(f"ERROR: sintaxis linea {e.lineno}: {e.msg}")
    p.write_text(original, encoding="utf-8")
    raise SystemExit(1)

# ═══════════════════════════════════════════════════════════════
# FIX 2: Además, normalizar el numero y monto en el helper
# (por si acaso tiene espacios o formato distinto)
# ═══════════════════════════════════════════════════════════════
patron_helper = re.compile(
    r"(def _jugada_duplicada\(.*?)(\n\ndef |\n\n@|\Z)",
    re.DOTALL,
)
m = patron_helper.search(src)
if m:
    helper_actual = m.group(1)
    if "numero__iexact=num_norm" in helper_actual and "forma_juego__nombre__iexact" not in helper_actual:
        # Mejorar el helper: buscar por nombre de forma_juego también (por si hay IDs duplicados)
        helper_nuevo = '''def _jugada_duplicada(cliente_id, sorteo_id, forma_juego_id, forma_pago_id, numero, monto, fecha_sorteo):
    """Devuelve True si ya existe una jugada identica en BD (no cancelada).
    Compara por IDs, tolerando case-insensitive en numero."""
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
    ).exists()'''
        src = src[:m.start(1)] + helper_nuevo + src[m.end(1):]
        p.write_text(src, encoding="utf-8")
        cambios.append("FIX 2: OK (helper normalizado)")
    else:
        cambios.append("FIX 2: SKIP")
else:
    cambios.append("FIX 2: WARN (no matcheo helper)")

print("\n═══ REPORTE FINAL ═══")
for c in cambios:
    print(f"  {c}")
