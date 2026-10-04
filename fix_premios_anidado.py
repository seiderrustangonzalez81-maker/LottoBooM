# -*- coding: utf-8 -*-
"""Premios en cuadre: sorteo → clientes (toggle anidado)."""
import shutil, datetime, re, py_compile
from pathlib import Path

TS = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
SERV = Path('/home/LottoBooM/roles/services.py')
TPL = Path('/home/LottoBooM/roles/templates/roles/cuadre_diario.html')

# ═══════════════════════════════════════════════════════════
# 1. services.py — enriquecer premios_por_sorteo con clientes
# ═══════════════════════════════════════════════════════════
print('=' * 70)
print('1. services.py — premios con clientes por sorteo')
print('=' * 70)

s = SERV.read_text(encoding='utf-8')
orig = s

viejo_p = """        premios_por_sorteo = {}
        for fp_id, sort_dict in premios_por_fp_sorteo.items():
            premios_por_sorteo[fp_id] = [
                {'sorteo': sorteos.get(sid), 'monto': m}
                for sid, m in sorted(sort_dict.items(), key=lambda x: -x[1])
                if m > 0
            ]"""

nuevo_p = """        # FIX_PREMIOS_ANIDADO: enriquecer con clientes por sorteo
        premios_por_sorteo = {}
        # Agrupar por (fp, sorteo, cliente)
        premios_por_fp_sorteo_cliente = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
        for j in jugadas:
            if j.estado == 'ganadora' and j.monto_premio and j.forma_pago_id:
                premios_por_fp_sorteo_cliente[j.forma_pago_id][j.sorteo_id][j.usuario_id] += j.monto_premio

        for fp_id, sort_dict in premios_por_fp_sorteo.items():
            items = []
            for sid, m in sorted(sort_dict.items(), key=lambda x: -x[1]):
                if m <= 0:
                    continue
                # Clientes de este sorteo en esta FP
                cli_dict = premios_por_fp_sorteo_cliente.get(fp_id, {}).get(sid, {})
                clientes = []
                for uid, monto_cli in sorted(cli_dict.items(), key=lambda x: -x[1]):
                    u = User.objects.filter(id=uid).first()
                    if u:
                        clientes.append({
                            'cliente': u,
                            'monto': monto_cli,
                        })
                items.append({
                    'sorteo': sorteos.get(sid),
                    'monto': m,
                    'clientes': clientes,
                })
            premios_por_sorteo[fp_id] = items"""

if 'FIX_PREMIOS_ANIDADO' in s:
    print('-- services.py ya parcheado')
elif viejo_p in s:
    s = s.replace(viejo_p, nuevo_p, 1)
    print('OK: premios enriquecidos con clientes')
else:
    print('!! bloque premios_por_sorteo no encontrado')

if s != orig:
    tmp = SERV.with_suffix('.py.chk')
    tmp.write_text(s, encoding='utf-8')
    try:
        py_compile.compile(str(tmp), doraise=True)
        print('OK: sintaxis Python')
    finally:
        tmp.unlink(missing_ok=True)
    bak = SERV.with_suffix(SERV.suffix + '.bak_anid_' + TS)
    shutil.copy2(SERV, bak)
    print(f'Backup: {bak.name}')
    SERV.write_text(s, encoding='utf-8')
    print('GUARDADO services.py')

# ═══════════════════════════════════════════════════════════
# 2. Template — reemplazar bloque Premios
# ═══════════════════════════════════════════════════════════
print()
print('=' * 70)
print('2. Template — premios anidados')
print('=' * 70)

t = TPL.read_text(encoding='utf-8')
orig_t = t

viejo_tpl = """            <!-- FIX_SUBFILAS_DEF: sub-filas Premios por sorteo (toggle) -->
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
            {% endfor %}"""

nuevo_tpl = """            <!-- FIX_PREMIOS_ANIDADO: sorteo → clientes -->
            {% for fp_id, lista in control.premios_por_sorteo.items %}
              {% for item in lista %}
                {# Nivel 1: sorteo #}
                <tr class="row-transferencia subfila-premios row-toggleable-sorteo"
                    data-sorteo-target="subpremios-{{ fp_id }}-{{ item.sorteo.id }}"
                    style="display:none;">
                  <td class="td-sub">
                    <span class="toggle-icon-sorteo">▶</span>
                    ↳ <strong>{{ item.sorteo.nombre }}</strong> · ${{ item.monto|floatformat:2 }}
                    {% if item.clientes %}<span class="badge-count-sub">{{ item.clientes|length }}</span>{% endif %}
                  </td>
                  {% for _fp, _ in control.fondo_inicial.items %}<td></td>{% endfor %}
                  <td></td>
                </tr>
                {# Nivel 2: clientes dentro del sorteo #}
                {% for c in item.clientes %}
                  <tr class="row-transferencia subfila-premios-cliente subpremios-{{ fp_id }}-{{ item.sorteo.id }}"
                      style="display:none;">
                    <td class="td-sub td-sub-2">
                      ↳↳ {{ c.cliente.username }} · ${{ c.monto|floatformat:2 }}
                    </td>
                    {% for _fp, _ in control.fondo_inicial.items %}<td></td>{% endfor %}
                    <td></td>
                  </tr>
                {% endfor %}
              {% endfor %}
            {% endfor %}"""

if 'FIX_PREMIOS_ANIDADO' in t:
    print('-- template ya parcheado')
elif viejo_tpl in t:
    t = t.replace(viejo_tpl, nuevo_tpl, 1)
    print('OK: bloque Premios anidado')
else:
    print('!! bloque premios template no encontrado')

# ═══════════════════════════════════════════════════════════
# 3. CSS para el toggle anidado
# ═══════════════════════════════════════════════════════════
viejo_css = """  /* Sub-filas animadas */
  .row-transferencia{
    animation: rowFadeIn .2s ease;
  }"""

nuevo_css = """  /* FIX_PREMIOS_ANIDADO: toggle anidado */
  .row-toggleable-sorteo{
    cursor: pointer;
  }
  .row-toggleable-sorteo:hover td{
    background: rgba(244,63,94,0.06) !important;
  }
  .toggle-icon-sorteo{
    display: inline-block;
    width: 12px;
    color: #e11d48;
    font-size: .65rem;
    transition: transform .2s;
    margin-right: 2px;
  }
  .row-toggleable-sorteo.open .toggle-icon-sorteo{
    transform: rotate(90deg);
  }
  .badge-count-sub{
    background: #fee2e2;
    color: #991b1b;
    font-size: .62rem;
    padding: 0 6px;
    border-radius: 20px;
    font-weight: 800;
    margin-left: 6px;
    border: 1px solid #fecaca;
  }
  .td-sub-2{
    padding-left: 70px !important;
    color: #64748b !important;
    font-style: italic;
  }

  /* Sub-filas animadas */
  .row-transferencia{
    animation: rowFadeIn .2s ease;
  }"""

if 'FIX_PREMIOS_ANIDADO: toggle anidado' in t:
    print('-- CSS ya estaba')
elif viejo_css in t:
    t = t.replace(viejo_css, nuevo_css, 1)
    print('OK: CSS toggle anidado')
else:
    print('-- bloque CSS no encontrado')

# ═══════════════════════════════════════════════════════════
# 4. JS para el toggle anidado
# ═══════════════════════════════════════════════════════════
viejo_js = """  // FIX_CUADRE_TOGGLE_VISUAL: toggle sub-filas Ventas/Premios
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
  });"""

nuevo_js = """  // FIX_CUADRE_TOGGLE_VISUAL: toggle sub-filas Ventas/Premios
  document.addEventListener('click', function(e) {
    // FIX_PREMIOS_ANIDADO: toggle por sorteo (nivel 2) — debe ir PRIMERO para capturar
    const rowSorteo = e.target.closest('.row-toggleable-sorteo');
    if (rowSorteo) {
      if (e.target.closest('button')) return;
      const targetSub = rowSorteo.dataset.sorteoTarget;
      if (!targetSub) return;
      const abrir = !rowSorteo.classList.contains('open');
      rowSorteo.classList.toggle('open', abrir);
      document.querySelectorAll('.' + targetSub).forEach(function(sf){
        if (abrir){
          sf.style.removeProperty('display');
          sf.style.display = 'table-row';
        } else {
          sf.style.display = 'none';
        }
      });
      // Si cerramos este sorteo, cerramos también su toggle padre si todos cerrados
      return;
    }

    // Toggle padre (Ventas/Premios)
    const row = e.target.closest('.row-toggleable');
    if (!row) return;
    if (e.target.closest('button')) return;
    const target = row.dataset.target;
    if (!target) return;
    const abrirPadre = !row.classList.contains('open');
    row.classList.toggle('open', abrirPadre);
    const subfilas = document.querySelectorAll('tr.' + target);
    subfilas.forEach(function(sf){
      if (abrirPadre){
        sf.style.removeProperty('display');
        sf.style.display = 'table-row';
      } else {
        sf.style.display = 'none';
      }
    });
    // Si cerramos Premios, cerrar todos los sub-toggles de sorteos
    if (!abrirPadre){
      document.querySelectorAll('.row-toggleable-sorteo.open').forEach(function(rs){
        rs.classList.remove('open');
        const sub = rs.dataset.sorteoTarget;
        if (sub){
          document.querySelectorAll('.' + sub).forEach(function(sf){
            sf.style.display = 'none';
          });
        }
      });
    }
  });"""

if 'FIX_PREMIOS_ANIDADO: toggle por sorteo' in t:
    print('-- JS ya estaba')
elif viejo_js in t:
    t = t.replace(viejo_js, nuevo_js, 1)
    print('OK: JS toggle anidado')
else:
    print('-- bloque JS no encontrado')

if t != orig_t:
    bak = TPL.with_suffix(TPL.suffix + '.bak_anid_' + TS)
    shutil.copy2(TPL, bak)
    print(f'Backup: {bak.name}')
    TPL.write_text(t, encoding='utf-8')
    print('GUARDADO template')

print()
print('FIX_PREMIOS_ANIDADO COMPLETO')
