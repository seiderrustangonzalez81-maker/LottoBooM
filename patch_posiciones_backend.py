from pathlib import Path
import ast

p = Path("/home/LottoBooM/jugadas/views.py")
src = p.read_text(encoding="utf-8")

if "POSICION_PRELOAD_V1" in src:
    print("SKIP: ya aplicado")
    raise SystemExit(0)

viejo = """                    lineas.append({
                        'tipo': tipo,
                        'numero': j.numero,
                        'monto': float(j.monto),
                        'sorteo_id': j.sorteo_id,
                    })"""

nuevo = """                    # POSICION_PRELOAD_V1
                    _meta_orig = (j.metadata or {}).get('original', {}) or {}
                    lineas.append({
                        'tipo': tipo,
                        'numero': j.numero,
                        'monto': float(j.monto),
                        'sorteo_id': j.sorteo_id,
                        'posicion': _meta_orig.get('posicion'),
                    })"""

if viejo not in src:
    print("ERROR: no encontré el bloque de lineas.append")
    raise SystemExit(1)
src = src.replace(viejo, nuevo, 1)

try:
    ast.parse(src)
except SyntaxError as e:
    print(f"ERROR sintaxis: {e}")
    raise SystemExit(1)

p.write_text(src, encoding="utf-8")
print("OK: POSICION_PRELOAD_V1 aplicado")
