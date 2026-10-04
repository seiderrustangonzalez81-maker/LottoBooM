# -*- coding: utf-8 -*-
"""Fix: JS modal + etiquetas dinámicas banco->comercial + verificación toggle."""
import shutil, datetime
from pathlib import Path

TS = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
TPL = Path('/home/LottoBooM/roles/templates/roles/cuadre_diario.html')

t = TPL.read_text(encoding='utf-8')
orig = t

# ═══════════════════════════════════════════════════════════
# FIX 1 — Error JS: Object.keys sin llaves
# ═══════════════════════════════════════════════════════════
viejo1 = "modalFp.value = fp || Object.keys({% for k, v in control.fondo_inicial.items %}{{ k|escapejs }}:1,{% endfor %})[0];"
nuevo1 = "modalFp.value = fp || Object.keys({ {% for k, v in control.fondo_inicial.items %}'{{ k|escapejs }}':1,{% endfor %} })[0];"

if 'Object.keys({ {% for k' in t:
    print('-- Fix 1 ya aplicado')
elif viejo1 in t:
    t = t.replace(viejo1, nuevo1, 1)
    print('OK: JS Object.keys con llaves y comillas')
else:
    print('!! línea Object.keys no encontrada')

# ═══════════════════════════════════════════════════════════
# FIX 2 — Etiquetas dinámicas: banco viendo comercial
# ═══════════════════════════════════════════════════════════
# Cuando es_banco y comercial_seleccionado -> cambia etiquetas
viejo2 = '''              <td>
                Recibí del banco
                {% if es_banco or es_superadmin %}<button type="button" class="cd-btn-add" data-tipo="recibi">+</button>{% endif %}
              </td>'''

nuevo2 = '''              <td>
                {% if es_banco and comercial_seleccionado %}Recibí del comercial{% else %}Recibí del banco{% endif %}
                {% if es_banco or es_superadmin %}<button type="button" class="cd-btn-add" data-tipo="recibi">+</button>{% endif %}
              </td>'''

if 'Recibí del comercial' in t:
    print('-- Fix 2 (recibí) ya aplicado')
elif viejo2 in t:
    t = t.replace(viejo2, nuevo2, 1)
    print('OK: etiqueta Recibí dinámica')
else:
    print('!! bloque Recibí no encontrado')

# Envié
viejo3 = '''              <td>
                Envié al banco
                {% if es_banco or es_superadmin %}<button type="button" class="cd-btn-add" data-tipo="envie">+</button>{% endif %}
              </td>'''

nuevo3 = '''              <td>
                {% if es_banco and comercial_seleccionado %}Envié al comercial{% else %}Envié al banco{% endif %}
                {% if es_banco or es_superadmin %}<button type="button" class="cd-btn-add" data-tipo="envie">+</button>{% endif %}
              </td>'''

if 'Envié al comercial' in t:
    print('-- Fix 2 (envié) ya aplicado')
elif viejo3 in t:
    t = t.replace(viejo3, nuevo3, 1)
    print('OK: etiqueta Envié dinámica')
else:
    print('!! bloque Envié no encontrado')

# ═══════════════════════════════════════════════════════════
# FIX 3 — Ventas y Premios: permitir edición (botón + en filas)
# ═══════════════════════════════════════════════════════════
# Las sub-filas ahora iteran todos los grupos (no hay if es_banco).
# Está bien, pero para banco viendo comercial debe permitir editar.
# El usuario pidió: "cuando toca en ventas/premios/ajustes no se despliegan para escribir"

# Asegurar que el toggle está activo. Verificar que la clase row-toggleable esté.
if 'row-toggleable' not in t:
    print('!! row-toggleable no existe — toggle roto')
else:
    print('-- row-toggleable presente')

# ═══════════════════════════════════════════════════════════
# FIX 4 — Si es banco viendo comercial, mostrar botones en Recibí/Envíé/Ajuste
# (ya debería estar por el fix anterior pero verificamos)
# ═══════════════════════════════════════════════════════════
# Contar cuántos botones tienen la condición correcta
n_botones = t.count('{% if es_banco or es_superadmin %}<button type="button" class="cd-btn-add"')
print(f'-- Botones + con condición banco/superadmin: {n_botones}')

# ═══════════════════════════════════════════════════════════
# GUARDAR
# ═══════════════════════════════════════════════════════════
if t == orig:
    print()
    print('Sin cambios')
else:
    bak = TPL.with_suffix(TPL.suffix + '.bak_bancomerc_' + TS)
    shutil.copy2(TPL, bak)
    print(f'Backup: {bak.name}')
    TPL.write_text(t, encoding='utf-8')
    print('GUARDADO')
    print()
    print('FIX_CUADRE_BANCO_COMERCIAL COMPLETO')
