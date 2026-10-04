# -*- coding: utf-8 -*-
"""Sub-filas Ventas y Premios por sorteo."""
import shutil, datetime, re, sys
from pathlib import Path

TPL = Path('/home/LottoBooM/roles/templates/roles/cuadre_diario.html')
TS = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')

t = TPL.read_text(encoding='utf-8')
orig = t

# ═══════════════════════════════════════════════════════════
# 1. Ventas — añadir sub-filas después
# ═══════════════════════════════════════════════════════════
viejo_ventas = '''            <!-- VENTAS -->
            <tr>
              <td>Ventas</td>
              {% for fp_nombre, valor in control.ventas.items %}
                <td>{% if valor %}{{ valor|floatformat:2|intcomma }}{% endif %}</td>
              {% endfor %}
              <td class="col-total">{{ resumen.total_recogido|floatformat:2|intcomma }}</td>
            </tr>'''

nuevo_ventas = '''            <!-- VENTAS -->
            <tr>
              <td>Ventas</td>
              {% for fp_nombre, valor in control.ventas.items %}
                <td>{% if valor %}{{ valor|floatformat:2|intcomma }}{% endif %}</td>
              {% endfor %}
              <td class="col-total">{{ resumen.total_recogido|floatformat:2|intcomma }}</td>
            </tr>

            <!-- FIX_CUADRE_SUBFILAS: sub-filas Ventas por sorteo -->
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

if 'FIX_CUADRE_SUBFILAS' in t:
    print('-- Ventas sub-filas ya estaban')
elif viejo_ventas in t:
    t = t.replace(viejo_ventas, nuevo_ventas, 1)
    print('OK: sub-filas Ventas')
else:
    print('!! bloque VENTAS no encontrado')
    sys.exit(1)

# ═══════════════════════════════════════════════════════════
# 2. Premios — añadir sub-filas después
# ═══════════════════════════════════════════════════════════
viejo_premios = '''            <!-- PREMIOS -->
            <tr class="row-premios">
              <td>Premios</td>
              {% for fp_nombre, valor in control.premios.items %}
                <td>− {{ valor|floatformat:2|intcomma }}</td>
              {% endfor %}
              <td class="col-total">− {{ resumen.premios|floatformat:2|intcomma }}</td>
            </tr>'''

nuevo_premios = '''            <!-- PREMIOS -->
            <tr class="row-premios">
              <td>Premios</td>
              {% for fp_nombre, valor in control.premios.items %}
                <td>− {{ valor|floatformat:2|intcomma }}</td>
              {% endfor %}
              <td class="col-total">− {{ resumen.premios|floatformat:2|intcomma }}</td>
            </tr>

            <!-- FIX_CUADRE_SUBFILAS: sub-filas Premios por sorteo (solo > 0) -->
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

if 'FIX_CUADRE_SUBFILAS' in t and 'sub-filas Premios' in t:
    print('-- Premios sub-filas ya estaban')
elif viejo_premios in t:
    t = t.replace(viejo_premios, nuevo_premios, 1)
    print('OK: sub-filas Premios')
else:
    print('!! bloque PREMIOS no encontrado')
    sys.exit(1)

if t == orig:
    print('Sin cambios')
    sys.exit(0)

bak = TPL.with_suffix(TPL.suffix + '.bak_p2_' + TS)
shutil.copy2(TPL, bak)
print(f'Backup: {bak.name}')
TPL.write_text(t, encoding='utf-8')
print('GUARDADO')
print()
print('PASO 2 COMPLETO')
