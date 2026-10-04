# -*- coding: utf-8 -*-
"""Limpieza de venvs huérfanos + backups WSGI viejos."""
import os, shutil, subprocess
from pathlib import Path

RAIZ = Path('/home/LottoBooM')
WWW = Path('/var/www')

# ═══════════════════════════════════════════════════════════
# A. Verificar WSGI antes (crítico)
# ═══════════════════════════════════════════════════════════
wsgi = WWW / 'lottoboom_pythonanywhere_com_wsgi.py'
if not wsgi.exists():
    print('❌ WSGI no encontrado. Abortando por seguridad.')
    raise SystemExit(1)

contenido = wsgi.read_text()
if "'/home/LottoBooM/venv'" not in contenido:
    print('❌ El WSGI NO apunta a /home/LottoBooM/venv')
    print('Contenido:')
    print(contenido)
    print()
    print('ABORTAR. No sé qué venv usar.')
    raise SystemExit(1)

print('✅ WSGI confirma: /home/LottoBooM/venv es el venv activo')
print()

# ═══════════════════════════════════════════════════════════
# B. Directorios a borrar
# ═══════════════════════════════════════════════════════════
dirs_borrar = [
    (RAIZ / '.venv', 'Venv huérfano'),
    (RAIZ / 'LottoBooM' / 'venv', 'Venv huérfano'),
    (RAIZ / '.virtualenvs' / 'lottoboomenv', 'Venv huérfano'),
]

# ═══════════════════════════════════════════════════════════
# C. Backups WSGI viejos
# ═══════════════════════════════════════════════════════════
wsgi_baks = sorted(WWW.glob('lottoboom_pythonanywhere_com_wsgi.py.*.bak'))

# ═══════════════════════════════════════════════════════════
# DRY RUN
# ═══════════════════════════════════════════════════════════
print('=' * 78)
print('LIMPIEZA DE VENVs HUÉRFANOS — DRY RUN')
print('=' * 78)
print()

def size_dir(d):
    if not d.exists():
        return 0
    return sum(f.stat().st_size for f in d.rglob('*') if f.is_file())

total_dirs = 0
for d, motivo in dirs_borrar:
    if d.exists():
        s = size_dir(d)
        total_dirs += s
        print(f'   {d.relative_to(RAIZ)}/  ({s/1024/1024:.2f} MB) — {motivo}')

total_bak = sum(p.stat().st_size for p in wsgi_baks)
print()
print(f'   Backups WSGI: {len(wsgi_baks)} archivos — {total_bak/1024:.1f} KB')

print()
print('=' * 78)
print(f'TOTAL A LIBERAR: {(total_dirs + total_bak)/1024/1024:.2f} MB')
print('=' * 78)
print()

# Verificar que el venv real sigue
venv_real = RAIZ / 'venv'
if venv_real.exists():
    s = size_dir(venv_real)
    print(f'✅ Venv activo /venv INTACTO: {s/1024/1024:.2f} MB')
else:
    print('❌ ALERTA: /venv no existe. Abortando.')
    raise SystemExit(1)
print()

resp = input('¿Aplicar? (si/no): ').strip().lower()
if resp != 'si':
    print('Cancelado.')
    raise SystemExit(0)

# ═══════════════════════════════════════════════════════════
# APLICAR
# ═══════════════════════════════════════════════════════════
borrados = 0
for d, _ in dirs_borrar:
    if not d.exists():
        continue
    try:
        shutil.rmtree(d)
        borrados += 1
        print(f'  ✅ Borrado: {d.relative_to(RAIZ)}/')
    except Exception as e:
        print(f'  ❌ Error: {d}: {e}')

for p in wsgi_baks:
    try:
        p.unlink()
        print(f'  ✅ Borrado: {p.name}')
    except Exception as e:
        print(f'  ❌ Error: {p}: {e}')

print()
print(f'✅ Directorios borrados: {borrados}')

# ═══════════════════════════════════════════════════════════
# Verificación final
# ═══════════════════════════════════════════════════════════
print()
print('Verificación:')
print(f'   /venv: {"✅ existe" if (RAIZ / "venv").exists() else "❌ FALTA"}')
print(f'   .local: {"✅ existe" if (RAIZ / ".local").exists() else "❌ FALTA"}')
print(f'   db.sqlite3: {"✅ existe" if (RAIZ / "db.sqlite3").exists() else "❌ FALTA"}')

r = subprocess.run(['df', '-h', str(RAIZ)], capture_output=True, text=True)
print()
print(r.stdout)

# Test importar Django
print('Test de importación Django...')
r = subprocess.run(
    [str(RAIZ / 'venv' / 'bin' / 'python'), '-c', 'import django; print("Django", django.VERSION)'],
    cwd=str(RAIZ), capture_output=True, text=True,
)
print(f'   {r.stdout.strip() or r.stderr.strip()}')
