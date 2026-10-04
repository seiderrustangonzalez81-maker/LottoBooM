import re
from pathlib import Path

p = Path("/home/LottoBooM/jugadas/views.py")
src = p.read_text(encoding="utf-8")
original = src

if "def _consolidar_tripletas(" in src:
    print("SKIP: _consolidar_tripletas ya esta definida")
    raise SystemExit(0)

helper_tripletas = '''

# ═══════════════════════════════════════════════════════════════
# Helper · Consolidar tripletas (FIX_TRIPLETA_V1)
# ═══════════════════════════════════════════════════════════════
def _consolidar_tripletas(items):
    """Agrupa items tripleta con mismo (sorteo_id, monto) en uno solo."""
    if not items:
        return items
    otros = []
    tripletas_por_key = {}
    for it in items:
        tipo = (it.get('tipo') or '').strip().lower()
        if tipo != 'tripleta':
            otros.append(it)
            continue
        key = (it.get('sorteo_id'), str(it.get('monto', 0)))
        if key not in tripletas_por_key:
            tripletas_por_key[key] = {
                'tipo': it.get('tipo'),
                'numero': it.get('numero', ''),
                'monto': it.get('monto', 0),
                'sorteo_id': it.get('sorteo_id'),
            }
        else:
            nums_prev = tripletas_por_key[key]['numero']
            nums_new = it.get('numero', '')
            tripletas_por_key[key]['numero'] = (nums_prev + ' ' + nums_new).strip()
    return otros + list(tripletas_por_key.values())

'''

# Buscar el final de _jugada_duplicada
patron = re.compile(
    r"(def _jugada_duplicada\(.*?\n    return Jugada\.objects\.filter\(.*?\n\s*\)\.exists\(\)\n)",
    re.DOTALL,
)
m = patron.search(src)
if not m:
    print("ERROR: no encontre el final de _jugada_duplicada")
    raise SystemExit(1)

src = src[:m.end()] + helper_tripletas + src[m.end():]
p.write_text(src, encoding="utf-8")
print("OK: _consolidar_tripletas insertada")

import ast
try:
    ast.parse(src)
    print("OK: sintaxis correcta")
except SyntaxError as e:
    print(f"ERROR: sintaxis linea {e.lineno}: {e.msg}")
    p.write_text(original, encoding="utf-8")
    print("REVERTIDO")
    raise SystemExit(1)

print(f"_consolidar_tripletas: {src.count('def _consolidar_tripletas')} definiciones")
print(f"Llamadas: {src.count('_consolidar_tripletas(')}")
