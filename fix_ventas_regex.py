# -*- coding: utf-8 -*-
import re, shutil, datetime
from pathlib import Path

TS = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
TPL = Path('/home/LottoBooM/roles/templates/roles/cuadre_diario.html')

t = TPL.read_text(encoding='utf-8')
orig = t

# Regex que captura el bloque Ventas actual (desde el comentario hasta antes de COMISIÓN)
patron = re.compile(
    r'<!-- FIX_CUADRE_SUBFILAS: sub-filas Ventas por sorteo \(toggle\) -->[\s\S]*?(?=<!-- COMISIÓN -->)',
    re.DOTALL
)

nuevo = '''<!-- FIX_SUBFILAS_DEF: sub-filas Ventas por sorteo (toggle) -->
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

            '''

m = patron.search(t)
if not m:
    print('!! patrón Ventas no encontrado')
else:
    t = t[:m.start()] + nuevo + t[m.end():]
    print('OK: bloque Ventas reemplazado por regex')
    bak = TPL.with_suffix(TPL.suffix + '.bak_vr_' + TS)
    shutil.copy2(TPL, bak)
    print(f'Backup: {bak.name}')
    TPL.write_text(t, encoding='utf-8')
    print('GUARDADO')

print('FIX_VENTAS_REGEX COMPLETO')
