from pathlib import Path

p = Path("/home/LottoBooM/jugadas/templates/jugadas/apostar.html")
src = p.read_text(encoding="utf-8")

# ═══════════════════════════════════════════════════════════════
# PASO 1: Envolver el botón "Recargar a este cliente"
# ═══════════════════════════════════════════════════════════════
viejo1 = '<button type="button" id="btnRecargarQuick" style="'
nuevo1 = '{% if not es_cliente %}<button type="button" id="btnRecargarQuick" style="'

if "{% if not es_cliente %}<button" in src:
    print("PASO 1: SKIP (ya envuelto)")
elif viejo1 in src:
    src = src.replace(viejo1, nuevo1, 1)
    # Buscar el cierre del botón y agregar {% endif %}
    idx = src.find(nuevo1)
    idx_fin = src.find("</button>", idx)
    if idx_fin > 0:
        src = src[:idx_fin + len("</button>")] + "{% endif %}" + src[idx_fin + len("</button>"):]
        print("PASO 1: OK (boton envuelto)")
    else:
        print("PASO 1: ERROR (no encontre cierre)")
else:
    print("PASO 1: ERROR (no encontre btnRecargarQuick)")

# ═══════════════════════════════════════════════════════════════
# PASO 2: Ajustar initRecargaQuick
# ═══════════════════════════════════════════════════════════════
viejo2 = """    if (ES_CLIENTE){
      wrap.style.display = 'none';
      return;
    }
    var hayCliente = !!cliente;
    var hayFP = !!fpSel;
    wrap.style.display = (hayCliente && hayFP) ? 'block' : 'none';"""

nuevo2 = """    if (ES_CLIENTE){
      // Cliente: no tocar el wrap (lo maneja _actualizarVisibilidadBotones)
      return;
    }
    var hayCliente = !!cliente;
    var hayFP = !!fpSel;
    wrap.style.display = (hayCliente && hayFP) ? 'block' : 'none';"""

if "lo maneja _actualizarVisibilidadBotones" in src:
    print("PASO 2: SKIP (ya ajustado)")
elif viejo2 in src:
    src = src.replace(viejo2, nuevo2, 1)
    print("PASO 2: OK")
else:
    print("PASO 2: WARN (no encontre el bloque)")

p.write_text(src, encoding="utf-8")

# Verificacion con variables (sin f-strings problematicos)
ok1 = "{% if not es_cliente %}<button" in src
ok2 = "lo maneja _actualizarVisibilidadBotones" in src
print("")
print("--- VERIFICACION ---")
print("boton envuelto:", "OK" if ok1 else "NO")
print("initRecargaQuick ajustado:", "OK" if ok2 else "NO")
