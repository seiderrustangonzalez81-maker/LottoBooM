# -*- coding: utf-8 -*-
"""Auto-apply en todos los templates con filtros GET:
- onchange='this.form.submit()' en selects y dates
- eliminar <button type='submit'>
NO toca inputs text/email/number (evita auto-submit molesto).
"""
import re, shutil, datetime, sys
from pathlib import Path

TS = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
RAIZ = Path('/home/LottoBooM')

# Templates a procesar (excluye backups)
templates = [
    'banco/templates/banco/gestion_comerciales.html',
    'jugadas/templates/jugadas/mis_apuestas.html',
    'resultados/templates/resultados/resultados.html',
    'resultados/templates/resultados/mis_premios.html',
    'resultados/templates/resultados/ganadores.html',
    'roles/templates/roles/gestion_limites_dosis.html',
    'roles/templates/roles/historial_ventas.html',
    'roles/templates/roles/recarga_directa.html',
    'roles/templates/roles/historial_cuadres.html',
    'roles/templates/roles/lista_clientes.html',
    'roles/templates/roles/analisis_rendimiento.html',
    'roles/templates/roles/gestiones_banco.html',
    'roles/templates/roles/gestion_numeros_restringidos.html',
    'roles/templates/roles/ascender_usuario.html',
    'roles/templates/roles/mis_vias_pago.html',
    'roles/templates/roles/panel_sobrelimites.html',
    'superadmin/templates/superadmin/usuarios_list.html',
]

total_procesados = 0
total_cambiados = 0

for rel in templates:
    p = RAIZ / rel
    if not p.exists():
        print(f'  ⏭️  {rel}: no existe')
        continue

    total_procesados += 1
    t = p.read_text(encoding='utf-8')
    orig = t

    # 1. Encontrar forms con method=get
    def procesar_form(match):
        form_html = match.group(0)

        # Solo procesar si tiene algún select o input type=date
        if '<select' not in form_html and 'type="date"' not in form_html:
            return form_html

        # 1a. Añadir onchange a selects sin onchange
        form_html = re.sub(
            r'<select(?![^>]*\bonchange=)([^>]*)>',
            r'<select onchange="this.form.submit()"\1>',
            form_html
        )

        # 1b. Añadir onchange a inputs type=date sin onchange
        form_html = re.sub(
            r'<input(?![^>]*\bonchange=)([^>]*\btype="date"[^>]*)>',
            r'<input onchange="this.form.submit()"\1>',
            form_html
        )

        # 1c. Eliminar botón submit (con cualquier texto)
        form_html = re.sub(
            r'<button[^>]*type="submit"[^>]*>.*?</button>\s*',
            '',
            form_html,
            flags=re.DOTALL
        )

        return form_html

    # Aplicar a cada <form...>...</form>
    t = re.sub(
        r'<form[^>]*method="get"[^>]*>.*?</form>',
        procesar_form,
        t,
        flags=re.DOTALL | re.IGNORECASE
    )

    if t != orig:
        total_cambiados += 1
        bak = p.with_suffix(p.suffix + '.bak_filtros_' + TS)
        shutil.copy2(p, bak)
        p.write_text(t, encoding='utf-8')
        print(f'  ✅ {rel}')
    else:
        print(f'  ⏭️  {rel}: sin cambios')

print()
print(f'Procesados: {total_procesados}')
print(f'Modificados: {total_cambiados}')
print()
print('FIX_FILTROS_GLOBAL COMPLETO')
