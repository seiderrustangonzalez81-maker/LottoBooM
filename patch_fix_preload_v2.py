from pathlib import Path
import re

p = Path("/home/LottoBooM/jugadas/templates/jugadas/apostar.html")
src = p.read_text(encoding="utf-8")

# ═══════════════════════════════════════════════════════════════
# FIX 1: Llave huérfana entre waitFor(.fp-chip) y .catch
# ═══════════════════════════════════════════════════════════════
# Regex flexible: cualquier línea que sea solo "}" (con espacios) entre esas 2 lineas
patron = re.compile(
    r"(waitFor\(function\(\)\{ return document\.querySelector\('\.fp-chip'\); \}, 8000\))\s*\n(\s*\}\s*\n)(\s*\.catch\(function\(e\)\{ console\.warn\('\[apostar\] Timeout esperando chips FP)",
    re.MULTILINE,
)

def fix_llave(m):
    return m.group(1) + "\n" + m.group(3)

src_new, n = patron.subn(fix_llave, src)
if n == 0:
    print("WARN: regex no encontro la llave huerfana")
    # Intento 2: buscar cualquier "}" entre las 2 lineas
    patron2 = re.compile(
        r"(waitFor\(function\(\)\{ return document\.querySelector\('\.fp-chip'\); \}, 8000\))(.*?)(\.catch\(function\(e\)\{ console\.warn\('\[apostar\] Timeout esperando chips FP)",
        re.DOTALL,
    )
    def fix_llave2(m):
        # Eliminar cualquier "}" suelto en el medio
        medio = m.group(2)
        medio_limpio = re.sub(r"^\s*\}\s*$", "", medio, flags=re.MULTILINE)
        return m.group(1) + medio_limpio + m.group(3)
    src_new, n = patron2.subn(fix_llave2, src)
    if n == 0:
        print("ERROR: no pude arreglar automaticamente")
        print("Buscando contexto...")
        idx = src.find("querySelector('.fp-chip'); }, 8000)")
        if idx > 0:
            print("Contexto (200 chars):")
            print(repr(src[idx:idx+200]))
        raise SystemExit(1)
    else:
        print(f"OK: llave huerfana eliminada (metodo 2, {n} cambio)")
else:
    src_new = src_new
    print(f"OK: llave huerfana eliminada (metodo 1, {n} cambio)")

src = src_new

# ═══════════════════════════════════════════════════════════════
# FIX 2: waitFor duplicada
# ═══════════════════════════════════════════════════════════════
patron_waitfor = re.compile(
    r"function waitFor\(cond, timeout, intervalo\)\{.*?\n\}\n",
    re.DOTALL,
)

matches = list(patron_waitfor.finditer(src))
print(f"INFO: {len(matches)} definiciones de waitFor")

if len(matches) > 1:
    segundo = matches[1]
    src = src[:segundo.start()] + src[segundo.end():]
    print("OK: waitFor duplicada eliminada")

p.write_text(src, encoding="utf-8")

# ═══════════════════════════════════════════════════════════════
# Verificar balance de llaves
# ═══════════════════════════════════════════════════════════════
idx_ini = src.find("function preloadBoletaEdit(data)")
idx_fin = src.find("function inyectarLineasBoleta(data)")
if idx_ini > 0 and idx_fin > idx_ini:
    cuerpo = src[idx_ini:idx_fin]
    abre = cuerpo.count("{")
    cierra = cuerpo.count("}")
    print(f"INFO: llaves en preloadBoletaEdit: {abre} abren / {cierra} cierran")
    if abre == cierra:
        print("OK: balance correcto")
    else:
        print(f"WARN: desbalance de {abre-cierra} llaves")

print("OK: archivo guardado")
