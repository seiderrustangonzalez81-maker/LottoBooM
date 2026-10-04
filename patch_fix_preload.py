from pathlib import Path
import re

p = Path("/home/LottoBooM/jugadas/templates/jugadas/apostar.html")
src = p.read_text(encoding="utf-8")

# ═══════════════════════════════════════════════════════════════
# FIX 1: Llave huérfana en preloadBoletaEdit
# ═══════════════════════════════════════════════════════════════
viejo = """  waitFor(function(){ return document.querySelector('.fp-chip'); }, 8000)
  }
    .catch(function(e){ console.warn('[apostar] Timeout esperando chips FP:', e.message); })"""

nuevo = """  waitFor(function(){ return document.querySelector('.fp-chip'); }, 8000)
    .catch(function(e){ console.warn('[apostar] Timeout esperando chips FP:', e.message); })"""

if viejo not in src:
    print("WARN: no encontre el patron exacto de la llave huerfana")
    print("     Buscando variante...")
    # Intentar variantes
    viejo_alt = "document.querySelector('.fp-chip'); }, 8000)\n  }\n"
    if viejo_alt in src:
        print("OK: encontre variante con salto de linea")
        src = src.replace(viejo_alt, "document.querySelector('.fp-chip'); }, 8000)\n", 1)
    else:
        print("ERROR: no se pudo detectar la llave huerfana automaticamente")
        raise SystemExit(1)
else:
    src = src.replace(viejo, nuevo, 1)
    print("OK: llave huerfana eliminada")

# ═══════════════════════════════════════════════════════════════
# FIX 2: Eliminar waitFor duplicada
# ═══════════════════════════════════════════════════════════════
# Buscar las 2 definiciones
patron_waitfor = re.compile(
    r"function waitFor\(cond, timeout, intervalo\)\{.*?\n\}\n",
    re.DOTALL,
)

matches = list(patron_waitfor.finditer(src))
print(f"INFO: encontradas {len(matches)} definiciones de waitFor")

if len(matches) > 1:
    # Eliminar la segunda (dejando la primera)
    segundo = matches[1]
    src = src[:segundo.start()] + src[segundo.end():]
    print("OK: waitFor duplicada eliminada (quedó 1)")

# ═══════════════════════════════════════════════════════════════
# Verificar sintaxis
# ═══════════════════════════════════════════════════════════════
p.write_text(src, encoding="utf-8")
print("OK: archivo guardado")

# Verificacion de balance de llaves en preloadBoletaEdit
idx_ini = src.find("function preloadBoletaEdit(data)")
idx_fin = src.find("function inyectarLineasBoleta(data)")
if idx_ini > 0 and idx_fin > idx_ini:
    cuerpo = src[idx_ini:idx_fin]
    abre = cuerpo.count("{")
    cierra = cuerpo.count("}")
    print(f"INFO: llaves en preloadBoletaEdit: {abre} abiertas, {cierra} cerradas")
    if abre == cierra:
        print("OK: balance de llaves correcto")
    else:
        print(f"WARN: desbalance de {abre-cierra} llaves")
