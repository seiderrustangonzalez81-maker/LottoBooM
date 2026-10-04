from pathlib import Path

p = Path("/home/LottoBooM/roles/views.py")
src = p.read_text(encoding="utf-8")

if "motivo_tipo=request.POST.get('motivo_tipo'" in src:
    print("SKIP: ya aplicado")
    raise SystemExit(0)

# Bloque a reemplazar (idéntico en las 2 ocurrencias)
viejo = """            mensaje_cliente=mensaje,
            datos_via_cliente=datos_via
        )"""

nuevo = """            mensaje_cliente=mensaje,
            datos_via_cliente=datos_via,
            motivo_tipo=request.POST.get('motivo_tipo', 'cobro_premios'),
            motivo_detalle=request.POST.get('motivo_detalle', '').strip(),
        )"""

# Bloque indentado a 8 espacios (dentro del segundo if/elif)
viejo2 = """                mensaje_cliente=mensaje,
                datos_via_cliente=datos_via
            )"""

nuevo2 = """                mensaje_cliente=mensaje,
                datos_via_cliente=datos_via,
                motivo_tipo=request.POST.get('motivo_tipo', 'cobro_premios'),
                motivo_detalle=request.POST.get('motivo_detalle', '').strip(),
            )"""

n1 = 0
if viejo in src:
    src = src.replace(viejo, nuevo, 1)
    n1 += 1
    print(f"OK bloque 1 (indent 12 espacios) patcheado")

n2 = 0
if viejo2 in src:
    src = src.replace(viejo2, nuevo2, 1)
    n2 += 1
    print(f"OK bloque 2 (indent 16 espacios) patcheado")

if n1 == 0 and n2 == 0:
    print("ERROR: ningun bloque matcheado")
    raise SystemExit(1)

p.write_text(src, encoding="utf-8")
print(f"OK total: {n1 + n2} bloque(s) patcheado(s)")

import ast
ast.parse(src)
print("OK sintaxis")
