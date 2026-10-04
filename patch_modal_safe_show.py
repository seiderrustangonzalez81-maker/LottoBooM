from pathlib import Path
import re

p = Path("/home/LottoBooM/jugadas/templates/jugadas/apostar.html")
src = p.read_text(encoding="utf-8")
original = src

cambios = []

# ═══════════════════════════════════════════════════════════════
# PASO 1: Añadir helpers _safeModalShow/_safeModalHide
# ═══════════════════════════════════════════════════════════════
helpers = """
// ═══════════════════════════════════════════════════════════════
// Helpers de modal SEGUROS (evitan el bug "backdrop undefined")
// ═══════════════════════════════════════════════════════════════
window._safeModalShow = function(modalId) {
  var el = document.getElementById(modalId);
  if (!el) { console.error('[safeModalShow] no existe #' + modalId); return null; }
  try {
    // Dispose cualquier instancia existente (evita _config undefined)
    var existing = bootstrap.Modal.getInstance(el);
    if (existing) {
      try { existing.hide(); } catch(_){}
      try { existing.dispose(); } catch(_){}
    }
    // Limpiar DOM por si acaso
    el.classList.remove('show');
    el.style.display = 'none';
    el.removeAttribute('aria-hidden');
    el.removeAttribute('aria-modal');
    // Remover backdrops huérfanos
    document.querySelectorAll('.modal-backdrop').forEach(function(b){ b.remove(); });
    document.body.classList.remove('modal-open');
    document.body.style.removeProperty('overflow');
    document.body.style.removeProperty('padding-right');
  } catch(e){ console.warn('[safeModalShow prep]', e); }
  // Crear instancia fresca
  try {
    var modal = new bootstrap.Modal(el);
    modal.show();
    return modal;
  } catch(e) {
    console.error('[safeModalShow] Error creando modal:', e);
    return null;
  }
};

window._safeModalHide = function(modalId) {
  var el = document.getElementById(modalId);
  if (!el) return;
  try {
    var inst = bootstrap.Modal.getInstance(el);
    if (inst) {
      try { inst.hide(); } catch(_){}
    } else {
      el.classList.remove('show');
      el.style.display = 'none';
      el.setAttribute('aria-hidden', 'true');
    }
    // Cleanup backdrops después de la animación
    setTimeout(function(){
      document.querySelectorAll('.modal-backdrop').forEach(function(b){ b.remove(); });
      document.body.classList.remove('modal-open');
      document.body.style.removeProperty('overflow');
      document.body.style.removeProperty('padding-right');
    }, 400);
  } catch(e){ console.warn('[safeModalHide]', e); }
};

"""

# Insertar antes del ancla de debug
ancla = "window.autoformatear = autoformatear;"
if "_safeModalShow" in src:
    cambios.append("PASO 1: SKIP (ya existe)")
elif ancla in src:
    src = src.replace(ancla, helpers + ancla, 1)
    cambios.append("PASO 1: OK (helpers insertados)")
else:
    cambios.append("PASO 1: ERROR (no encontre ancla)")

p.write_text(src, encoding="utf-8")
print(cambios[-1])

# ═══════════════════════════════════════════════════════════════
# PASO 2: Reemplazar TODAS las llamadas a bootstrap.Modal
# ═══════════════════════════════════════════════════════════════

# 2.1 — Reemplazar .show() → _safeModalShow
patron_show = re.compile(
    r"bootstrap\.Modal\.getOrCreateInstance\(\s*document\.getElementById\(['\"]([^'\"]+)['\"]\)\s*\)\.show\(\)"
)
src_new, n_show = patron_show.subn(
    lambda m: f"window._safeModalShow('{m.group(1)}')",
    src
)
if n_show:
    src = src_new
    cambios.append(f"PASO 2.1: OK ({n_show} .show() reemplazados)")
else:
    cambios.append("PASO 2.1: SKIP")

# 2.2 — Reemplazar new bootstrap.Modal(el).show() → _safeModalShow
patron_new = re.compile(
    r"new bootstrap\.Modal\(\s*document\.getElementById\(['\"]([^'\"]+)['\"]\)\s*\)\.show\(\)"
)
src_new, n_new = patron_new.subn(
    lambda m: f"window._safeModalShow('{m.group(1)}')",
    src
)
if n_new:
    src = src_new
    cambios.append(f"PASO 2.2: OK ({n_new} new+show reemplazados)")
else:
    cambios.append("PASO 2.2: SKIP")

# 2.3 — Reemplazar .hide() → _safeModalHide
patron_hide = re.compile(
    r"bootstrap\.Modal\.getInstance\(\s*document\.getElementById\(['\"]([^'\"]+)['\"]\)\s*\)\.hide\(\)"
)
src_new, n_hide = patron_hide.subn(
    lambda m: f"window._safeModalHide('{m.group(1)}')",
    src
)
if n_hide:
    src = src_new
    cambios.append(f"PASO 2.3: OK ({n_hide} .hide() reemplazados)")
else:
    cambios.append("PASO 2.3: SKIP")

# 2.4 — jQuery style $('modalX') que también aparezca
patron_jq = re.compile(
    r"bootstrap\.Modal\.getOrCreateInstance\(\s*\$\(['\"]([^'\"]+)['\"]\)\s*\)\.(show|hide)\(\)"
)
def repl_jq(m):
    accion = m.group(2)
    return f"window._safeModal{'Show' if accion == 'show' else 'Hide'}('{m.group(1)}')"
src_new, n_jq = patron_jq.subn(repl_jq, src)
if n_jq:
    src = src_new
    cambios.append(f"PASO 2.4: OK ({n_jq} jQuery-style reemplazados)")
else:
    cambios.append("PASO 2.4: SKIP")

p.write_text(src, encoding="utf-8")

# ═══════════════════════════════════════════════════════════════
# REPORTE
# ═══════════════════════════════════════════════════════════════
print("\n═══ REPORTE ═══")
for c in cambios:
    print(f"  {c}")

print(f"\n_safeModalShow en src: {src.count('_safeModalShow')}")
print(f"_safeModalHide en src: {src.count('_safeModalHide')}")
print(f"bootstrap.Modal restantes: {src.count('bootstrap.Modal')}")

# Verificar balance de comillas
if src.count("'") % 2 != 0:
    print("WARN: comillas simples impares — posible error")

if src == original:
    print("ERROR: no se aplicaron cambios")
else:
    print("OK: archivo actualizado")
