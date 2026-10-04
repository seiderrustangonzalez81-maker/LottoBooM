from pathlib import Path

p = Path("/home/LottoBooM/jugadas/views.py")
src = p.read_text(encoding="utf-8")

# Chequeo específico: la línea completa con indentación (así no matchea imports del top)
viejo = "    from jugadas.models import Jugada, FormaJuego, Sorteo\n"

if "    from jugadas.models import Jugada, FormaJuego\n    from sorteos.models import Sorteo\n" in src:
    print("SKIP: ya aplicado (helper correcto)")
    raise SystemExit(0)

if viejo not in src:
    print("ERROR: no encontré la línea específica con indentación de 4 espacios")
    print("Cuenta ocurrencias totales:")
    print("  'Jugada, FormaJuego, Sorteo':", src.count("Jugada, FormaJuego, Sorteo"))
    print("  'from jugadas.models import Jugada':", src.count("from jugadas.models import Jugada"))
    raise SystemExit(1)

# Reemplazar TODAS las ocurrencias (por si hay más de una)
n = src.count(viejo)
src = src.replace(viejo,
    "    from jugadas.models import Jugada, FormaJuego\n    from sorteos.models import Sorteo\n")
print(f"OK: {n} ocurrencia(s) reemplazada(s)")

p.write_text(src, encoding="utf-8")

import ast
try:
    ast.parse(src)
    print("OK: sintaxis válida")
except SyntaxError as e:
    print(f"ERROR sintaxis: {e}")
    raise SystemExit(1)

print()
print("═══ Resumen ═══")
print("from sorteos.models import Sorteo (total):", src.count("from sorteos.models import Sorteo"))
print("Jugada, FormaJuego, Sorteo (mal):", src.count("Jugada, FormaJuego, Sorteo"))
