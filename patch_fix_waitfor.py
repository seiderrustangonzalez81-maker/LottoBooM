from pathlib import Path
import re

p = Path("/home/LottoBooM/jugadas/templates/jugadas/apostar.html")
src = p.read_text(encoding="utf-8")

# Buscar las 2 definiciones de waitFor
patron = re.compile(r"function waitFor\(cond, timeout, intervalo\)\{.*?\n\}\n", re.DOTALL)
matches = list(patron.finditer(src))
print(f"INFO: {len(matches)} definiciones de waitFor encontradas")

if len(matches) > 1:
    # Eliminar todas menos la primera
    for m in reversed(matches[1:]):
        src = src[:m.start()] + src[m.end():]
        print(f"OK: eliminada definicion desde pos {m.start()}")

p.write_text(src, encoding="utf-8")

# Verificar
restantes = len(re.findall(r"function waitFor", src))
print(f"OK: {restantes} definicion(es) de waitFor restantes")
