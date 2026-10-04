# -*- coding: utf-8 -*-
"""
Limpieza de archivos temporales.
DRY-RUN por defecto. Escribe 'si' al final para aplicar.
NUNCA toca: código de apps, db.sqlite3, manage.py, settings, requirements.
"""
import os, sys
from pathlib import Path

RAIZ = Path('/home/LottoBooM')

# ═══════════════════════════════════════════════════════════
# GRUPOS A BORRAR
# ═══════════════════════════════════════════════════════════

# A. JSONs de backup viejos
grupo_json = ['data.json', 'backup.json', 'backup.sql',
              'backup_completo_20260904.json', 'backup_data.json',
              'backup_negocio.json', 'backup_jugadas_20260920_153130.json']

# B. Backups de BD viejos (por si acaso)
grupo_db_bak = [p for p in RAIZ.glob('db.sqlite3.bak_*')]

# C. Backups de código (.bak_*) de ANTES de hoy
hoy = '20260929'
grupo_code_bak = []
for p in RAIZ.rglob('*.bak_*'):
    if not p.is_file():
        continue
    if hoy not in p.name:  # conservar los de hoy
        grupo_code_bak.append(p)

# D. Scripts de hoy ya aplicados (conservar revertir_y_recalcular.py y reconciliar_ya.py)
grupo_scripts = []
for p in RAIZ.glob('*.py'):
    if not p.is_file():
        continue
    n = p.name
    # Scripts de esta sesión
    if n.startswith(('fix_', 'fase1_', 'fase1b_', 'paso', 'diag_', 'aplicar_',
                     'listar_', 'asignar_rol_', 'quitar_pick4_', 'urgencia_',
                     'inventario_', 'plan_revertir_', 'debug_', 'limpiar_duplicado')):
        grupo_scripts.append(p)

# E. Scripts .sh de septiembre (ya aplicados)
grupo_sh = []
for p in RAIZ.glob('*.sh'):
    if p.is_file():
        grupo_sh.append(p)

# F. TXTs de análisis viejos
grupo_txt = [
    'auditoria_templates_20260922_195431.txt',
    'auditoria_templates_20260922_200113.txt',
    'clasificacion_templates_20260922_200412.txt',
    'templates_basura.txt',
    'templates_huerfanos.txt',
    'templates_usados.txt',
    'analisis_contexto_20260922_205708.txt',
    'verificacion_exacta_205934.txt',
    'cleanup_templates_20260922_204431.log',
]

# G. Basura
grupo_basura = ['0', 'span:first-child{']

# ═══════════════════════════════════════════════════════════
# CALCULAR TAMAÑOS
# ═══════════════════════════════════════════════════════════
def size_of(items):
    total = 0
    for it in items:
        p = RAIZ / it if isinstance(it, str) else it
        if p.is_file():
            total += p.stat().st_size
    return total

grupos = [
    ('A. JSONs de backup viejos', [RAIZ / n for n in grupo_json if (RAIZ / n).exists()]),
    ('B. Backups de BD viejos', grupo_db_bak),
    ('C. Backups de código (.bak_* viejos)', grupo_code_bak),
    ('D. Scripts .py de esta sesión ya aplicados', grupo_scripts),
    ('E. Scripts .sh de septiembre', grupo_sh),
    ('F. TXTs de análisis viejos', [RAIZ / n for n in grupo_txt if (RAIZ / n).exists()]),
    ('G. Basura', [RAIZ / n for n in grupo_basura if (RAIZ / n).exists()]),
]

print('=' * 78)
print('LIMPIEZA DE TEMPORALES — DRY RUN')
print('=' * 78)
print()

gran_total = 0
todos = []
for nombre, items in grupos:
    if not items:
        continue
    t = size_of(items)
    gran_total += t
    todos.extend(items)
    print(f'{nombre}: {len(items)} archivos — {t/1024:.1f} KB')

print()
print('=' * 78)
print(f'TOTAL A LIBERAR: {gran_total/1024/1024:.2f} MB')
print(f'TOTAL ARCHIVOS: {len(todos)}')
print('=' * 78)
print()

# ═══════════════════════════════════════════════════════════
# CONFIRMACIÓN
# ═══════════════════════════════════════════════════════════
resp = input('¿Aplicar limpieza? (si/no): ').strip().lower()
if resp != 'si':
    print('Cancelado.')
    raise SystemExit(0)

borrados = 0
errores = 0
for p in todos:
    try:
        p.unlink()
        borrados += 1
    except Exception as e:
        errores += 1
        print(f'  ERROR borrando {p}: {e}')

print()
print(f'✅ Borrados: {borrados}')
print(f'⚠️  Errores: {errores}')

# Verificar espacio
import subprocess
r = subprocess.run(['df', '-h', str(RAIZ)], capture_output=True, text=True)
print()
print(r.stdout)

# Verificar BD
db = RAIZ / 'db.sqlite3'
if db.exists():
    print(f'✅ db.sqlite3 INTACTA: {db.stat().st_size/1024/1024:.2f} MB')
else:
    print('❌ ALERTA: db.sqlite3 NO EXISTE')
