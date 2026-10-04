from pathlib import Path
import re

p = Path("/home/LottoBooM/jugadas/templates/jugadas/mis_apuestas.html")
src = p.read_text(encoding="utf-8")

if "_waCompartirMultiple" in src:
    print("SKIP: ya aplicado")
    raise SystemExit(0)

# ═══════════════════════════════════════════════════════════════
# 1. Añadir CSS para el botón general
# ═══════════════════════════════════════════════════════════════
css_extra = """
/* Botón compartir todas */
.ma-compartir-todas {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 10px 20px;
  background: linear-gradient(145deg, #25d366, #128c7e);
  color: #fff; border: 2px solid #075e54;
  border-radius: 12px;
  font-weight: 800; font-size: .85rem;
  cursor: pointer; font-family: inherit;
  box-shadow: 3px 3px 0 #064e3b;
  text-shadow: 0 1px 2px rgba(0,0,0,.25);
  letter-spacing: .3px;
  transition: .15s;
}
.ma-compartir-todas:hover { transform: translate(-1px,-1px); box-shadow: 4px 4px 0 #064e3b; }
.ma-compartir-todas:active { transform: translate(1px,1px); box-shadow: 1px 1px 0 #064e3b; }
.ma-compartir-todas i { color: #fff !important; }
"""

# Insertar CSS antes de </style>
if "ma-compartir-todas" not in src:
    idx = src.rfind("</style>")
    if idx > 0:
        src = src[:idx] + css_extra + src[idx:]
        print("OK: CSS del botón general agregado")

# ═══════════════════════════════════════════════════════════════
# 2. Modificar buildBoletaWhatsappText para mejor formato
# ═══════════════════════════════════════════════════════════════
# (ya existe, dejarlo así)

# ═══════════════════════════════════════════════════════════════
# 3. Añadir función _waCompartirMultiple + handler botón general
# ═══════════════════════════════════════════════════════════════

# Insertar antes del cierre del <script> principal
# Ancla: la última función buildBoletaWhatsappText o el handler btn-wa

nueva_logica = """
/* ═══════════════════════════════════════════════════════════════
   Compartir múltiples boletas por WhatsApp con división inteligente
   ═══════════════════════════════════════════════════════════════ */
function _waCompartirMultiple(boletas, opts){
  opts = opts || {};
  var maxChars = opts.maxChars || 3000;
  var titulo = opts.titulo || '📋 *Boletas — LottoBooM*';

  if (!boletas.length){
    showToast('No hay boletas para compartir', 'warn');
    return;
  }

  // Construir bloque de cada boleta
  var bloques = boletas.map(function(b){
    return buildBoletaWhatsappText(b);
  });

  // Calcular tamaño del mensaje con encabezado
  var totalFiltro = boletas.reduce(function(s, b){
    var t = (b.dataset && b.dataset.boletaTotal) ? parseFloat(b.dataset.boletaTotal) : 0;
    return s + (t || 0);
  }, 0);

  var header = titulo + '\\n'
             + '📅 Total boletas: ' + boletas.length + '\\n'
             + '💵 Total general: $' + totalFiltro.toFixed(2) + '\\n';

  var bloquesTotales = [];
  var actual = header;
  var idxInicio = 0;

  for (var i = 0; i < bloques.length; i++){
    var bloque = '\\n━━━━━━━━━━━━━━━━━━━━\\n' + bloques[i];
    if (actual.length + bloque.length > maxChars && actual !== header){
      bloquesTotales.push(actual);
      actual = '_(continuación)_\\n' + bloque;
      idxInicio = i;
    } else {
      actual += bloque;
    }
  }
  if (actual) bloquesTotales.push(actual);

  // Si es 1 solo bloque → abrir directo
  if (bloquesTotales.length === 1){
    var url = 'https://wa.me/?text=' + encodeURIComponent(bloquesTotales[0]);
    window.open(url, '_blank', 'noopener,noreferrer');
    showToast('Abriendo WhatsApp…', 'pos');
    return;
  }

  // Múltiples bloques → abrir 1ro + copiar 2do al portapapeles
  var url1 = 'https://wa.me/?text=' + encodeURIComponent(bloquesTotales[0]);
  window.open(url1, '_blank', 'noopener,noreferrer');

  if (bloquesTotales.length >= 2){
    var resto = bloquesTotales.slice(1).join('\\n\\n---\\n\\n');
    if (navigator.clipboard && navigator.clipboard.writeText){
      navigator.clipboard.writeText(resto).then(function(){
        showToast('✅ Mensaje 1/2 abierto en WhatsApp. El resto de las boletas (2/2) está copiado — pégalo en el chat.', 'pos');
      }).catch(function(){
        showToast('⚠️ Abierto primer mensaje. Continúa manualmente las siguientes boletas.', 'warn');
      });
    } else {
      showToast('✅ Abierto primer mensaje. Continúa manualmente las siguientes boletas.', 'warn');
    }
  }
}
"""

# Insertar antes de "// WHATSAPP" (que ya existe)
if "function buildBoletaWhatsappText" in src and "_waCompartirMultiple" not in src:
    # Insertar antes de la definición de buildBoletaWhatsappText
    patron = re.compile(r"(function buildBoletaWhatsappText\(boletaEl\)\{)")
    m = patron.search(src)
    if m:
        src = src[:m.start()] + nueva_logica + "\n" + src[m.start():]
        print("OK: función _waCompartirMultiple insertada")
    else:
        print("WARN: no encontre buildBoletaWhatsappText")
else:
    print("SKIP: ya tenia _waCompartirMultiple o falta base")

p.write_text(src, encoding="utf-8")
print("OK: template mis_apuestas.html actualizado")

