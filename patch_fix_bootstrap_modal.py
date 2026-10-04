from pathlib import Path
import re

p = Path("/home/LottoBooM/jugadas/templates/jugadas/apostar.html")
src = p.read_text(encoding="utf-8")

cambios = []

# ═══════════════════════════════════════════════════════════════
# FIX 1: Reemplazar TODOS los new bootstrap.Modal(el) por getOrCreateInstance
# ═══════════════════════════════════════════════════════════════
patron = re.compile(r"new bootstrap\.Modal\(([^)]+)\)")
src_nuevo, n = patron.subn(r"bootstrap.Modal.getOrCreateInstance(\1)", src)

if n > 0:
    src = src_nuevo
    cambios.append(f"FIX 1: OK ({n} ocurrencias reemplazadas)")
else:
    cambios.append("FIX 1: SKIP (no habia new bootstrap.Modal)")

# ═══════════════════════════════════════════════════════════════
# FIX 2: Al mostrar modalPreview, cerrar el anterior correctamente
# ═══════════════════════════════════════════════════════════════
viejo_2 = """function mostrarPreviewApuesta(data){
  // ... código antes"""
# Buscar la función y parchear el arranque
patron_2 = re.compile(
    r"(function mostrarPreviewApuesta\(data\)\{)",
)
m2 = patron_2.search(src)
if m2:
    # Insertar guardia al inicio
    guard = """function mostrarPreviewApuesta(data){
  // Cerrar cualquier modal previo de manera segura
  try {
    var _pwdModal = bootstrap.Modal.getInstance(document.getElementById('modalPwd'));
    if (_pwdModal) _pwdModal.hide();
  } catch(_){}
  // Pequeño delay para que la animación de cierre termine
  setTimeout(function(){ _mostrarPreviewApuesta_real(data); }, 350);
}

function _mostrarPreviewApuesta_real(data){
"""
    if "_mostrarPreviewApuesta_real" in src:
        cambios.append("FIX 2: SKIP (ya aplicado)")
    else:
        src = src[:m2.start()] + guard + src[m2.end():]
        cambios.append("FIX 2: OK (delay de 350ms antes de mostrar preview)")
else:
    cambios.append("FIX 2: ERROR (no encontre mostrarPreviewApuesta)")

# ═══════════════════════════════════════════════════════════════
# FIX 3: Al cerrar modalPreview, verificar que exista
# ═══════════════════════════════════════════════════════════════
patron_3 = re.compile(
    r"bootstrap\.Modal\.getInstance\(document\.getElementById\('modalPreview'\)\)\.hide\(\);"
)
def fix_getinstance(m):
    return """(function(){
        var _mp = bootstrap.Modal.getInstance(document.getElementById('modalPreview'));
        if (_mp) { _mp.hide(); } else {
          var _mpe = document.getElementById('modalPreview');
          if (_mpe) { _mpe.classList.remove('show'); _mpe.style.display = 'none'; document.body.classList.remove('modal-open'); document.body.style.removeProperty('overflow'); document.body.style.removeProperty('padding-right'); }
          var _bk = document.querySelector('.modal-backdrop');
          if (_bk) _bk.remove();
        }
      })();"""

src_nuevo3, n3 = patron_3.subn(fix_getinstance, src)
if n3 > 0:
    src = src_nuevo3
    cambios.append(f"FIX 3: OK ({n3} ocurrencias con safe-hide)")
else:
    cambios.append("FIX 3: SKIP (no habia getInstance directo)")

# ═══════════════════════════════════════════════════════════════
# FIX 4: Al cerrar modalPwd, safe hide también
# ═══════════════════════════════════════════════════════════════
patron_4 = re.compile(
    r"bootstrap\.Modal\.getInstance\(\\\$?\('modalPwd'\)\)\.hide\(\);"
)
def fix_pwd(m):
    return """(function(){
        var _mp = bootstrap.Modal.getInstance(document.getElementById('modalPwd'));
        if (_mp) { _mp.hide(); } else {
          var _mpe = document.getElementById('modalPwd');
          if (_mpe) { _mpe.classList.remove('show'); _mpe.style.display = 'none'; }
        }
      })();"""
src_nuevo4, n4 = patron_4.subn(fix_pwd, src)
if n4 > 0:
    src = src_nuevo4
    cambios.append(f"FIX 4: OK ({n4} safe-hide de modalPwd)")
else:
    cambios.append("FIX 4: SKIP")

p.write_text(src, encoding="utf-8")

# Reporte
print("═══ REPORTE ═══")
for c in cambios:
    print(f"  {c}")

# Contar
print(f"\nnew bootstrap.Modal restantes: {src.count('new bootstrap.Modal')}")
print(f"getOrCreateInstance: {src.count('getOrCreateInstance')}")
print(f"modalPreview occurrences: {src.count('modalPreview')}")
