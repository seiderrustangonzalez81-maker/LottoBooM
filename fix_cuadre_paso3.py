# -*- coding: utf-8 -*-
"""Fixes: modal JS + comercial ve fecha + auto-submit cuadre + verificar endpoint."""
import shutil, datetime, sys
from pathlib import Path

TS = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
RAIZ = Path('/home/LottoBooM')

# ═══════════════════════════════════════════════════════════
# FIX 1 — Modal JS: tipo correcto + llave extra
# ═══════════════════════════════════════════════════════════
print('=' * 70)
print('1. Template — fix modal JS')
print('=' * 70)

TPL = RAIZ / 'roles' / 'templates' / 'roles' / 'cuadre_diario.html'
t = TPL.read_text(encoding='utf-8')
orig = t

viejo_modal = '''    if (t.id === 'cd-modal-ok') {
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
    }
      }
      if (res.success) location.reload();
      else alert('Error: ' + res.error);
      return;
    }'''

nuevo_modal = '''    if (t.id === 'cd-modal-ok') {
      // FIX_MODAL_JS: usa editMode.tipo o window.__lastAddTipo (ambos seguros)
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
    }'''

if 'FIX_MODAL_JS' in t:
    print('  -- modal ya parcheado')
elif viejo_modal in t:
    t = t.replace(viejo_modal, nuevo_modal, 1)
    print('  OK: modal JS reescrito')
else:
    print('  !! bloque modal no encontrado (¿el JS cambió?)')

# ═══════════════════════════════════════════════════════════
# FIX 2 — Guardar tipo al abrir modal (mousedown → click)
# ═══════════════════════════════════════════════════════════
viejo_click = '''    if (t.classList.contains('cd-btn-add')) {
      e.preventDefault();
      const tipo = t.dataset.tipo;
      abrirModal(tipo);
      return;
    }'''

nuevo_click = '''    if (t.classList.contains('cd-btn-add')) {
      e.preventDefault();
      const tipo = t.dataset.tipo;
      // FIX_MODAL_JS: guardar tipo para usarlo al guardar
      window.__lastAddTipo = tipo;
      abrirModal(tipo);
      return;
    }'''

if 'FIX_MODAL_JS: guardar tipo' in t:
    print('  -- guardar tipo ya estaba')
elif viejo_click in t:
    t = t.replace(viejo_click, nuevo_click, 1)
    print('  OK: guardar tipo al abrir modal')
else:
    print('  !! bloque click-add no encontrado')

if t != orig:
    bak = TPL.with_suffix(TPL.suffix + '.bak_p3_' + TS)
    shutil.copy2(TPL, bak)
    print(f'  Backup: {bak.name}')
    TPL.write_text(t, encoding='utf-8')
    print('  GUARDADO')

# ═══════════════════════════════════════════════════════════
# FIX 3 — Comercial ve selector de fecha + auto-submit + quitar botón
# ═══════════════════════════════════════════════════════════
print()
print('=' * 70)
print('2. Template — filtros: comercial ve fecha + auto-submit')
print('=' * 70)

t = TPL.read_text(encoding='utf-8')
orig = t

# 2a. Cambiar el {% if es_banco or es_superadmin %} → agregar comercial
viejo_if = '''  {% if es_banco or es_superadmin %}
  <form method="get" class="cd-filters">'''

nuevo_if = '''  {# FIX_FILTROS_DINAMICOS: comercial solo ve fecha, banco y superadmin ven todo #}
  {% if es_banco or es_superadmin or es_comercial %}
  <form method="get" class="cd-filters" id="cdFilters">'''

if 'FIX_FILTROS_DINAMICOS' in t:
    print('  -- filtros ya parcheados')
elif viejo_if in t:
    t = t.replace(viejo_if, nuevo_if, 1)
    print('  OK: incluir comercial en filtros')
else:
    print('  !! bloque if no encontrado')

# 2b. Envolver Banco select en {% if es_superadmin %} — ya está
# 2c. Envolver Comercial select en {% if es_banco or es_superadmin %}
viejo_com = '''    <div class="fgrp">
      <label>Comercial</label>
      <select name="comercial_id" onchange="this.form.submit()">
        <option value="">-- Yo mismo --</option>
        {% for c in comerciales %}
          <option value="{{ c.id }}" {% if comercial_seleccionado and comercial_seleccionado.id == c.id %}selected{% endif %}>
            {{ c.get_full_name|default:c.username }}
          </option>
        {% endfor %}
      </select>
    </div>'''

nuevo_com = '''    {% if es_banco or es_superadmin %}
    <div class="fgrp">
      <label>Comercial</label>
      <select name="comercial_id" onchange="this.form.submit()">
        <option value="">-- Yo mismo --</option>
        {% for c in comerciales %}
          <option value="{{ c.id }}" {% if comercial_seleccionado and comercial_seleccionado.id == c.id %}selected{% endif %}>
            {{ c.get_full_name|default:c.username }}
          </option>
        {% endfor %}
      </select>
    </div>
    {% endif %}'''

if nuevo_com in t or 'label>Comercial' in t:
    if 'FIX_FILTROS_DINAMICOS: comercial oculto' in t:
        print('  -- comercial select ya condicionado')
    elif viejo_com in t:
        t = t.replace(viejo_com, nuevo_com.replace('{% if es_banco or es_superadmin %}', '{% if es_banco or es_superadmin %}{# FIX_FILTROS_DINAMICOS: comercial oculto #}'), 1)
        print('  OK: comercial select solo para banco/superadmin')

# 2d. Fecha con auto-submit + quitar botón Aplicar
viejo_fecha = '''    <div class="fgrp">
      <label>Fecha</label>
      <input type="date" name="fecha" value="{{ fecha|date:'Y-m-d' }}">
    </div>
    <button type="submit">Aplicar</button>
  </form>'''

nuevo_fecha = '''    <div class="fgrp">
      <label>Fecha</label>
      <input type="date" name="fecha" value="{{ fecha|date:'Y-m-d' }}" onchange="this.form.submit()">
    </div>
    {# FIX_FILTROS_DINAMICOS: botón eliminado (auto-submit) #}
  </form>'''

if 'FIX_FILTROS_DINAMICOS: botón eliminado' in t:
    print('  -- fecha + botón ya parcheados')
elif viejo_fecha in t:
    t = t.replace(viejo_fecha, nuevo_fecha, 1)
    print('  OK: fecha auto-submit + botón eliminado')
else:
    print('  !! bloque fecha+botón no encontrado')

if t != orig:
    bak = TPL.with_suffix(TPL.suffix + '.bak_p3b_' + TS)
    shutil.copy2(TPL, bak)
    print(f'  Backup: {bak.name}')
    TPL.write_text(t, encoding='utf-8')
    print('  GUARDADO')

# ═══════════════════════════════════════════════════════════
# FIX 4 — Vista: comercial puede filtrar por fecha
# ═══════════════════════════════════════════════════════════
print()
print('=' * 70)
print('3. Vista cuadre_diario_view — comercial usa fecha del GET')
print('=' * 70)

VIEWS = RAIZ / 'roles' / 'views.py'
v = VIEWS.read_text(encoding='utf-8')
orig_v = v

viejo_c = '''    if es_comercial:
        # FIX_CUADRE_FILTROS_V1: el comercial solo ve su propio cuadre,
        # ignora cualquier query param de banco/comercial.
        context.update(CuadreService.generar_cuadre_completo(usuario_actual, fecha))
        context["vista"] = "comercial"
        context["bancos"] = User.objects.none()
        context["comerciales"] = User.objects.none()
        return render(request, "roles/cuadre_diario.html", context)'''

nuevo_c = '''    if es_comercial:
        # FIX_FILTROS_DINAMICOS: comercial solo ve su cuadre, pero puede cambiar fecha
        context.update(CuadreService.generar_cuadre_completo(usuario_actual, fecha))
        context["vista"] = "comercial"
        context["bancos"] = User.objects.none()
        context["comerciales"] = User.objects.none()
        return render(request, "roles/cuadre_diario.html", context)'''

if 'FIX_FILTROS_DINAMICOS: comercial solo ve' in v:
    print('  -- vista comercial ya ok')
elif viejo_c in v:
    v = v.replace(viejo_c, nuevo_c, 1)
    print('  OK: vista comercial comentario actualizado (sin cambio funcional)')
else:
    print('  -- bloque comercial no encontrado o ya estaba OK')

if v != orig_v:
    bak = VIEWS.with_suffix(VIEWS.suffix + '.bak_p3_' + TS)
    shutil.copy2(VIEWS, bak)
    print(f'  Backup: {bak.name}')
    VIEWS.write_text(v, encoding='utf-8')
    print('  GUARDADO')

# ═══════════════════════════════════════════════════════════
# FIX 5 — Verificar endpoint agregar_transferencia
# ═══════════════════════════════════════════════════════════
print()
print('=' * 70)
print('4. Verificación endpoint agregar_transferencia')
print('=' * 70)

import subprocess
r = subprocess.run(['grep', '-n', 'def agregar_transferencia', str(VIEWS)],
                   capture_output=True, text=True)
if r.stdout:
    print(f'  {r.stdout.strip()}')
else:
    print('  !! no encontrado')

print()
print('PASO 3 COMPLETO')
