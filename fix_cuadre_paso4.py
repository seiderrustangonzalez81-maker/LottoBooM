# -*- coding: utf-8 -*-
"""Fix del modal JS roto + verificar permisos banco→comercial."""
import shutil, datetime, subprocess
from pathlib import Path

TS = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
RAIZ = Path('/home/LottoBooM')

# ═══════════════════════════════════════════════════════════
# 1. Fix del bloque modal roto
# ═══════════════════════════════════════════════════════════
print('=' * 70)
print('1. Fix modal JS')
print('=' * 70)

TPL = RAIZ / 'roles' / 'templates' / 'roles' / 'cuadre_diario.html'
t = TPL.read_text(encoding='utf-8')
orig = t

viejo = """    if (t.id === 'cd-modal-ok') {
      const tipo = editMode ? editMode.tipo : document.querySelector('.cd-btn-add:focus')?.dataset.tipo;
      const fp = modalFp.value;
      const monto = parseFloat(modalMonto.value);
      if (!tipo || !fp || isNaN(monto) || monto <= 0) {
        alert('Datos inválidos');
        return;
      }
      let res;
      if (editMode) {
        const url = URLS.editar.replace('INDEX', editMode.idx);
        res = await postJson(url, {tipo, forma_pago: fp, monto});
      } else {
        // Detectar tipo del último botón clickeado
        const ultBtn = window.__lastAddTipo || 'envie';
        res = await postJson(URLS.agregar, {tipo: ultBtn, forma_pago: fp, monto});
            return JsonResponse({'success': False, 'error': 'Sin permiso'}, status=403)
      }
      if (res.success) location.reload();
      else alert('Error: ' + res.error);
      return;
    }"""

nuevo = """    if (t.id === 'cd-modal-ok') {
      // FIX_MODAL_JS: usa editMode.tipo o window.__lastAddTipo
      const tipo = editMode ? editMode.tipo : (window.__lastAddTipo || 'envie');
      const fp = modalFp.value;
      const monto = parseFloat(modalMonto.value);
      if (!tipo || !fp || isNaN(monto) || monto <= 0) {
        alert('Datos inválidos');
        return;
      }
      let res;
      if (editMode) {
        const url = URLS.editar.replace('INDEX', editMode.idx);
        res = await postJson(url, {tipo, forma_pago: fp, monto});
      } else {
        res = await postJson(URLS.agregar, {tipo, forma_pago: fp, monto});
      }
      if (res && res.success) location.reload();
      else alert('Error: ' + ((res && (res.error || res.message)) || 'desconocido'));
      return;
    }"""

if 'FIX_MODAL_JS: usa editMode.tipo o window.__lastAddTipo' in t:
    print('  -- ya estaba parcheado')
elif viejo in t:
    t = t.replace(viejo, nuevo, 1)
    print('  ✅ modal JS arreglado (línea Python eliminada)')
    bak = TPL.with_suffix(TPL.suffix + '.bak_p4_' + TS)
    shutil.copy2(TPL, bak)
    print(f'  Backup: {bak.name}')
    TPL.write_text(t, encoding='utf-8')
    print('  GUARDADO')
else:
    print('  ❌ bloque no coincidió — revisar manualmente')

# ═══════════════════════════════════════════════════════════
# 2. Verificar _puede_gestionar_cuadre
# ═══════════════════════════════════════════════════════════
print()
print('=' * 70)
print('2. _puede_gestionar_cuadre')
print('=' * 70)

r = subprocess.run(['grep', '-n', 'def _puede_gestionar_cuadre', str(RAIZ / 'roles' / 'views.py')],
                   capture_output=True, text=True)
print(f'  {r.stdout.strip()}')
