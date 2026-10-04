# -*- coding: utf-8 -*-
import shutil, datetime
from pathlib import Path

TS = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
TPL = Path('/home/LottoBooM/roles/templates/roles/cuadre_diario.html')

t = TPL.read_text(encoding='utf-8')
orig = t

# ═══════════════════════════════════════════════════════════
# Etiqueta Recibí
# ═══════════════════════════════════════════════════════════
viejo_r = "                {% if es_banco and comercial_seleccionado %}Recibí del comercial{% else %}Recibí del banco{% endif %}"

nuevo_r = """                {% if es_superadmin and banco_seleccionado and not comercial_seleccionado %}Recibí del banco
                {% elif es_superadmin and not banco_seleccionado %}Recibí de los bancos
                {% elif es_banco and comercial_seleccionado %}Recibí del comercial
                {% elif es_banco %}Recibí de los comerciales
                {% else %}Recibí del banco{% endif %}"""

if 'Recibí de los comerciales' in t:
    print('-- Recibí ya estaba')
elif viejo_r in t:
    t = t.replace(viejo_r, nuevo_r, 1)
    print('OK: etiqueta Recibí actualizada')
else:
    print('!! bloque Recibí no encontrado')

# ═══════════════════════════════════════════════════════════
# Etiqueta Envié
# ═══════════════════════════════════════════════════════════
viejo_e = "                {% if es_banco and comercial_seleccionado %}Envié al comercial{% else %}Envié al banco{% endif %}"

nuevo_e = """                {% if es_superadmin and banco_seleccionado and not comercial_seleccionado %}Envié al banco
                {% elif es_superadmin and not banco_seleccionado %}Envié a los bancos
                {% elif es_banco and comercial_seleccionado %}Envié al comercial
                {% elif es_banco %}Envié a los comerciales
                {% else %}Envié al banco{% endif %}"""

if 'Envié a los comerciales' in t:
    print('-- Envié ya estaba')
elif viejo_e in t:
    t = t.replace(viejo_e, nuevo_e, 1)
    print('OK: etiqueta Envié actualizada')
else:
    print('!! bloque Envié no encontrado')

if t == orig:
    print('Sin cambios')
    raise SystemExit(0)

bak = TPL.with_suffix(TPL.suffix + '.bak_etq_' + TS)
shutil.copy2(TPL, bak)
print(f'Backup: {bak.name}')
TPL.write_text(t, encoding='utf-8')
print('GUARDADO')
print()
print('FIX_ETIQUETAS_CUADRE COMPLETO')
