# -*- coding: utf-8 -*-
"""Análisis profundo: venvs, dotfiles, git, caches."""
import os, subprocess
from pathlib import Path
from datetime import datetime

RAIZ = Path('/home/LottoBooM')

print('=' * 78)
print('ANÁLISIS PROFUNDO — DRY RUN')
print('=' * 78)

# ═══════════════════════════════════════════════════════════
# 1. VENVs — cuál se usa realmente
# ═══════════════════════════════════════════════════════════
print()
print('1. VENVs — comparativa detallada')
print('-' * 78)

venvs = [
    RAIZ / 'venv',
    RAIZ / '.venv',
    RAIZ / 'LottoBooM' / 'venv',
]

for v in venvs:
    if not v.exists():
        print(f'   {v.name}/: no existe')
        continue
    s = sum(f.stat().st_size for f in v.rglob('*') if f.is_file())
    pyvenv_cfg = v / 'pyvenv.cfg'
    python_bin = v / 'bin' / 'python'
    has_python = python_bin.exists()
    mtime = datetime.fromtimestamp(v.stat().st_mtime).strftime('%Y-%m-%d %H:%M')

    print(f'   {v.relative_to(RAIZ)}:')
    print(f'      Tamaño: {s/1024/1024:.2f} MB')
    print(f'      Última modificación: {mtime}')
    print(f'      ¿pyvenv.cfg? {pyvenv_cfg.exists()}')
    if pyvenv_cfg.exists():
        contenido = pyvenv_cfg.read_text()[:200]
        for linea in contenido.split('\n')[:5]:
            if linea.strip():
                print(f'         {linea}')
    print(f'      ¿bin/python? {has_python}')
    if has_python:
        try:
            r = subprocess.run([str(python_bin), '--version'],
                               capture_output=True, text=True, timeout=5)
            print(f'         Version: {r.stdout.strip() or r.stderr.strip()}')
        except Exception as e:
            print(f'         Error: {e}')
    print()

# ═══════════════════════════════════════════════════════════
# 2. Dotfiles y directorios ocultos
# ═══════════════════════════════════════════════════════════
print('2. DIRECTORIOS OCULTOS EN RAIZ')
print('-' * 78)
for p in sorted(RAIZ.iterdir()):
    if p.name.startswith('.') and p.name not in ('.gitignore', '.bashrc', '.profile', '.vimrc', '.gitconfig', '.pythonstartup.py'):
        if p.is_dir():
            s = sum(f.stat().st_size for f in p.rglob('*') if f.is_file())
            print(f'   {p.name}/: {s/1024/1024:.2f} MB')
        else:
            print(f'   {p.name}: {p.stat().st_size/1024:.1f} KB')

# ═══════════════════════════════════════════════════════════
# 3. .git — historia del proyecto
# ═══════════════════════════════════════════════════════════
print()
print('3. GIT')
print('-' * 78)
git_dir = RAIZ / '.git'
if git_dir.exists():
    s = sum(f.stat().st_size for f in git_dir.rglob('*') if f.is_file())
    print(f'   .git/: {s/1024/1024:.2f} MB')
    r = subprocess.run(['git', 'log', '--oneline', '-5'],
                       cwd=RAIZ, capture_output=True, text=True)
    if r.returncode == 0:
        print('   Últimos commits:')
        for l in r.stdout.strip().split('\n'):
            print(f'      {l}')
    r = subprocess.run(['git', 'status', '--porcelain'],
                       cwd=RAIZ, capture_output=True, text=True)
    if r.returncode == 0:
        n = len([l for l in r.stdout.strip().split('\n') if l.strip()])
        print(f'   Archivos modificados sin commit: {n}')

# ═══════════════════════════════════════════════════════════
# 4. Scripts .py en raíz (viejos de +30 días)
# ═══════════════════════════════════════════════════════════
print()
print('4. SCRIPTS .PY EN RAÍZ VIEJOS (+30 días)')
print('-' * 78)
hace30 = datetime.now().timestamp() - 30*24*3600
for p in sorted(RAIZ.glob('*.py')):
    if p.stat().st_mtime < hace30:
        dias = (datetime.now().timestamp() - p.stat().st_mtime) / 86400
        print(f'   {p.name:<45} {p.stat().st_size/1024:>8.1f} KB  ({dias:.0f} días)')

# ═══════════════════════════════════════════════════════════
# 5. media/ detalle
# ═══════════════════════════════════════════════════════════
print()
print('5. MEDIA/')
print('-' * 78)
media = RAIZ / 'media'
if media.exists():
    for p in sorted(media.rglob('*')):
        if p.is_file():
            print(f'   {p.relative_to(media)}  ({p.stat().st_size/1024:.1f} KB)')

# ═══════════════════════════════════════════════════════════
# 6. staticfiles/ y static/ (¿duplicados?)
# ═══════════════════════════════════════════════════════════
print()
print('6. STATIC vs STATICFILES')
print('-' * 78)
for nombre in ['static', 'staticfiles']:
    d = RAIZ / nombre
    if d.exists():
        s = sum(f.stat().st_size for f in d.rglob('*') if f.is_file())
        n = sum(1 for f in d.rglob('*') if f.is_file())
        print(f'   {nombre}/: {n} archivos, {s/1024/1024:.2f} MB')

# ═══════════════════════════════════════════════════════════
# 7. Archivos en raíz más grandes (+500 KB)
# ═══════════════════════════════════════════════════════════
print()
print('7. ARCHIVOS GRANDES EN RAÍZ (+500 KB)')
print('-' * 78)
for p in sorted(RAIZ.iterdir(), key=lambda x: -x.stat().st_size if x.is_file() else 0):
    if p.is_file() and p.stat().st_size > 500*1024:
        print(f'   {p.name:<45} {p.stat().st_size/1024/1024:>8.2f} MB')

# ═══════════════════════════════════════════════════════════
# 8. .cache, .ipython, .local
# ═══════════════════════════════════════════════════════════
print()
print('8. CACHES DE USUARIO')
print('-' * 78)
for nombre in ['.cache', '.ipython', '.local', '.texlive2021']:
    d = RAIZ / nombre
    if d.exists():
        s = sum(f.stat().st_size for f in d.rglob('*') if f.is_file())
        print(f'   {nombre}/: {s/1024/1024:.2f} MB')

# ═══════════════════════════════════════════════════════════
# 9. RESUMEN
# ═══════════════════════════════════════════════════════════
print()
print('=' * 78)
print('RESUMEN')
print('=' * 78)
total_raiz = sum(f.stat().st_size for f in RAIZ.rglob('*') if f.is_file())
print(f'Total del proyecto: {total_raiz/1024/1024:.2f} MB')

# Espacio venvs
total_venvs = 0
for v in venvs:
    if v.exists():
        total_venvs += sum(f.stat().st_size for f in v.rglob('*') if f.is_file())
print(f'Total venvs: {total_venvs/1024/1024:.2f} MB')
if total_venvs > 100*1024*1024:
    print(f'   ⚠️  Si solo 1 venv se usa → se pueden liberar {total_venvs*2/3/1024/1024:.2f} MB aprox')
