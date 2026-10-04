from pathlib import Path
import re

p = Path("/home/LottoBooM/jugadas/views.py")
src = p.read_text(encoding="utf-8")

# Buscar el bloque "with transaction.atomic():" seguido de "if es_edicion_boleta:"
patron = re.compile(
    r"(\s+)(with transaction\.atomic\(\):\s*\n\s+if es_edicion_boleta:)",
    re.MULTILINE,
)

m = patron.search(src)
if not m:
    print("ERROR: no encontre 'with transaction.atomic(): if es_edicion_boleta:'")
    raise SystemExit(1)

indent = m.group(1)

# Verificar si ya tiene "boleta = None"
contexto = src[m.start():m.start()+200]
if "boleta = None" in contexto:
    print("SKIP: ya tiene boleta = None")
else:
    # Insertar "boleta = None" después de "with transaction.atomic():"
    viejo = m.group(2)
    nuevo = f"""{indent}with transaction.atomic():
{indent}    # Asegurar que 'boleta' este siempre definida
{indent}    boleta = None
{indent}    if es_edicion_boleta:"""
    src = src[:m.start()] + nuevo + src[m.end():]
    print("OK: boleta = None insertado")

# Eliminar cualquier "boleta = None" duplicado que ya estaba (el del patch anterior)
# Esto podría haber dejado el código con 2 asignaciones
patron_dup = re.compile(
    r"(\s+)# Ya se manejo en el bloque anterior si es edicion_boleta\s*\n\s+if not es_edicion_pura and boleta is None:",
    re.MULTILINE,
)
m2 = patron_dup.search(src)
if m2:
    print(f"INFO: encontrado el bloque de PASO 3 con 'boleta is None'")
else:
    print("INFO: no encontrado el bloque 'boleta is None'")

p.write_text(src, encoding="utf-8")

# Verificar sintaxis
import ast
try:
    ast.parse(src)
    print("OK: sintaxis correcta")
except SyntaxError as e:
    print(f"ERROR: sintaxis linea {e.lineno}: {e.msg}")
    raise SystemExit(1)
