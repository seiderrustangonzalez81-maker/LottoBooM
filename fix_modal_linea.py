# -*- coding: utf-8 -*-
"""Elimina la línea Python huérfana dentro del JS + fix tipo."""
import shutil, datetime
from pathlib import Path

TS = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
TPL = Path('/home/LottoBooM/roles/templates/roles/cuadre_diario.html')

t = TPL.read_text(encoding='utf-8')
orig = t

# ═══════════════════════════════════════════════════════════
# 1. Eliminar la línea huérfana Python
# ═══════════════════════════════════════════════════════════
linea_mala = "            return JsonResponse({'success': False, 'error': 'Sin permiso'}, status=403)\n"

if linea_mala in t:
    # Verificar que esté DENTRO de un bloque <script>
    idx = t.index(linea_mala)
    # Buscar el <script> anterior más cercano
    script_open = t.rfind('<script>', 0, idx)
    script_close = t.rfind('</script>', 0, idx)
    if script_open > script_close:
        # sí está dentro de un script
        t = t.replace(linea_mala, "", 1)
        print('OK: línea Python huérfana eliminada del JS')
    else:
        print('!! la línea no está dentro de <script> — abortando')
        raise SystemExit(1)
else:
    print('-- línea huérfana no encontrada (¿ya eliminada?)')

# ═══════════════════════════════════════════════════════════
# 2. Reemplazar la línea del tipo
# ═══════════════════════════════════════════════════════════
linea_tipo_vieja = "      const tipo = editMode ? editMode.tipo : document.querySelector('.cd-btn-add:focus')?.dataset.tipo;"
linea_tipo_nueva = "      const tipo = editMode ? editMode.tipo : (window.__lastAddTipo || 'envie');  // FIX_MODAL_JS"

if 'FIX_MODAL_JS' in t:
    print('-- línea tipo ya parcheada')
elif linea_tipo_vieja in t:
    t = t.replace(linea_tipo_vieja, linea_tipo_nueva, 1)
    print('OK: línea tipo reemplazada')
else:
    print('!! línea tipo no encontrada')

# ═══════════════════════════════════════════════════════════
# 3. Asegurar que el tipo se guarda al abrir el modal (click)
# ═══════════════════════════════════════════════════════════
linea_add_vieja = "      const tipo = t.dataset.tipo;\n      abrirModal(tipo);"
linea_add_nueva = "      const tipo = t.dataset.tipo;\n      window.__lastAddTipo = tipo;  // FIX_MODAL_JS\n      abrirModal(tipo);"

if 'FIX_MODAL_JS\n      abrirModal' in t or ('window.__lastAddTipo = tipo' in t and 'abrirModal(tipo)' in t):
    print('-- guardar tipo ya estaba')
elif linea_add_vieja in t:
    t = t.replace(linea_add_vieja, linea_add_nueva, 1)
    print('OK: guardar tipo al abrir modal')
else:
    print('-- bloque add no encontrado (puede estar ya)')

# ═══════════════════════════════════════════════════════════
# 4. Validar balance de llaves/parens/corch
# ═══════════════════════════════════════════════════════════
import re
blocks = re.findall(r'<script>([\s\S]*?)</script>', t)
if blocks:
    js = blocks[-1]
    b = js.count('{') - js.count('}')
    p = js.count('(') - js.count(')')
    c = js.count('[') - js.count(']')
    print(f'Balance JS: llaves={b} parens={p} corch={c}')
    if b != 0 or p != 0 or c != 0:
        print('!! DESBALANCE — abortar')
        raise SystemExit(1)

# ═══════════════════════════════════════════════════════════
# 5. Guardar
# ═══════════════════════════════════════════════════════════
if t == orig:
    print('Sin cambios')
    raise SystemExit(0)

bak = TPL.with_suffix(TPL.suffix + '.bak_p5_' + TS)
shutil.copy2(TPL, bak)
print(f'Backup: {bak.name}')
TPL.write_text(t, encoding='utf-8')
print('GUARDADO')
print()
print('FIX_MODAL COMPLETO')
