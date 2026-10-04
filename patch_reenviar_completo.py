from pathlib import Path

# ═══════════════════════════════════════════════════════════════
# 1. VISTA apostar — detectar modo_editar vs modo_reenviar
# ═══════════════════════════════════════════════════════════════
p1 = Path("/home/LottoBooM/jugadas/views.py")
src1 = p1.read_text(encoding="utf-8")

viejo1 = """    edit_boleta_id = request.GET.get('edit_boleta')
    edit_boleta_data = None"""

nuevo1 = """    edit_boleta_id = request.GET.get('edit_boleta')
    edit_boleta_data = None
    # Modo editar vs reenviar (viene por URL)
    es_modo_editar = request.GET.get('modo_editar') == '1'
    es_modo_reenviar = request.GET.get('modo_reenviar') == '1'"""

if "es_modo_reenviar = request.GET.get('modo_reenviar')" in src1:
    print("1a: SKIP")
elif viejo1 in src1:
    src1 = src1.replace(viejo1, nuevo1, 1)
    print("1a: OK (detección modo editar/reenviar)")
else:
    print("1a: ERROR")

# Pasar al contexto
viejo1b = "        'rol': user.roles.filter(activo=True).first().tipo if user.roles.filter(activo=True).exists() else 'cliente',\n    }\n    return render(request, 'jugadas/apostar.html', context)"

nuevo1b = """        'rol': user.roles.filter(activo=True).first().tipo if user.roles.filter(activo=True).exists() else 'cliente',
        'es_modo_editar': es_modo_editar,
        'es_modo_reenviar': es_modo_reenviar,
    }
    return render(request, 'jugadas/apostar.html', context)"""

if "'es_modo_reenviar': es_modo_reenviar" in src1:
    print("1b: SKIP")
elif viejo1b in src1:
    src1 = src1.replace(viejo1b, nuevo1b, 1)
    print("1b: OK (context)")
else:
    # Alternativa: buscar solo el `return render(request, 'jugadas/apostar.html', context)`
    import re
    patron = re.compile(
        r"(\n\s+)(return render\(request, 'jugadas/apostar\.html', context\))"
    )
    m = patron.search(src1)
    if m:
        # Insertar antes del return
        src1 = src1[:m.start()] + f"\n        'es_modo_editar': es_modo_editar,\n        'es_modo_reenviar': es_modo_reenviar," + src1[m.start():]
        print("1b: OK (context, via regex)")
    else:
        print("1b: ERROR (no encontre return render de apostar.html)")

p1.write_text(src1, encoding="utf-8")

import ast
try:
    ast.parse(src1)
    print("sintaxis views.py: OK")
except SyntaxError as e:
    print(f"ERROR sintaxis views: {e}")
    raise SystemExit(1)


# ═══════════════════════════════════════════════════════════════
# 2. TEMPLATE — banner distinto + no bloquear total en reenviar
# ═══════════════════════════════════════════════════════════════
p2 = Path("/home/LottoBooM/jugadas/templates/jugadas/apostar.html")
src2 = p2.read_text(encoding="utf-8")

# ─── 2a. Reemplazar el banner ───
viejo2a = """  <div class="edit-banner">
    <i class="fas fa-edit"></i> Editando boleta <strong>{{ edit_boleta_data.referencia }}</strong> — al guardar se cancelará la original y se creará una nueva.
  </div>"""

nuevo2a = """  <div class="edit-banner" id="editBanner" style="{% if es_modo_reenviar %}background:linear-gradient(145deg,#dbeafe,#bfdbfe);border-color:#3b82f6;color:#1e3a8a;{% endif %}">
    {% if es_modo_reenviar %}
      <i class="fas fa-paper-plane"></i> <span id="editBannerText">Reenviando boleta <strong>{{ edit_boleta_data.referencia }}</strong> — la original se mantiene intacta. Puedes modificar números, montos, sorteos y forma de pago.</span>
    {% else %}
      <i class="fas fa-edit"></i> <span id="editBannerText">Editando boleta <strong>{{ edit_boleta_data.referencia }}</strong> — al guardar se cancelará la original y se creará una nueva. <em>El total debe ser igual.</em></span>
    {% endif %}
  </div>"""

if 'id="editBanner"' in src2:
    print("2a: SKIP")
elif viejo2a in src2:
    src2 = src2.replace(viejo2a, nuevo2a, 1)
    print("2a: OK (banner)")
else:
    print("2a: WARN (no matcheo banner exacto)")

# ─── 2b. JS: definir ES_MODO_REENVIAR ───
viejo2b = "const ES_SOLO_EDITAR = (new URLSearchParams(window.location.search)).get('modo_editar') === '1';"
nuevo2b = """const ES_SOLO_EDITAR = (new URLSearchParams(window.location.search)).get('modo_editar') === '1';
const ES_MODO_REENVIAR = (new URLSearchParams(window.location.search)).get('modo_reenviar') === '1';"""

if "const ES_MODO_REENVIAR" in src2:
    print("2b: SKIP")
elif viejo2b in src2:
    src2 = src2.replace(viejo2b, nuevo2b, 1)
    print("2b: OK (ES_MODO_REENVIAR)")
else:
    print("2b: ERROR (no encontre ES_SOLO_EDITAR)")

# ─── 2c. JS: en modo reenviar, NO validar suma igual ───
viejo2c = "  if (ok && typeof MODO_EDICION !== 'undefined' && MODO_EDICION === 'editar'){"

nuevo2c = "  if (ok && typeof MODO_EDICION !== 'undefined' && MODO_EDICION === 'editar' && !ES_MODO_REENVIAR){"

if "&& !ES_MODO_REENVIAR" in src2:
    print("2c: SKIP")
elif viejo2c in src2:
    src2 = src2.replace(viejo2c, nuevo2c, 1)
    print("2c: OK (no valida suma igual en reenviar)")
else:
    print("2c: WARN (no matcheo bloque de validación suma)")

# ─── 2d. JS: en modo reenviar, NO aplicar bloqueo de "cliente agotado" ───
viejo2d = "const esClienteAgotado = !ES_SOLO_EDITAR && ES_CLIENTE && !!fpSel && total > 0 && total > disponibleTotal;"
nuevo2d = "const esClienteAgotado = !ES_SOLO_EDITAR && !ES_MODO_REENVIAR && ES_CLIENTE && !!fpSel && total > 0 && total > disponibleTotal;"

if "!ES_SOLO_EDITAR && !ES_MODO_REENVIAR" in src2:
    print("2d: SKIP")
elif viejo2d in src2:
    src2 = src2.replace(viejo2d, nuevo2d, 1)
    print("2d: OK (no bloquea en reenviar)")
else:
    print("2d: WARN (no matcheo esClienteAgotado)")

p2.write_text(src2, encoding="utf-8")
print("template apostar.html: OK")

# ═══════════════════════════════════════════════════════════════
# 3. MIS_APUESTAS — botón reenviar con URL correcta
# ═══════════════════════════════════════════════════════════════
p3 = Path("/home/LottoBooM/jugadas/templates/jugadas/mis_apuestas.html")
if p3.exists():
    src3 = p3.read_text(encoding="utf-8")
    viejo3 = 'window.location.href = "{% url \'jugadas:apostar\' %}?edit_boleta=" + b.id + "&modo_reenviar=1";'
    # Verificar que ya está bien (el JS ya usa modo_reenviar=1)
    if "modo_reenviar=1" in src3:
        print("3: OK (botón reenviar ya apunta con modo_reenviar=1)")
    else:
        print("3: WARN (revisar botón reenviar manualmente)")

# ═══════════════════════════════════════════════════════════════
# REPORTE
# ═══════════════════════════════════════════════════════════════
print("\n✅ Patch reenviar aplicado")
print("\nVerificar con:")
print("  python3 manage.py check 2>&1 | tail -3")
print("  grep -c 'ES_MODO_REENVIAR' jugadas/templates/jugadas/apostar.html")
