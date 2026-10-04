# -*- coding: utf-8 -*-
"""Limpieza segura: backups viejos + __pycache__. NO toca venvs ni código."""
import os, shutil, subprocess
from pathlib import Path

RAIZ = Path('/home/LottoBooM')

# ═══════════════════════════════════════════════════════════
# A. Backups viejos
# ═══════════════════════════════════════════════════════════
backups_dir = RAIZ / 'backups'
a_borrar_archivos = []
a_borrar_dirs = []

if backups_dir.exists():
    for p in backups_dir.iterdir():
        n = p.name
        if p.is_file() and n.startswith('db_') and n.endswith('.sqlite3'):
            a_borrar_archivos.append(p)
        elif p.is_dir() and (n.startswith('templates_20260921') or n.startswith('orphans_')):
            a_borrar_dirs.append(p)

# ═══════════════════════════════════════════════════════════
# B. __pycache__ en apps
# ═══════════════════════════════════════════════════════════
APPS = ['jugadas', 'roles', 'sorteos', 'pagos', 'usuarios', 'publico',
        'resultados', 'superadmin', 'banco', 'comercial', 'ubicaciones',
        'LottoBooM']
for app in APPS:
    d = RAIZ / app
    if not d.exists():
        continue
    for p in d.rglob('__pycache__'):
        if p.is_dir():
            a_borrar_dirs.append(p)

# ═══════════════════════════════════════════════════════════
# C. .pyc sueltos en todo el proyecto (excepto venvs)
# ═══════════════════════════════════════════════════════════
for p in RAIZ.rglob('*.pyc'):
    if 'venv' in p.parts or '.venv' in p.parts:
        continue
    if p.is_file():
        a_borrar_archivos.append(p)

# ═══════════════════════════════════════════════════════════
# DRY RUN
# ═══════════════════════════════════════════════════════════
print('=' * 78)
print('LIMPIEZA SEGURA — DRY RUN')
print('=' * 78)

def size_dir(d):
    return sum(f.stat().st_size for f in d.rglob('*') if f.is_file())

total_files = sum(p.stat().st_size for p in a_borrar_archivos if p.exists())
total_dirs = sum(size_dir(d) for d in a_borrar_dirs if d.exists() and d.is_dir())

print(f'Archivos a borrar: {len(a_borrar_archivos)} — {total_files/1024/1024:.2f} MB')
for p in a_borrar_archivos[:20]:
    print(f'   {p.relative_to(RAIZ)}')
if len(a_borrar_archivos) > 20:
    print(f'   ... y {len(a_borrar_archivos)-20} más')

print()
print(f'Directorios a borrar: {len(a_borrar_dirs)} — {total_dirs/1024/1024:.2f} MB')
for d in a_borrar_dirs:
    print(f'   {d.relative_to(RAIZ)}/')

print()
print('=' * 78)
print(f'TOTAL A LIBERAR: {(total_files + total_dirs)/1024/1024:.2f} MB')
print('=' * 78)
print()

resp = input('¿Aplicar? (si/no): ').strip().lower()
if resp != 'si':
    print('Cancelado.')
    raise SystemExit(0)

# ═══════════════════════════════════════════════════════════
# APLICAR
# ═══════════════════════════════════════════════════════════
b_arch = b_dirs = 0
for p in a_borrar_archivos:
    try:
        p.unlink()
        b_arch += 1
    except Exception as e:
        print(f'  ERROR borrando {p}: {e}')

for d in a_borrar_dirs:
    try:
        shutil.rmtree(d)
        b_dirs += 1
    except Exception as e:
        print(f'  ERROR borrando {d}: {e}')

print()
print(f'✅ Archivos borrados: {b_arch}')
print(f'✅ Directorios borrados: {b_dirs}')

r = subprocess.run(['df', '-h', str(RAIZ)], capture_output=True, text=True)
print()
print(r.stdout)

db = RAIZ / 'db.sqlite3'
if db.exists():
    print(f'✅ db.sqlite3 INTACTA: {db.stat().st_size/1024/1024:.2f} MB')
