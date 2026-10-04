from pathlib import Path
import ast

p = Path("/home/LottoBooM/jugadas/views.py")
src = p.read_text(encoding="utf-8")

if "def _get_telefono(" in src:
    print("SKIP: _get_telefono ya existe")
    raise SystemExit(0)

helper = '''def _get_telefono(user):
    """Devuelve el telefono del usuario desde su perfil, o '' si no tiene."""
    if not user:
        return ''
    try:
        perfil = getattr(user, 'perfil', None)
        if perfil is not None:
            return getattr(perfil, 'telefono', '') or ''
    except Exception:
        pass
    return ''


'''

# Insertar antes de _get_banco_de
if "def _get_banco_de(user):" in src:
    src = src.replace("def _get_banco_de(user):", helper + "def _get_banco_de(user):", 1)
    print("OK: _get_telefono insertado antes de _get_banco_de")
else:
    # Fallback: después de logger = ...
    import re
    m = re.search(r"(logger\s*=\s*logging\.getLogger\(__name__\)\s*\n)", src)
    if m:
        src = src[:m.end()] + "\n" + helper + src[m.end():]
        print("OK: _get_telefono insertado tras logger")
    else:
        print("ERROR: no encontre ancla")
        raise SystemExit(1)

p.write_text(src, encoding="utf-8")

try:
    ast.parse(src)
    print("OK: sintaxis correcta")
except SyntaxError as e:
    print("ERROR sintaxis:", e)
    raise SystemExit(1)

print("Llamadas _get_telefono:", src.count("_get_telefono("))
print("Definicion:", src.count("def _get_telefono("))
