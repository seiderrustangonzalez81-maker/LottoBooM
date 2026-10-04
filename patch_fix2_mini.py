from pathlib import Path
import re

p = Path("/home/LottoBooM/jugadas/templates/jugadas/apostar.html")
src = p.read_text(encoding="utf-8")

# Regex flexible que tolera cualquier indentación
patron = re.compile(
    r"(if \(parletBlocked && vCand > 0\)\{\s*\n)"
    r"(\s+)const percap = vCand / nPlays;\s*\n"
    r"(\s+)row\.montos\['parlet'\] = percap\.toFixed\(2\);\s*\n"
    r"(\s+)inpParlet\.value = percap\.toFixed\(2\);",
    re.MULTILINE,
)

def fix(m):
    ind = m.group(2)
    return (
        m.group(1) +
        ind + "const percap = Math.floor((vCand / nPlays) * 100) / 100;\n" +
        ind + "row.montos['parlet'] = percap.toFixed(2);\n" +
        ind + "inpParlet.value = percap.toFixed(2);\n" +
        ind + "const candadoReal = (percap * nPlays).toFixed(2);\n" +
        ind + "row.montos['candado'] = candadoReal;\n" +
        ind + "if (inpCand) inpCand.value = candadoReal;"
    )

src_new, n = patron.subn(fix, src, count=1)
if n == 0:
    print("ERROR: no matcheo ni con regex flexible")
    print("Pégame el sed -n '3105,3120p' para ver el bloque real")
    raise SystemExit(1)

p.write_text(src_new, encoding="utf-8")
print("OK: FIX 2 aplicado via regex")

# Verificar
print("Math.floor totales:", src_new.count("Math.floor"))
print("Math.floor((vCand / nPlays):", src_new.count("Math.floor((vCand / nPlays)"))
