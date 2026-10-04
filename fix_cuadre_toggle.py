# -*- coding: utf-8 -*-
"""Toggle sub-filas Ventas/Premios + mejoras visuales."""
import shutil, datetime
from pathlib import Path

TS = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
TPL = Path('/home/LottoBooM/roles/templates/roles/cuadre_diario.html')

t = TPL.read_text(encoding='utf-8')
orig = t

# ═══════════════════════════════════════════════════════════
# 1. Ventas — añadir botón toggle + clase "subfila-ventas"
# ═══════════════════════════════════════════════════════════
viejo_v = '''            <!-- VENTAS -->
            <tr>
              <td>Ventas</td>
              {% for fp_nombre, valor in control.ventas.items %}
                <td>{% if valor %}{{ valor|floatformat:2|intcomma }}{% endif %}</td>
              {% endfor %}
              <td class="col-total">{{ resumen.total_recogido|floatformat:2|intcomma }}</td>
            </tr>'''

nuevo_v = '''            <!-- VENTAS -->
            <tr class="row-toggleable" data-target="subfila-ventas">
              <td>
                <span class="toggle-icon">▶</span>
                Ventas
              </td>
              {% for fp_nombre, valor in control.ventas.items %}
                <td>{% if valor %}{{ valor|floatformat:2|intcomma }}{% endif %}</td>
              {% endfor %}
              <td class="col-total">{{ resumen.total_recogido|floatformat:2|intcomma }}</td>
            </tr>'''

if 'row-toggleable' in t and 'subfila-ventas' in t:
    print('-- toggle Ventas ya estaba')
elif viejo_v in t:
    t = t.replace(viejo_v, nuevo_v, 1)
    print('OK: toggle en fila Ventas')
else:
    print('!! bloque VENTAS no encontrado')

# ═══════════════════════════════════════════════════════════
# 2. Sub-filas Ventas → añadir clase + ocultas por defecto
# ═══════════════════════════════════════════════════════════
viejo_vs = '''            <!-- FIX_CUADRE_SUBFILAS: sub-filas Ventas por sorteo -->
            {% for fp_nombre, _ in control.fondo_inicial.items %}
              {% for fp_id, lista in control.ventas_por_sorteo.items %}
                {% for item in lista %}
                  <tr class="row-transferencia">
                    <td class="td-sub">
                      ↳ {{ item.sorteo.nombre }} · ${{ item.monto|floatformat:2 }}
                    </td>
                    {% for _fp, _ in control.fondo_inicial.items %}<td></td>{% endfor %}
                    <td></td>
                  </tr>
                {% endfor %}
              {% endfor %}
            {% endfor %}'''

nuevo_vs = '''            <!-- FIX_CUADRE_SUBFILAS: sub-filas Ventas por sorteo (toggle) -->
            {% for fp_nombre, _ in control.fondo_inicial.items %}
              {% for fp_id, lista in control.ventas_por_sorteo.items %}
                {% for item in lista %}
                  <tr class="row-transferencia subfila-ventas" style="display:none;">
                    <td class="td-sub">
                      ↳ {{ item.sorteo.nombre }} · ${{ item.monto|floatformat:2 }}
                    </td>
                    {% for _fp, _ in control.fondo_inicial.items %}<td></td>{% endfor %}
                    <td></td>
                  </tr>
                {% endfor %}
              {% endfor %}
            {% endfor %}'''

if 'subfila-ventas' in t and 'style="display:none;"' in t and 'FIX_CUADRE_SUBFILAS: sub-filas Ventas por sorteo (toggle)' in t:
    print('-- sub-filas Ventas ya tenían toggle')
elif viejo_vs in t:
    t = t.replace(viejo_vs, nuevo_vs, 1)
    print('OK: sub-filas Ventas ocultas por defecto')
else:
    print('!! bloque sub-filas Ventas no encontrado')

# ═══════════════════════════════════════════════════════════
# 3. Premios — añadir botón toggle
# ═══════════════════════════════════════════════════════════
viejo_p = '''            <!-- PREMIOS -->
            <tr class="row-premios">
              <td>Premios</td>
              {% for fp_nombre, valor in control.premios.items %}
                <td>− {{ valor|floatformat:2|intcomma }}</td>
              {% endfor %}
              <td class="col-total">− {{ resumen.premios|floatformat:2|intcomma }}</td>
            </tr>'''

nuevo_p = '''            <!-- PREMIOS -->
            <tr class="row-premios row-toggleable" data-target="subfila-premios">
              <td>
                <span class="toggle-icon">▶</span>
                Premios
              </td>
              {% for fp_nombre, valor in control.premios.items %}
                <td>− {{ valor|floatformat:2|intcomma }}</td>
              {% endfor %}
              <td class="col-total">− {{ resumen.premios|floatformat:2|intcomma }}</td>
            </tr>'''

if 'row-toggleable' in t and 'subfila-premios' in t:
    print('-- toggle Premios ya estaba')
elif viejo_p in t:
    t = t.replace(viejo_p, nuevo_p, 1)
    print('OK: toggle en fila Premios')
else:
    print('!! bloque PREMIOS no encontrado')

# ═══════════════════════════════════════════════════════════
# 4. Sub-filas Premios → añadir clase + ocultas
# ═══════════════════════════════════════════════════════════
viejo_ps = '''            <!-- FIX_CUADRE_SUBFILAS: sub-filas Premios por sorteo (solo > 0) -->
            {% for fp_nombre, _ in control.fondo_inicial.items %}
              {% for fp_id, lista in control.premios_por_sorteo.items %}
                {% for item in lista %}
                  <tr class="row-transferencia">
                    <td class="td-sub">
                      ↳ {{ item.sorteo.nombre }} · ${{ item.monto|floatformat:2 }}
                    </td>
                    {% for _fp, _ in control.fondo_inicial.items %}<td></td>{% endfor %}
                    <td></td>
                  </tr>
                {% endfor %}
              {% endfor %}
            {% endfor %}'''

nuevo_ps = '''            <!-- FIX_CUADRE_SUBFILAS: sub-filas Premios por sorteo (toggle) -->
            {% for fp_nombre, _ in control.fondo_inicial.items %}
              {% for fp_id, lista in control.premios_por_sorteo.items %}
                {% for item in lista %}
                  <tr class="row-transferencia subfila-premios" style="display:none;">
                    <td class="td-sub">
                      ↳ {{ item.sorteo.nombre }} · ${{ item.monto|floatformat:2 }}
                    </td>
                    {% for _fp, _ in control.fondo_inicial.items %}<td></td>{% endfor %}
                    <td></td>
                  </tr>
                {% endfor %}
              {% endfor %}
            {% endfor %}'''

if 'subfila-premios' in t and 'FIX_CUADRE_SUBFILAS: sub-filas Premios por sorteo (toggle)' in t:
    print('-- sub-filas Premios ya tenían toggle')
elif viejo_ps in t:
    t = t.replace(viejo_ps, nuevo_ps, 1)
    print('OK: sub-filas Premios ocultas por defecto')
else:
    print('!! bloque sub-filas Premios no encontrado')

# ═══════════════════════════════════════════════════════════
# 5. CSS — mejoras visuales + toggle-icon
# ═══════════════════════════════════════════════════════════
viejo_css = '''  @media (max-width: 640px){
    .cd-table thead th,
    .cd-table tbody td{
      padding: 6px 8px !important;
      font-size: 13px !important;
    }'''

nuevo_css = '''  /* FIX_CUADRE_TOGGLE_VISUAL: mejoras visuales */
  .row-toggleable{
    cursor: pointer;
    transition: background .15s;
  }
  .row-toggleable:hover td{
    background: rgba(45, 212, 191, 0.08) !important;
  }
  .row-toggleable .toggle-icon{
    display: inline-block;
    width: 14px;
    color: #14b8a6;
    font-size: .75rem;
    transition: transform .2s;
    margin-right: 4px;
  }
  .row-toggleable.open .toggle-icon{
    transform: rotate(90deg);
  }

  /* Sub-filas animadas */
  .row-transferencia{
    animation: rowFadeIn .2s ease;
  }
  @keyframes rowFadeIn{
    from { opacity: 0; transform: translateY(-4px); }
    to   { opacity: 1; transform: translateY(0); }
  }

  /* Badges de resumen mejorados */
  .cd-resumen-item{
    transition: transform .15s, box-shadow .15s;
  }
  .cd-resumen-item:hover{
    transform: translateY(-2px);
    box-shadow: 0 6px 16px rgba(0,0,0,.08);
  }

  /* Fila FONDO FINAL destacada */
  .cd-table tr.row-total td{
    background: linear-gradient(90deg, rgba(45,212,191,0.12), rgba(45,212,191,0.05)) !important;
    font-size: 1.05em;
  }

  /* Fila Ventas destacada sutilmente */
  .cd-table tr:not(.row-transferencia):not(.row-total):not(.row-premios):not(.row-recibi):not(.row-envie):not(.row-ajuste):not(.row-neto):not(.row-comision):not(.row-fondo-inicial) td{
    background: rgba(45,212,191,0.03);
  }

  @media (max-width: 640px){
    .cd-table thead th,
    .cd-table tbody td{
      padding: 6px 8px !important;
      font-size: 13px !important;
    }'''

if 'FIX_CUADRE_TOGGLE_VISUAL' in t:
    print('-- CSS toggle/visual ya estaba')
elif viejo_css in t:
    t = t.replace(viejo_css, nuevo_css, 1)
    print('OK: CSS toggle + visual')
else:
    print('!! bloque CSS móvil no encontrado (¿cambió?)')

# ═══════════════════════════════════════════════════════════
# 6. JS — handler de toggle
# ═══════════════════════════════════════════════════════════
viejo_js = '''  // Guardar tipo del add pulsado
  document.addEventListener('mousedown', function(e) {
    if (e.target.classList.contains('cd-btn-add')) {
      window.__lastAddTipo = e.target.dataset.tipo;
    }
  });
})();'''

nuevo_js = '''  // Guardar tipo del add pulsado
  document.addEventListener('mousedown', function(e) {
    if (e.target.classList.contains('cd-btn-add')) {
      window.__lastAddTipo = e.target.dataset.tipo;
    }
  });

  // FIX_CUADRE_TOGGLE_VISUAL: toggle sub-filas Ventas/Premios
  document.addEventListener('click', function(e) {
    const row = e.target.closest('.row-toggleable');
    if (!row) return;
    // Ignorar si el click fue en botón (evitar conflicto)
    if (e.target.closest('button')) return;
    const target = row.dataset.target;
    if (!target) return;
    row.classList.toggle('open');
    const subfilas = document.querySelectorAll('.' + target);
    subfilas.forEach(function(sf){
      sf.style.display = (sf.style.display === 'none' || !sf.style.display) ? 'table-row' : 'none';
    });
  });
})();'''

if 'FIX_CUADRE_TOGGLE_VISUAL: toggle sub-filas' in t:
    print('-- JS toggle ya estaba')
elif viejo_js in t:
    t = t.replace(viejo_js, nuevo_js, 1)
    print('OK: JS toggle añadido')
else:
    print('!! bloque JS final no encontrado')

if t == orig:
    print()
    print('Sin cambios')
else:
    bak = TPL.with_suffix(TPL.suffix + '.bak_toggle_' + TS)
    shutil.copy2(TPL, bak)
    print(f'Backup: {bak.name}')
    TPL.write_text(t, encoding='utf-8')
    print('GUARDADO')
    print()
    print('FIX_CUADRE_TOGGLE COMPLETO')
