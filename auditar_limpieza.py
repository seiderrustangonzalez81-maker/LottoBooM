# -*- coding: utf-8 -*-
"""Auditoría completa: qué se puede borrar en cada app/carpeta."""
import os
from pathlib import Path
from datetime import datetime

RAIZ = Path('/home/LottoBooM')
hoy = datetime.now().strftime('%Y%m%d')

# Apps de Django (no tocar código pero sí revisar basura interna)
APPS = ['jugadas', 'roles', 'sorteos', 'pagos', 'usuarios', 'publico',
        'resultados', 'superadmin', 'banco', 'comercial', 'ubicaciones']

print('=' * 78)
print('AUDITORÍA DE LIMPIEZA — DRY RUN (no borra nada)')
print('=' * 78)

# ═══════════════════════════════════════════════════════════
# 1. Backups folder
# ═══════════════════════════════════════════════════════════
print()
print('1. CARPETA /backups/')
print('-' * 78)
backups_dir = RAIZ / 'backups'
if backups_dir.exists():
    total = 0
    for p in sorted(backups_dir.iterdir()):
        if p.is_file():
            s = p.stat().st_size
            total += s
            print(f'   {p.name:<60} {s/1024/1024:>8.2f} MB')
        elif p.is_dir():
            sub = sum(f.stat().st_size for f in p.rglob('*') if f.is_file())
            total += sub
            print(f'   {p.name}/<dir>{"":<45} {sub/1024/1024:>8.2f} MB')
    print(f'   {"TOTAL":<60} {total/1024/1024:>8.2f} MB')
else:
    print('   (no existe)')

# ═══════════════════════════════════════════════════════════
# 2. LottoBooM/ (carpeta settings)
# ═══════════════════════════════════════════════════════════
print()
print('2. CARPETA /LottoBooM/ (módulo settings)')
print('-' * 78)
mod = RAIZ / 'LottoBooM'
if mod.exists():
    for p in sorted(mod.iterdir()):
        if p.is_dir():
            s = sum(f.stat().st_size for f in p.rglob('*') if f.is_file())
            print(f'   {p.name}/<dir>{"":<45} {s/1024/1024:>8.2f} MB')
        else:
            s = p.stat().st_size
            print(f'   {p.name:<60} {s/1024:>8.1f} KB')

# ═══════════════════════════════════════════════════════════
# 3. Contenido de cada app (buscando basura)
# ═══════════════════════════════════════════════════════════
print()
print('3. BASURA EN APPS (no .py, no .html oficiales)')
print('-' * 78)
basura_patrones = [
    '*.pyc', '*.pyo', '__pycache__',
    '*.bak', '*.bak_*', '*~', '*.orig', '*.swp',
    '*.log', '*.sqlite3', '*.sqlite3-journal',
]
encontrado_basura = []
for app in APPS:
    app_dir = RAIZ / app
    if not app_dir.exists():
        continue
    items = []
    for pat in basura_patrones:
        for p in app_dir.rglob(pat):
            if p.is_file() and 'migrations' not in str(p):
                items.append(p)
    if items:
        total = sum(p.stat().st_size for p in items)
        print(f'   {app}/: {len(items)} archivos basura — {total/1024:.1f} KB')
        for p in sorted(items, key=lambda x: -x.stat().st_size)[:5]:
            print(f'      {p.relative_to(RAIZ)}  ({p.stat().st_size/1024:.1f} KB)')
        encontrado_basura.extend(items)

# ═══════════════════════════════════════════════════════════
# 4. Archivos sueltos en raíz que puedan ser basura
# ═══════════════════════════════════════════════════════════
print()
print('4. ARCHIVOS SUELTOS EN RAÍZ (potencialmente borrables)')
print('-' * 78)
sospechosos = []
for p in RAIZ.iterdir():
    if not p.is_file():
        continue
    n = p.name
    # Extensiones sospechosas
    if n.endswith(('.log', '.tmp', '.temp', '.swp', '.orig')):
        sospechosos.append(p)
    # Archivos sin extensión (basura)
    elif '.' not in n and n not in ('.gitignore', '.bashrc', '.profile', '.vimrc', '.gitconfig'):
        sospechosos.append(p)
    # Archivos muy viejos (>60 días)
    elif p.stat().st_mtime < datetime.now().timestamp() - 60*24*3600:
        if n.endswith(('.py', '.sh', '.json', '.csv', '.txt')):
            sospechosos.append(p)

if sospechosos:
    for p in sorted(sospechosos, key=lambda x: -x.stat().st_size):
        dias = (datetime.now().timestamp() - p.stat().st_mtime) / 86400
        print(f'   {p.name:<50} {p.stat().st_size/1024:>8.1f} KB  ({dias:.0f} días)')
else:
    print('   (nada sospechoso)')

# ═══════════════════════════════════════════════════════════
# 5. media/ y logs/
# ═══════════════════════════════════════════════════════════
print()
print('5. /media/ y /logs/')
print('-' * 78)
for carpeta in ['media', 'logs']:
    d = RAIZ / carpeta
    if d.exists():
        sub_items = list(d.rglob('*'))
        archivos = [p for p in sub_items if p.is_file()]
        total = sum(p.stat().st_size for p in archivos)
        print(f'   {carpeta}/: {len(archivos)} archivos, {total/1024/1024:.2f} MB')
        # Top 5 más grandes
        for p in sorted(archivos, key=lambda x: -x.stat().st_size)[:5]:
            print(f'      {p.relative_to(d)}  ({p.stat().st_size/1024:.1f} KB)')

# ═══════════════════════════════════════════════════════════
# 6. venv duplicados (SOLO INFO, no borrar)
# ═══════════════════════════════════════════════════════════
print()
print('6. VENVs (NO BORRAR sin verificar cuál se usa)')
print('-' * 78)
for venv_path in ['venv', '.venv', 'LottoBooM/venv']:
    p = RAIZ / venv_path
    if p.exists():
        s = sum(f.stat().st_size for f in p.rglob('*') if f.is_file())
        print(f'   {venv_path:<40} {s/1024/1024:>8.2f} MB')
        # ¿Es un venv real?
        pyvenv = p / 'pyvenv.cfg'
        print(f'      ¿pyvenv.cfg existe? {"sí" if pyvenv.exists() else "NO"}')

# ═══════════════════════════════════════════════════════════
# 7. RESUMEN
# ═══════════════════════════════════════════════════════════
print()
print('=' * 78)
print('RESUMEN')
print('=' * 78)
print(f'Archivos basura en apps: {len(encontrado_basura)} ({sum(p.stat().st_size for p in encontrado_basura)/1024:.1f} KB)')
print(f'Archivos sospechosos en raíz: {len(sospechosos)} ({sum(p.stat().st_size for p in sospechosos)/1024:.1f} KB)')

# Verificar venvs duplicados
v_principal = RAIZ / 'venv'
v_dentro = RAIZ / 'LottoBooM' / 'venv'
if v_principal.exists() and v_dentro.exists():
    print()
    print('⚠️  HAY 2 VENVs (raíz + LottoBooM/). Verificar cuál usa PythonAnywhere antes de tocar.')
    print('   Ejecuta en PythonAnywhere:')
    print('   ls -la $(which python)')
    print('   head -1 .venv/bin/python 2>/dev/null')
