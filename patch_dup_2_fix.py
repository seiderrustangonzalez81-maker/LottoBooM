from pathlib import Path
import re

p = Path("/home/LottoBooM/jugadas/views.py")
src = p.read_text(encoding="utf-8")
original = src

# ═══════════════════════════════════════════════════════════════
# PASO 1: Extraer el helper de su ubicación incorrecta
# ═══════════════════════════════════════════════════════════════
patron_helper = re.compile(
    r"\n# ═+\n# Helper · Detecta si una jugada ya existe en BD.*?(?=\n@login_required|\ndef _guardar_apuesta_impl|\Z)",
    re.DOTALL,
)

m = patron_helper.search(src)
if not m:
    # Intentar variante
    patron_helper = re.compile(
        r"\n# ═+\n# Helper · Detecta.*?\n(def _jugada_duplicada\(.*?\n    return Jugada\.objects\.filter\(.*?\n\s*\)\.exists\(\)\n)",
        re.DOTALL,
    )
    m = patron_helper.search(src)

if not m:
    print("ERROR: no encontre el helper para mover")
    print("Buscando '_jugada_duplicada'...")
    idx = src.find("def _jugada_duplicada")
    if idx > 0:
        print(repr(src[max(0, idx-200):idx+600]))
    raise SystemExit(1)

helper_block = m.group(0)
print(f"PASO 1: helper encontrado, tamaño={len(helper_block)}")

# ═══════════════════════════════════════════════════════════════
# PASO 2: Eliminarlo de su posición actual
# ═══════════════════════════════════════════════════════════════
src = src[:m.start()] + "\n" + src[m.end():]
print("PASO 2: helper eliminado de su posición incorrecta")

# ═══════════════════════════════════════════════════════════════
# PASO 3: Insertarlo justo después del último logger = logging...
# ═══════════════════════════════════════════════════════════════
patron_logger = re.compile(
    r"(logger\s*=\s*logging\.getLogger\(__name__\)\s*\n)",
    re.MULTILINE,
)
m_logger = patron_logger.search(src)
if not m_logger:
    print("ERROR: no encontre 'logger = logging.getLogger'")
    raise SystemExit(1)

# Reconstruir el helper limpio (sin el leading \n extra)
helper_limpio = helper_block.strip() + "\n\n"
src = src[:m_logger.end()] + "\n" + helper_limpio + src[m_logger.end():]
print("PASO 3: helper insertado después del logger")

p.write_text(src, encoding="utf-8")

# Verificar sintaxis
import ast
try:
    ast.parse(src)
    print("OK: sintaxis correcta")
except SyntaxError as e:
    print(f"ERROR: sintaxis linea {e.lineno}: {e.msg}")
    p.write_text(original, encoding="utf-8")
    print("REVERTIDO")
    raise SystemExit(1)

# ═══════════════════════════════════════════════════════════════
# PASO 4: Verificar que _guardar_apuesta_impl sigue con decoradores
# ═══════════════════════════════════════════════════════════════
idx_impl = src.find("def _guardar_apuesta_impl(request):")
if idx_impl > 0:
    antes = src[max(0, idx_impl-200):idx_impl]
    if "@login_required" in antes and "@require_POST" in antes:
        print("OK: _guardar_apuesta_impl conserva sus decoradores")
    else:
        print("WARN: revisar decoradores de _guardar_apuesta_impl")
        print(repr(antes[-100:]))

print("\n✅ Fix aplicado")
print(f"_jugada_duplicada: {src.count('def _jugada_duplicada')}")
