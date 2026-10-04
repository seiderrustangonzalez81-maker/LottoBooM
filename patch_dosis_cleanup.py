from pathlib import Path

p = Path("/home/LottoBooM/roles/dosis_default.py")
src = p.read_text(encoding="utf-8")

if "# PATCH_DOSIS_CLEANUP_V1" in src:
    print("SKIP: ya aplicado")
    raise SystemExit(0)

# ─── 1. Quitar la entrada duplicada 'posición': 80 ───
viejo = """    'posicion': 80,
    'posición': 80,
}"""
nuevo = """    'posicion': 80,
}  # PATCH_DOSIS_CLEANUP_V1: 'posición' eliminada — _normalizar() ahora quita acentos"""

if viejo not in src:
    print("ERROR: no encontré el bloque 'posicion': 80 en DOSIS_GLOBAL")
    raise SystemExit(1)
src = src.replace(viejo, nuevo, 1)

# ─── 2. Quitar la entrada duplicada en LIMITES_POR_FORMA ───
viejo2 = """    'posicion': 1000,
    'posición': 1000,
}"""
nuevo2 = """    'posicion': 1000,
}  # PATCH_DOSIS_CLEANUP_V1"""

if viejo2 not in src:
    print("ERROR: no encontré el bloque 'posicion': 1000 en LIMITES_POR_FORMA")
    raise SystemExit(1)
src = src.replace(viejo2, nuevo2, 1)

# ─── 3. Reforzar _normalizar() para que quite acentos ───
viejo3 = """def _normalizar(nombre):
    return (nombre or '').strip().lower()"""
nuevo3 = """def _normalizar(nombre):
    # PATCH_DOSIS_CLEANUP_V1: quita acentos para que 'Posición' == 'posicion'
    import unicodedata
    s = (nombre or '').strip().lower()
    s = unicodedata.normalize('NFD', s)
    return ''.join(c for c in s if unicodedata.category(c) != 'Mn')"""

if viejo3 not in src:
    print("WARN: no encontré _normalizar() — revisa manualmente")
else:
    src = src.replace(viejo3, nuevo3, 1)

# ─── 4. Validar sintaxis ───
import ast
try:
    ast.parse(src)
except SyntaxError as e:
    print(f"ERROR de sintaxis: {e}")
    raise SystemExit(1)

p.write_text(src, encoding="utf-8")
print("OK: dosis_default.py limpiado")
print("  - 'posición': 80 eliminado")
print("  - 'posición': 1000 eliminado")
print("  - _normalizar() ahora quita acentos")
print("OK: sintaxis correcta")
