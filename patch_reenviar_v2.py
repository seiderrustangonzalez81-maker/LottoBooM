from pathlib import Path
import ast

# ═══════════════════════════════════════════════════════════════
# 1. views.py — agregar context entries
# ═══════════════════════════════════════════════════════════════
p1 = Path("/home/LottoBooM/jugadas/views.py")
src1 = p1.read_text(encoding="utf-8")

if "'es_modo_editar': es_modo_editar," in src1:
    print("1: SKIP (ya en context)")
else:
    viejo = "        'recarga_ok': recarga_ok,\n    }\n    return render(request, 'jugadas/apostar.html', context)"
    nuevo = """        'recarga_ok': recarga_ok,
        'es_modo_editar': es_modo_editar,
        'es_modo_reenviar': es_modo_reenviar,
    }
    return render(request, 'jugadas/apostar.html', context)"""
    
    if viejo in src1:
        src1 = src1.replace(viejo, nuevo, 1)
        p1.write_text(src1, encoding="utf-8")
        print("1: OK (context entries agregadas)")
    else:
        print("1: ERROR (no encontre el bloque exacto)")
        idx = src1.find("return render(request, 'jugadas/apostar.html', context)")
        if idx > 0:
            cierre = src1.rfind("\n    }", 0, idx)
            if cierre > 0:
                src1 = src1[:cierre] + "\n        'es_modo_editar': es_modo_editar,\n        'es_modo_reenviar': es_modo_reenviar," + src1[cierre:]
                p1.write_text(src1, encoding="utf-8")
                print("1: OK (via fallback)")

try:
    ast.parse(src1)
    print("sintaxis views.py: OK")
except SyntaxError as e:
    print("ERROR sintaxis views.py:", str(e))
    raise SystemExit(1)


# ═══════════════════════════════════════════════════════════════
# 2. apostar.html — aplicar cambios del template
# ═══════════════════════════════════════════════════════════════
p2 = Path("/home/LottoBooM/jugadas/templates/jugadas/apostar.html")
src2 = p2.read_text(encoding="utf-8")
cambios = []

# ─── 2a. Banner ───
if 'id="editBanner"' in src2:
    cambios.append("2a: SKIP")
else:
    viejo2a = """  <div class="edit-banner">
    <i class="fas fa-edit"></i> Editando boleta <strong>{{ edit_boleta_data.referencia }}</strong> — al guardar se cancelará la original y se creará una nueva.
  </div>"""
    nuevo2a = """  <div class="edit-banner" id="editBanner" style="{% if es_modo_reenviar %}background:linear-gradient(145deg,#dbeafe,#bfdbfe);border-color:#3b82f6;color:#1e3a8a;{% endif %}">
    {% if es_modo_reenviar %}
      <i class="fas fa-paper-plane"></i> <span id="editBannerText">Reenviando boleta <strong>{{ edit_boleta_data.referencia }}</strong> — la original se mantiene intacta. Puedes modificar números, montos, sorteos y forma de pago.</span>
    {% else %}
      <i class="fas fa-edit"></i> <span id="editBannerText">Editando boleta <strong>{{ edit_boleta_data.referencia }}</strong> — al guardar se cancelará la original y se creará una nueva.</span>
    {% endif %}
  </div>"""
    if viejo2a in src2:
        src2 = src2.replace(viejo2a, nuevo2a, 1)
        cambios.append("2a: OK (banner)")
    else:
        cambios.append("2a: WARN (no matcheo banner)")

# ─── 2b. ES_MODO_REENVIAR ───
if "const ES_MODO_REENVIAR" in src2:
    cambios.append("2b: SKIP")
else:
    viejo2b = "const ES_SOLO_EDITAR = (new URLSearchParams(window.location.search)).get('modo_editar') === '1';"
    nuevo2b = """const ES_SOLO_EDITAR = (new URLSearchParams(window.location.search)).get('modo_editar') === '1';
const ES_MODO_REENVIAR = (new URLSearchParams(window.location.search)).get('modo_reenviar') === '1';"""
    if viejo2b in src2:
        src2 = src2.replace(viejo2b, nuevo2b, 1)
        cambios.append("2b: OK (ES_MODO_REENVIAR)")
    else:
        cambios.append("2b: ERROR (no encontre ES_SOLO_EDITAR)")

# ─── 2c. No validar suma igual en reenviar ───
if "&& !ES_MODO_REENVIAR){" in src2:
    cambios.append("2c: SKIP")
else:
    viejo2c = "if (ok && typeof MODO_EDICION !== 'undefined' && MODO_EDICION === 'editar'){"
    nuevo2c = "if (ok && typeof MODO_EDICION !== 'undefined' && MODO_EDICION === 'editar' && !ES_MODO_REENVIAR){"
    if viejo2c in src2:
        src2 = src2.replace(viejo2c, nuevo2c, 1)
        cambios.append("2c: OK")
    else:
        cambios.append("2c: WARN")

# ─── 2d. No bloquear cliente agotado en reenviar ───
if "!ES_SOLO_EDITAR && !ES_MODO_REENVIAR" in src2:
    cambios.append("2d: SKIP")
else:
    viejo2d = "const esClienteAgotado = !ES_SOLO_EDITAR && ES_CLIENTE && !!fpSel && total > 0 && total > disponibleTotal;"
    nuevo2d = "const esClienteAgotado = !ES_SOLO_EDITAR && !ES_MODO_REENVIAR && ES_CLIENTE && !!fpSel && total > 0 && total > disponibleTotal;"
    if viejo2d in src2:
        src2 = src2.replace(viejo2d, nuevo2d, 1)
        cambios.append("2d: OK")
    else:
        cambios.append("2d: WARN")

p2.write_text(src2, encoding="utf-8")

print("")
print("=== REPORTE ===")
for c in cambios:
    print("  " + c)

ok1 = "'es_modo_editar': es_modo_editar," in src1
print("")
print("--- VERIFICACION ---")
print("es_modo_editar en context:", "OK" if ok1 else "NO")
print("ES_MODO_REENVIAR en template:", src2.count('ES_MODO_REENVIAR'))
print("editBanner en template:", src2.count('id="editBanner"'))
