from pathlib import Path

p = Path("/home/LottoBooM/jugadas/templates/jugadas/apostar.html")
src = p.read_text(encoding="utf-8")

# Añadir una función global que limpia TODOS los modales abiertos
helper = """
// ═══════ LIMPIEZA GLOBAL DE MODALES ═══════
window._cerrarTodosLosModales = function(){
  try {
    // Cerrar modales de Bootstrap por instancia
    document.querySelectorAll('.modal.show').forEach(function(el){
      var inst = bootstrap.Modal.getInstance(el);
      if (inst) {
        try { inst.hide(); } catch(_){}
      }
      // Fallback manual
      setTimeout(function(){
        el.classList.remove('show');
        el.style.display = 'none';
        el.setAttribute('aria-hidden', 'true');
      }, 200);
    });
    // Quitar backdrops huérfanos
    setTimeout(function(){
      document.querySelectorAll('.modal-backdrop').forEach(function(b){ b.remove(); });
      document.body.classList.remove('modal-open');
      document.body.style.removeProperty('overflow');
      document.body.style.removeProperty('padding-right');
    }, 400);
  } catch(e){ console.warn('[modal cleanup]', e); }
};
"""

# Insertar antes de "console.log('[apostar] Funciones expuestas"
ancla = "window.autoformatear = autoformatear;"
if ancla in src and "_cerrarTodosLosModales" not in src:
    src = src.replace(ancla, helper + "\n" + ancla, 1)
    p.write_text(src, encoding="utf-8")
    print("OK: helper _cerrarTodosLosModales añadido")
else:
    print("SKIP: ya existe o no se encontro ancla")
