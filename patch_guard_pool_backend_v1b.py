from pathlib import Path

p = Path("/home/LottoBooM/jugadas/views.py")
src = p.read_text(encoding="utf-8")

viejo = "    from jugadas.models import Jugada, FormaJuego, Sorteo\n"
nuevo = "    from jugadas.models import Jugada, FormaJuego\n    from sorteos.models import Sorteo\n"

if "from sorteos.models import Sorteo" in src:
    print("SKIP: ya aplicado")
    raise SystemExit(0)

if viejo not in src:
    print("ERROR: no encontré el import malo exacto")
    print("Busca con: grep -n 'from jugadas.models import' jugadas/views.py")
    raise SystemExit(1)

src = src.replace(viejo, nuevo, 1)
p.write_text(src, encoding="utf-8")

import ast
try:
    ast.parse(src)
    print("OK: import corregido + sintaxis válida")
except SyntaxError as e:
    print(f"ERROR sintaxis: {e}")
    raise SystemExit(1)

print("from sorteos.models import Sorteo:", src.count("from sorteos.models import Sorteo"))
