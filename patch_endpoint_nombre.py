from pathlib import Path

p = Path("/home/LottoBooM/jugadas/views.py")
src = p.read_text(encoding="utf-8")

if "'forma_nombre': fj.nombre" in src:
    print("SKIP: ya aplicado")
    raise SystemExit(0)

viejo = """            data[str(fj.id)] = {
                'pool_total': float(pool),
                'consumido_por_numero': {c['numero']: float(c['total']) for c in consumos}
            }"""

nuevo = """            data[str(fj.id)] = {
                'forma_nombre': fj.nombre,
                'forma_id': fj.id,
                'pool_total': float(pool),
                'consumido_por_numero': {c['numero']: float(c['total']) for c in consumos}
            }"""

if viejo not in src:
    print("ERROR: no encontre el bloque exacto")
    print("Buscando variantes...")
    # Buscar variante
    import re
    patron = re.compile(
        r"data\[str\(fj\.id\)\] = \{\s*\n\s*'pool_total':\s*float\(pool\),\s*\n\s*'consumido_por_numero':.*?\n\s*\}",
        re.DOTALL,
    )
    m = patron.search(src)
    if m:
        reemplazo = """data[str(fj.id)] = {
                'forma_nombre': fj.nombre,
                'forma_id': fj.id,
                'pool_total': float(pool),
                'consumido_por_numero': {c['numero']: float(c['total']) for c in consumos}
            }"""
        src = src[:m.start()] + reemplazo + src[m.end():]
        print("OK: aplicado via regex")
    else:
        print("ERROR: no pude matchear de ninguna forma")
        raise SystemExit(1)
else:
    src = src.replace(viejo, nuevo, 1)
    print("OK: aplicado exacto")

p.write_text(src, encoding="utf-8")

import ast
try:
    ast.parse(src)
    print("OK: sintaxis correcta")
except SyntaxError as e:
    print(f"ERROR: {e}")
    raise SystemExit(1)
