from pathlib import Path

p = Path("/home/LottoBooM/jugadas/templates/jugadas/apostar.html")
src = p.read_text(encoding="utf-8")

# Reemplazar la lógica de visibilidad del botón
viejo = """  // ═══ VISIBILIDAD DE BOTONES ═══
  function _actualizarVisibilidadBotones(){
    var btnRetiro = document.getElementById('lottortRetiroBtn');
    var btnLimites = document.getElementById('lottortLimitesBtn');
    if (!btnRetiro || !btnLimites) return;

    // Retiro: solo si NO es cliente y hay cliente + FP seleccionados
    var esGestor = !ES_CLIENTE;
    var tieneDatos = cliente && cliente.id && fpSel;
    btnRetiro.style.display = (esGestor && tieneDatos) ? 'inline-flex' : 'none';

    // Limites: siempre visible cuando hay cliente + al menos 1 sorteo activo
    var tieneSorteo = typeof ordenSorteos !== 'undefined' && ordenSorteos.length > 0;
    btnLimites.style.display = (tieneDatos && tieneSorteo) ? 'inline-flex' : 'none';
  }"""

nuevo = """  // ═══ VISIBILIDAD DE BOTONES ═══
  function _actualizarVisibilidadBotones(){
    var btnRetiro = document.getElementById('lottortRetiroBtn');
    var btnLimites = document.getElementById('lottortLimitesBtn');
    var wrap = document.getElementById('recargaQuickWrap');
    if (!btnRetiro || !btnLimites) return;

    var tieneSorteo = (typeof ordenSorteos !== 'undefined') && ordenSorteos.length > 0;
    var esGestor = !ES_CLIENTE;
    var tieneCliente = cliente && cliente.id;
    var tieneFP = !!fpSel;
    var tieneDatos = tieneCliente && tieneFP;

    // Mostrar el wrap si hay sorteo activo O datos completos
    if (wrap) {
      wrap.style.display = (tieneSorteo || tieneDatos) ? 'block' : 'none';
    }

    // Retiro: solo gestor + cliente + FP
    btnRetiro.style.display = (esGestor && tieneDatos) ? 'inline-flex' : 'none';

    // Límites: siempre visible si hay sorteo activo (aunque no haya cliente/FP aún)
    btnLimites.style.display = tieneSorteo ? 'inline-flex' : 'none';
  }"""

if "_actualizarVisibilidadBotones" not in src:
    print("ERROR: no existe la función")
    raise SystemExit(1)

if viejo not in src:
    print("WARN: no matcheo el bloque exacto, buscando variante...")
    # Buscar cualquier versión de la función
    import re
    patron = re.compile(
        r"// ═+ VISIBILIDAD DE BOTONES ═+.*?function _actualizarVisibilidadBotones\(\)\{.*?\n  \}",
        re.DOTALL,
    )
    if patron.search(src):
        src_new, n = patron.subn(nuevo, src, count=1)
        if n:
            src = src_new
            print("OK: reemplazado via regex")
    else:
        print("ERROR: no encontre la función para reemplazar")
        raise SystemExit(1)
else:
    src = src.replace(viejo, nuevo, 1)
    print("OK: reemplazado exacto")

p.write_text(src, encoding="utf-8")
print("OK: visibilidad de botones actualizada")
