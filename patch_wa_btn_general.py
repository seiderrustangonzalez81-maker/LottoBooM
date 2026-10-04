from pathlib import Path

p = Path("/home/LottoBooM/jugadas/templates/jugadas/mis_apuestas.html")
src = p.read_text(encoding="utf-8")

if 'id="maCompartirTodas"' in src:
    print("SKIP: botón ya existe")
    raise SystemExit(0)

# ═══════════════════════════════════════════════════════════════
# 1. Insertar el botón en ma-header-right (antes del theme button)
# ═══════════════════════════════════════════════════════════════
viejo = '''        <button class="ma-icon-btn" id="maThemeBtn" title="Cambiar tema" type="button">
          <i class="fas fa-moon"></i>
        </button>'''

nuevo = '''        <button class="ma-compartir-todas" id="maCompartirTodas" type="button" title="Compartir todas las boletas visibles">
          <i class="fab fa-whatsapp"></i>
          <span>Compartir todas</span>
        </button>
        <button class="ma-icon-btn" id="maThemeBtn" title="Cambiar tema" type="button">
          <i class="fas fa-moon"></i>
        </button>'''

if viejo not in src:
    print("ERROR: no encontre el bloque del botón theme")
    raise SystemExit(1)

src = src.replace(viejo, nuevo, 1)
print("OK: botón 'Compartir todas' insertado")

# ═══════════════════════════════════════════════════════════════
# 2. Handler click → recolectar boletas visibles → llamar _waCompartirMultiple
# ═══════════════════════════════════════════════════════════════
handler_js = '''
// ═══════════════════════════════════════════════════════════════
// Handler del botón "Compartir todas"
// ═══════════════════════════════════════════════════════════════
document.addEventListener('DOMContentLoaded', function(){
  var btn = document.getElementById('maCompartirTodas');
  if (!btn || btn.dataset.bound) return;
  btn.dataset.bound = '1';
  btn.addEventListener('click', function(e){
    e.preventDefault();
    e.stopPropagation();

    // Recolectar todas las tarjetas de boleta visibles
    var tarjetas = document.querySelectorAll('.ma-boleta[data-boleta-id]');
    if (!tarjetas.length){
      showToast('No hay boletas para compartir', 'warn');
      return;
    }

    // Filtrar las que NO estén ocultas (display: none)
    var visibles = [];
    tarjetas.forEach(function(t){
      var oculta = t.offsetParent === null;  // true si display:none o padre oculto
      if (!oculta){
        visibles.push(t);
      }
    });

    if (!visibles.length){
      showToast('No hay boletas visibles', 'warn');
      return;
    }

    // Filtrar las canceladas si aplica
    visibles = visibles.filter(function(t){
      var estadoEl = t.querySelector('.ma-estado');
      var estado = estadoEl ? estadoEl.textContent.trim().toLowerCase() : '';
      return estado !== 'cancelada' && estado !== 'anulada';
    });

    if (!visibles.length){
      showToast('No hay boletas activas para compartir', 'warn');
      return;
    }

    _waCompartirMultiple(visibles, {
      maxChars: 3000,
      titulo: '📋 *Boletas — LottoBooM*',
    });
  });
});
'''

# Insertar antes de "// WHATSAPP" (dentro del <script>)
ancla = "  // WHATSAPP"
if ancla not in src:
    # Fallback: al final del script
    idx = src.rfind("</script>")
    if idx > 0:
        src = src[:idx] + "\n" + handler_js + "\n" + src[idx:]
        print("OK: handler insertado al final del script")
    else:
        print("ERROR: no encontre </script>")
        raise SystemExit(1)
else:
    src = src.replace(ancla, handler_js + "\n" + ancla, 1)
    print("OK: handler insertado antes de WHATSAPP")

p.write_text(src, encoding="utf-8")

# Verificación
ok1 = 'id="maCompartirTodas"' in src
ok2 = "_waCompartirMultiple" in src
ok3 = src.count("_waCompartirMultiple") >= 2
print("")
print("--- VERIFICACION ---")
print("boton general:", "OK" if ok1 else "NO")
print("funcion _waCompartirMultiple:", "OK" if ok2 else "NO")
print("total referencias:", src.count("_waCompartirMultiple"))
