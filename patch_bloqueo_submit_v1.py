from pathlib import Path
import re

p = Path("/home/LottoBooM/jugadas/templates/jugadas/apostar.html")
src = p.read_text(encoding="utf-8")

if "BLOQUEO_SUBMIT_V1" in src:
    print("SKIP: ya aplicado")
    raise SystemExit(0)

# ═══════════════════════════════════════════════════════════════
# 1) Helper global: ¿hay filas con excepción activa?
# ═══════════════════════════════════════════════════════════════
helper = r"""
/* ═══════════════════════════════════════════════════════════════
   BLOQUEO_SUBMIT_V1
   Devuelve { bloqueado: bool, motivos: [string], filas: [Element] }
   Revisa el DOM (no cachea) para no perder estado.
   ═══════════════════════════════════════════════════════════════ */
function _hayExcepcionesActivas(){
  var filas = document.querySelectorAll('tr.fila-excede');
  if (!filas.length) return { bloqueado: false, motivos: [], filas: [] };
  var motivos = [];
  filas.forEach(function(tr){
    var m = tr.getAttribute('data-motivo') || 'excede límite';
    var p = tr.closest('.sp-panel');
    var sid = p ? p.getAttribute('data-sorteo-id') : '?';
    motivos.push('Sorteo ' + sid + ': ' + m);
  });
  return { bloqueado: true, motivos: motivos, filas: Array.from(filas) };
}

function _avisarExcepciones(exc){
  // Pinta de rojo el botón Enviar temporalmente
  var btns = document.querySelectorAll('#btnEnviar, .btn-enviar, button[type="submit"]');
  btns.forEach(function(b){
    b.classList.add('btn-excede-pulse');
    setTimeout(function(){ b.classList.remove('btn-excede-pulse'); }, 1600);
  });
  // Scroll a la primera fila roja
  if (exc.filas[0]) exc.filas[0].scrollIntoView({ behavior: 'smooth', block: 'center' });
  // Toast
  var msg = 'No se puede enviar: ' + exc.motivos.length + ' fila(s) exceden el límite';
  if (typeof toast === 'function') toast('🚫 ' + msg, 'danger');
  else alert(msg + '\n\n' + exc.motivos.slice(0, 5).join('\n'));
}
"""

# Insertar antes del comentario BLOQUEO_PARLET_CANDADO_V1 (que ya existe)
ancla = "/* ═══════════════════════════════════════════════════════════════\n   BLOQUEO_PARLET_CANDADO_V1"
if ancla not in src:
    print("ERROR: no encontré ancla BLOQUEO_PARLET_CANDADO_V1")
    raise SystemExit(1)
src = src.replace(ancla, helper + "\n" + ancla, 1)
print("OK 1: helpers _hayExcepcionesActivas + _avisarExcepciones insertados")


# ═══════════════════════════════════════════════════════════════
# 2) Guard en el/los handlers de envío  <AJUSTAR según grep>
# ═══════════════════════════════════════════════════════════════
# Buscamos un botón con id/clase conocidos y envolvemos su listener existente.
# Estrategia: escuchar en CAPTURA en el document, y si el click viene de un
# botón de envío y hay excepciones, abortar.
guard = r"""
/* BLOQUEO_SUBMIT_V1: interceptor en captura */
document.addEventListener('click', function(ev){
  var btn = ev.target.closest && ev.target.closest('#btnEnviar, .btn-enviar, button[type="submit"], [data-action="enviar"]');
  if (!btn) return;
  var exc = _hayExcepcionesActivas();
  if (!exc.bloqueado) return;
  ev.preventDefault();
  ev.stopPropagation();
  ev.stopImmediatePropagation();
  _avisarExcepciones(exc);
  return false;
}, true);

document.addEventListener('submit', function(ev){
  var exc = _hayExcepcionesActivas();
  if (!exc.bloqueado) return;
  ev.preventDefault();
  ev.stopPropagation();
  _avisarExcepciones(exc);
  return false;
}, true);
"""

# Inyectar justo antes de </script> final (último cierre del bloque grande)
idx = src.rfind("</script>")
if idx == -1:
    print("ERROR: no encontré </script>")
    raise SystemExit(1)
src = src[:idx] + guard + "\n" + src[idx:]
print("OK 2: interceptor de submit insertado")


# ═══════════════════════════════════════════════════════════════
# 3) CSS del pulse
# ═══════════════════════════════════════════════════════════════
if "btn-excede-pulse" not in src:
    css = """
  /* BLOQUEO_SUBMIT_V1 */
  @keyframes btnExcedePulse{
    0%,100%{ transform: scale(1); box-shadow: 0 0 0 0 rgba(220,38,38,.55); }
    50%    { transform: scale(1.03); box-shadow: 0 0 0 8px rgba(220,38,38,0); }
  }
  .btn-excede-pulse{
    animation: btnExcedePulse 0.55s ease-in-out 3;
    background: #dc2626 !important;
    border-color: #dc2626 !important;
    color: #fff !important;
  }
"""
    css_idx = src.find("</style>")
    if css_idx == -1:
        print("WARN: no encontré </style>, CSS no insertado")
    else:
        src = src[:css_idx] + css + src[css_idx:]
        print("OK 3: CSS insertado")
else:
    print("SKIP 3: CSS ya existe")

p.write_text(src, encoding="utf-8")

print()
print("═══ Resumen ═══")
print("BLOQUEO_SUBMIT_V1            :", src.count("BLOQUEO_SUBMIT_V1"))
print("_hayExcepcionesActivas       :", src.count("_hayExcepcionesActivas"))
print("btn-excede-pulse             :", src.count("btn-excede-pulse"))
