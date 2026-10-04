# -*- coding: utf-8 -*-
"""Fix sub-filas Ventas: endfor mal ubicado + doble loop."""
import shutil, datetime
from pathlib import Path

TS = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
TPL = Path('/home/LottoBooM/roles/templates/roles/cuadre_diario.html')

t = TPL.read_text(encoding='utf-8')
orig = t

# ═══════════════════════════════════════════════════════════
# Fix Ventas — bloque actual roto
# ═══════════════════════════════════════════════════════════
viejo_v = '''            <!-- FIX_CUADRE_SUBFILAS: sub-filas Ventas por sorteo (toggle) -->
            {% for fp_nombre, _ in control.fondo_inicial.items %}
              {% for fp_id, lista in control.ventas_por_sorteo.items %}
                {% for item in lista %}
                  <tr class="row-transferencia subfila-ventas" style="display:none;">
                    <td class="td-sub">
                      ↳ {{ item.sorteo.nombre }} · ${{ item.monto|floatformat:2 }}
              {% endfor %}
                    </td>
                    {% for _fp, _ in control.fondo_inicial.items %}<td></td>{% endfor %}
                    <td></td>
                  </tr>
                {% endfor %}
              {% endfor %}
            {% endfor %}'''

nuevo_v = '''            <!-- FIX_SUBFILAS_DEF: sub-filas Ventas por sorteo (toggle) -->
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
            {% endfor %}'''

if 'FIX_SUBFILAS_DEF: sub-filas Ventas' in t:
    print('-- Ventas ya estaba')
elif viejo_v in t:
    t = t.replace(viejo_v, nuevo_v, 1)
    print('OK: Ventas — endfor mal ubicado + doble loop eliminados')
else:
    print('!! bloque Ventas no encontrado')

# ═══════════════════════════════════════════════════════════
# Fix Premios — mismo patrón (doble loop)
# ═══════════════════════════════════════════════════════════
viejo_p = '''            <!-- FIX_CUADRE_SUBFILAS: sub-filas Premios por sorteo (toggle) -->
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

nuevo_p = '''            <!-- FIX_SUBFILAS_DEF: sub-filas Premios por sorteo (toggle) -->
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
            {% endfor %}'''

if 'FIX_SUBFILAS_DEF: sub-filas Premios' in t:
    print('-- Premios ya estaba')
elif viejo_p in t:
    t = t.replace(viejo_p, nuevo_p, 1)
    print('OK: Premios — doble loop eliminado')
else:
    print('!! bloque Premios no encontrado')

if t == orig:
    print('Sin cambios')
    raise SystemExit(0)

bak = TPL.with_suffix(TPL.suffix + '.bak_subdef_' + TS)
shutil.copy2(TPL, bak)
print(f'Backup: {bak.name}')
TPL.write_text(t, encoding='utf-8')
print('GUARDADO')
print()
print('FIX_SUBFILAS_DEF COMPLETO')
