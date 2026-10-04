# -*- coding: utf-8 -*-
"""Fix etiquetas con regex — a prueba de fallos."""
import re, shutil, datetime
from pathlib import Path

TS = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
TPL = Path('/home/LottoBooM/roles/templates/roles/cuadre_diario.html')

t = TPL.read_text(encoding='utf-8')
orig = t

# ═══════════════════════════════════════════════════════════
# RECIBÍ — regex robusto que captura cualquier {% if %}...{% endif %}
# dentro de un <td> que contenga la palabra "Recibí"
# ═══════════════════════════════════════════════════════════
patron_r = re.compile(
    r'(\{% if [^%]*%\}Recibí del comercial\{% else %\}Recibí del banco\{% endif %\})'
)
if patron_r.search(t):
    t = patron_r.sub(
        "{% if es_banco and comercial_seleccionado %}Recibí del comercial{% elif es_banco %}Recibí de los comerciales{% else %}Recibí del banco{% endif %}",
        t
    )
    print('OK: Recibí (regex)')
elif 'Recibí de los comerciales' in t:
    print('-- Recibí ya estaba')
else:
    # Buscar por proximidad
    m = re.search(r'Recibí del banco', t)
    if m:
        # Reemplazar la línea entera buscando un {% if ... %} antes
        start = t.rfind('{% if', 0, m.start())
        end = t.find('{% endif %}', m.start())
        if start > 0 and end > 0:
            end += len('{% endif %}')
            t = t[:start] + "{% if es_banco and comercial_seleccionado %}Recibí del comercial{% elif es_banco %}Recibí de los comerciales{% else %}Recibí del banco{% endif %}" + t[end:]
            print('OK: Recibí (por proximidad)')
        else:
            print('!! no se pudo ubicar el if/endif de Recibí')
    else:
        print('!! "Recibí del banco" no está en el archivo')

# ═══════════════════════════════════════════════════════════
# ENVIÉ — mismo patrón
# ═══════════════════════════════════════════════════════════
patron_e = re.compile(
    r'(\{% if [^%]*%\}Envié al comercial\{% else %\}Envié al banco\{% endif %\})'
)
if patron_e.search(t):
    t = patron_e.sub(
        "{% if es_banco and comercial_seleccionado %}Envié al comercial{% elif es_banco %}Envié a los comerciales{% else %}Envié al banco{% endif %}",
        t
    )
    print('OK: Envié (regex)')
elif 'Envié a los comerciales' in t:
    print('-- Envié ya estaba')
else:
    m = re.search(r'Envié al banco', t)
    if m:
        start = t.rfind('{% if', 0, m.start())
        end = t.find('{% endif %}', m.start())
        if start > 0 and end > 0:
            end += len('{% endif %}')
            t = t[:start] + "{% if es_banco and comercial_seleccionado %}Envié al comercial{% elif es_banco %}Envié a los comerciales{% else %}Envié al banco{% endif %}" + t[end:]
            print('OK: Envié (por proximidad)')
        else:
            print('!! no se pudo ubicar el if/endif de Envié')
    else:
        print('!! "Envié al banco" no está en el archivo')

if t == orig:
    print('Sin cambios')
    raise SystemExit(0)

bak = TPL.with_suffix(TPL.suffix + '.bak_etq2_' + TS)
shutil.copy2(TPL, bak)
print(f'Backup: {bak.name}')
TPL.write_text(t, encoding='utf-8')
print('GUARDADO')
print()
print('FIX_ETIQUETAS_V2 COMPLETO')
