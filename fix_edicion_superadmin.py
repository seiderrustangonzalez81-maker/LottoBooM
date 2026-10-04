# -*- coding: utf-8 -*-
"""Permite a superadmin editar Recibí/Envíé/Ajuste (comercial NO)."""
import shutil, datetime, re
from pathlib import Path

TS = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
TPL = Path('/home/LottoBooM/roles/templates/roles/cuadre_diario.html')

t = TPL.read_text(encoding='utf-8')
orig = t

# ═══════════════════════════════════════════════════════════
# Reemplazar TODOS los `{% if es_banco %}` por `{% if es_banco or es_superadmin %}`
# Solo en bloques específicos, con marcador para no tocar otros
# ═══════════════════════════════════════════════════════════

# 1. Botón + de Recibí
viejo1 = '''                Recibí del banco
                {% if es_banco %}<button type="button" class="cd-btn-add" data-tipo="recibi">+</button>{% endif %}'''
nuevo1 = '''                Recibí del banco
                {% if es_banco or es_superadmin %}<button type="button" class="cd-btn-add" data-tipo="recibi">+</button>{% endif %}'''

if 'data-tipo="recibi">+</button>{% endif %}' in t and 'es_banco or es_superadmin %}<button type="button" class="cd-btn-add" data-tipo="recibi"' in t:
    print('-- recibí + ya estaba')
elif viejo1 in t:
    t = t.replace(viejo1, nuevo1, 1)
    print('OK: botón + Recibí ahora para banco+superadmin')
else:
    print('!! bloque Recibí + no encontrado')

# 2. Sub-filas Recibí
viejo2 = '''            {% if es_banco %}
              {% for fp_nombre, lista in cuadre.recibi_lista.items %}'''
nuevo2 = '''            {% if es_banco or es_superadmin %}
              {% for fp_nombre, lista in cuadre.recibi_lista.items %}'''

if 'es_banco or es_superadmin %}\n              {% for fp_nombre, lista in cuadre.recibi_lista' in t:
    print('-- sub-filas Recibí ya estaban')
elif viejo2 in t:
    t = t.replace(viejo2, nuevo2, 1)
    print('OK: sub-filas Recibí para banco+superadmin')
else:
    print('!! bloque sub-filas Recibí no encontrado')

# 3. Botón + de Envié
viejo3 = '''                Envié al banco
                {% if es_banco %}<button type="button" class="cd-btn-add" data-tipo="envie">+</button>{% endif %}'''
nuevo3 = '''                Envié al banco
                {% if es_banco or es_superadmin %}<button type="button" class="cd-btn-add" data-tipo="envie">+</button>{% endif %}'''

if 'es_banco or es_superadmin %}<button type="button" class="cd-btn-add" data-tipo="envie"' in t:
    print('-- envié + ya estaba')
elif viejo3 in t:
    t = t.replace(viejo3, nuevo3, 1)
    print('OK: botón + Envié ahora para banco+superadmin')
else:
    print('!! bloque Envié + no encontrado')

# 4. Sub-filas Envié
viejo4 = '''            {% if es_banco %}
              {% for fp_nombre, lista in cuadre.envie_lista.items %}'''
nuevo4 = '''            {% if es_banco or es_superadmin %}
              {% for fp_nombre, lista in cuadre.envie_lista.items %}'''

if 'es_banco or es_superadmin %}\n              {% for fp_nombre, lista in cuadre.envie_lista' in t:
    print('-- sub-filas Envié ya estaban')
elif viejo4 in t:
    t = t.replace(viejo4, nuevo4, 1)
    print('OK: sub-filas Envié para banco+superadmin')
else:
    print('!! bloque sub-filas Envié no encontrado')

# 5. Botón + de Ajuste
viejo5 = '''                Ajuste
                {% if es_banco %}<button type="button" class="cd-btn-add" data-tipo="ajuste">+</button>{% endif %}'''
nuevo5 = '''                Ajuste
                {% if es_banco or es_superadmin %}<button type="button" class="cd-btn-add" data-tipo="ajuste">+</button>{% endif %}'''

if 'es_banco or es_superadmin %}<button type="button" class="cd-btn-add" data-tipo="ajuste"' in t:
    print('-- ajuste + ya estaba')
elif viejo5 in t:
    t = t.replace(viejo5, nuevo5, 1)
    print('OK: botón + Ajuste ahora para banco+superadmin')
else:
    print('!! bloque Ajuste + no encontrado')

# 6. Sub-filas Ajuste
viejo6 = '''            {% if es_banco %}
              {% for fp_nombre, lista in cuadre.ajuste_lista.items %}'''
nuevo6 = '''            {% if es_banco or es_superadmin %}
              {% for fp_nombre, lista in cuadre.ajuste_lista.items %}'''

if 'es_banco or es_superadmin %}\n              {% for fp_nombre, lista in cuadre.ajuste_lista' in t:
    print('-- sub-filas Ajuste ya estaban')
elif viejo6 in t:
    t = t.replace(viejo6, nuevo6, 1)
    print('OK: sub-filas Ajuste para banco+superadmin')
else:
    print('!! bloque sub-filas Ajuste no encontrado')

if t == orig:
    print('Sin cambios')
    raise SystemExit(0)

bak = TPL.with_suffix(TPL.suffix + '.bak_superadmin_' + TS)
shutil.copy2(TPL, bak)
print(f'Backup: {bak.name}')
TPL.write_text(t, encoding='utf-8')
print('GUARDADO')
print()
print('FIX_EDICION_SUPERADMIN COMPLETO')
