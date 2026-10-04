# -*- coding: utf-8 -*-
"""Agrega @login_required a cuadre_diario_view."""
import re, shutil, datetime, py_compile
from pathlib import Path

TS = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
VIEWS = Path('/home/LottoBooM/roles/views.py')

v = VIEWS.read_text(encoding='utf-8')
orig = v

# Buscar "def cuadre_diario_view" y ver qué hay justo antes
patron = re.compile(r'(?m)^(@login_required\s*\n+)?def cuadre_diario_view\(request\):')

m = patron.search(v)
if not m:
    print('!! no se encontró def cuadre_diario_view')
    raise SystemExit(1)

if m.group(1):
    print('-- ya tiene @login_required')
else:
    v = v[:m.start()] + '@login_required\ndef cuadre_diario_view(request):' + v[m.end():]
    print('OK: @login_required agregado a cuadre_diario_view')

if v == orig:
    print('Sin cambios')
    raise SystemExit(0)

tmp = VIEWS.with_suffix('.py.chk')
tmp.write_text(v, encoding='utf-8')
try:
    py_compile.compile(str(tmp), doraise=True)
    print('OK: sintaxis Python')
finally:
    tmp.unlink(missing_ok=True)

bak = VIEWS.with_suffix(VIEWS.suffix + '.bak_loginreq_' + TS)
shutil.copy2(VIEWS, bak)
print(f'Backup: {bak.name}')
VIEWS.write_text(v, encoding='utf-8')
print('GUARDADO')
print()
print('FIX_LOGIN_REQUIRED COMPLETO')
