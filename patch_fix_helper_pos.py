from pathlib import Path
import re
import ast

p = Path("/home/LottoBooM/jugadas/views.py")
src = p.read_text(encoding="utf-8")

# Ver el bloque actual
idx = src.find("def _dentro_ventana_banco")
print("Bloque actual:")
print(repr(src[max(0, idx-200):idx+100]))

# ═══════════════════════════════════════════════════════════════
# Extraer el helper
# ═══════════════════════════════════════════════════════════════
patron_helper = re.compile(
    r"\n# ═+\n# Helper · ¿El banco aún puede insertar.*?\n(    return \(ahora - hc\) <= timedelta\(hours=horas\)\n)",
    re.DOTALL,
)
m = patron_helper.search(src)
if not m:
    print("ERROR: no encontre el helper completo")
    raise SystemExit(1)

helper_block = m.group(0)
src = src[:m.start()] + src[m.end():]
print("OK: helper extraído")

# ═══════════════════════════════════════════════════════════════
# Encontrar los decoradores de _guardar_apuesta_impl
# ═══════════════════════════════════════════════════════════════
patron_deco = re.compile(
    r"(\n)(@login_required\s*\n@require_POST\s*\n@csrf_exempt\s*\n\s*\n\s*\n\s*\n)(def _guardar_apuesta_impl)",
)
m2 = patron_deco.search(src)
if not m2:
    print("ERROR: no encontre el bloque de decoradores")
    print("Buscando '_guardar_apuesta_impl'...")
    idx = src.find("def _guardar_apuesta_impl")
    print(repr(src[max(0, idx-300):idx+50]))
    raise SystemExit(1)

# Reconstruir con el helper ANTES de los decoradores
nuevo = m2.group(1) + helper_block.strip() + "\n\n" + m2.group(2) + m2.group(3)
src = src[:m2.start()] + nuevo + src[m2.end():]
print("OK: helper reubicado antes de los decoradores")

p.write_text(src, encoding="utf-8")

try:
    ast.parse(src)
    print("OK: sintaxis correcta")
except SyntaxError as e:
    print("ERROR sintaxis:", e)
    raise SystemExit(1)

# Verificar
idx2 = src.find("def _dentro_ventana_banco")
print("\nContexto final:")
print(repr(src[max(0, idx2-150):idx2+50]))
