from pathlib import Path
import ast

p = Path("/home/LottoBooM/usuarios/models.py")
src = p.read_text(encoding="utf-8")

if "prestamo_badge_visto" in src:
    print("SKIP: campo ya existe")
    raise SystemExit(0)

# Buscar la clase Perfil
idx = src.find("class Perfil(")
if idx < 0:
    print("ERROR: no encontré class Perfil")
    raise SystemExit(1)

# Encontrar la última línea de campos antes de class Meta o def
nueva_linea = "\n    # FIX_PRESTAMO_V1: badge 'Nuevo' en sidebar\n    prestamo_badge_visto = models.BooleanField(default=False)\n"

# Insertar antes de la primera 'class Meta:' después de Perfil
idx_meta = src.find("    class Meta:", idx)
if idx_meta < 0:
    print("ERROR: no encontré class Meta en Perfil")
    raise SystemExit(1)

src = src[:idx_meta] + nueva_linea + "\n" + src[idx_meta:]

try:
    ast.parse(src)
except SyntaxError as e:
    print(f"ERROR sintaxis: {e}")
    raise SystemExit(1)

p.write_text(src, encoding="utf-8")
print("OK: prestamo_badge_visto agregado a Perfil")
