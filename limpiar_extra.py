# -*- coding: utf-8 -*-
"""Limpieza de archivos sueltos en la raíz que ya no se usan."""
from pathlib import Path
import subprocess

RAIZ = Path('/home/LottoBooM')

a_borrar = [
    'settings.py',                          # 0 bytes, vacío
    '_nuevo_gestion_limites.py',
    'actualizar_bd.py',
    'asignar_herencia_existentes.py',
    'cargar_bonos_existentes.py',
    'corregir_api_sorteos.py',
    'corregir_matriz.py',
    'diag2_notif.py',
    'eliminar_superparlet.py',
    'fase2_crear.py',
    'fase3_defaults.py',
    'fase4_cargar.py',
    'fase4_dryrun.py',
    'forzar_unificacion.py',
    'mejorar_gestion_limites.py',
    'optimizar_layout_apostar.py',
    'patcher_views.py',
]

print('=' * 78)
print('LIMPIEZA EXTRA — DRY RUN')
print('=' * 78)

items = []
total = 0
for n in a_borrar:
    p = RAIZ / n
    if p.is_file():
        s = p.stat().st_size
        total += s
        items.append(p)
        print(f'  {n} ({s/1024:.1f} KB)')

print()
print(f'Total: {len(items)} archivos — {total/1024:.1f} KB')
print()

resp = input('¿Aplicar? (si/no): ').strip().lower()
if resp != 'si':
    print('Cancelado.')
    raise SystemExit(0)

borrados = 0
for p in items:
    try:
        p.unlink()
        borrados += 1
    except Exception as e:
        print(f'  ERROR: {p}: {e}')

print()
print(f'✅ Borrados: {borrados}')
r = subprocess.run(['df', '-h', str(RAIZ)], capture_output=True, text=True)
print(r.stdout)

db = RAIZ / 'db.sqlite3'
if db.exists():
    print(f'✅ db.sqlite3 INTACTA: {db.stat().st_size/1024/1024:.2f} MB')
