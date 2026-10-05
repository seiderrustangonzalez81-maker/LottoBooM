from pathlib import Path

p = Path("/home/LottoBooM/templates/base.html")
src = p.read_text(encoding="utf-8")

if "FILTROS_DINAMICOS_V1" in src:
    print("SKIP: ya aplicado")
    raise SystemExit(0)

# Insertar antes del cierre </body>
ancla = "</body>"
if ancla not in src:
    print("ERROR: no encontré </body>")
    raise SystemExit(1)

snippet = """<script>
/* ═══════════════════════════════════════════════════════════════
   FILTROS_DINAMICOS_V1
   - Auto-submit en selects, inputs de texto, fechas dentro de
     cualquier <form method="GET"> — sin botón "Buscar"
   - Debounce 450ms para texto
   - Submit inmediato para selects/fechas
   - Búsqueda por prefijo en <select data-searchable>
   - Barra de progreso suave arriba mientras carga
   ═══════════════════════════════════════════════════════════════ */
(function(){
  'use strict';

  var DEBOUNCE_MS = 450;
  var SKIP_TYPES = { hidden: 1, submit: 1, button: 1, reset: 1, file: 1, image: 1, checkbox: 1, radio: 1 };

  // ─── Barra de progreso superior ───
  function _showProgress(){
    var bar = document.getElementById('lottortFilterBar');
    if (!bar){
      bar = document.createElement('div');
      bar.id = 'lottortFilterBar';
      bar.style.cssText = 'position:fixed;top:0;left:0;right:0;height:3px;z-index:99999;'
                        + 'background:linear-gradient(90deg,#22c55e,#16a34a,#22c55e);'
                        + 'background-size:200% 100%;'
                        + 'animation:lottortFilterSlide 1s linear infinite;'
                        + 'box-shadow:0 0 8px rgba(34,197,94,.6);'
                        + 'transform-origin:left;transition:opacity .2s;opacity:1;';
      document.body.appendChild(bar);

      var style = document.createElement('style');
      style.textContent = '@keyframes lottortFilterSlide{0%{background-position:0% 50%;}100%{background-position:200% 50%;}}';
      document.head.appendChild(style);
    } else {
      bar.style.opacity = '1';
    }
  }

  // ─── Submit "seguro": evita doble submit, muestra barra ───
  var _submitting = false;
  function _submitForm(form){
    if (_submitting) return;
    _submitting = true;
    _showProgress();
    // Recolectar valores vacíos y limpiarlos para URL limpia
    try {
      form.querySelectorAll('input[type="text"], input[type="search"], input[type="date"], select').forEach(function(el){
        if (el.dataset.keepEmpty === '1') return;
        if (el.value === '' || el.value === null || el.value === undefined){
          // Crear un disabled clone para no enviar el campo vacío
          var disabled = el.cloneNode(true);
          disabled.disabled = true;
          el.parentNode.insertBefore(disabled, el);
          el.dataset._disabledForSubmit = '1';
        }
      });
    } catch(_){}
    form.submit();
  }

  // ─── Adjuntar comportamiento a un form ───
  function _attach(form){
    if (form.dataset._filtersBound === '1') return;
    form.dataset._filtersBound = '1';

    var inputs = form.querySelectorAll('select, input[type="text"], input[type="search"], input[type="date"]');
    inputs.forEach(function(el){
      var type = (el.type || '').toLowerCase();
      if (el.tagName === 'SELECT'){
        // Si ya tiene onchange, no duplicar
        if (el.getAttribute('onchange')) return;
        el.addEventListener('change', function(){ _submitForm(form); });
        return;
      }
      if (SKIP_TYPES[type]) return;

      if (type === 'date'){
        // Fechas: submit al cambiar (no en cada tecla)
        el.addEventListener('change', function(){ _submitForm(form); });
        return;
      }

      // Texto/search: debounce
      var timer;
      el.addEventListener('input', function(){
        clearTimeout(timer);
        timer = setTimeout(function(){ _submitForm(form); }, DEBOUNCE_MS);
      });
      // Enter: submit inmediato
      el.addEventListener('keydown', function(ev){
        if (ev.key === 'Enter'){
          ev.preventDefault();
          clearTimeout(timer);
          _submitForm(form);
        }
      });
    });
  }

  // ─── Búsqueda por prefijo en <select data-searchable> ───
  function _attachSelectSearch(sel){
    if (sel.dataset._searchBound === '1') return;
    var opts = sel.querySelectorAll('option');
    if (opts.length <= 8) return;   // no vale la pena si hay pocas
    sel.dataset._searchBound = '1';

    var inp = document.createElement('input');
    inp.type = 'text';
    inp.placeholder = '🔍 Buscar...';
    inp.className = 'form-control form-control-sm mb-1';
    inp.style.fontSize = '.72rem';
    inp.style.background = '#f0fdf4';
    inp.style.border = '1.5px dashed #86efac';

    sel.parentNode.insertBefore(inp, sel);

    inp.addEventListener('input', function(){
      var q = this.value.toLowerCase().trim();
      opts.forEach(function(o){
        // siempre mantener el placeholder (value vacío)
        if (!o.value){ o.hidden = false; o.style.display = ''; return; }
        var txt = (o.textContent || '').toLowerCase().trim();
        var match = !q || txt.startsWith(q) || txt.indexOf(q) !== -1;
        o.hidden = !match;
        o.style.display = match ? '' : 'none';
      });
    });

    inp.addEventListener('keydown', function(ev){
      if (ev.key === 'Escape'){ this.value = ''; this.dispatchEvent(new Event('input')); }
    });
  }

  // ─── Init ───
  function _init(){
    // 1. Formularios GET con inputs de filtro
    var forms = document.querySelectorAll('form');
    forms.forEach(function(form){
      var method = (form.getAttribute('method') || 'get').toLowerCase();
      if (method !== 'get') return;
      // Solo si tiene algún filtro típico
      var tieneFiltro = form.querySelector('input[name="q"], input[name="buscar"], select[name], input[type="date"], input[name^="fecha"]');
      if (!tieneFiltro) return;
      _attach(form);
    });

    // 2. Selects con búsqueda por prefijo (opt-in con data-searchable)
    document.querySelectorAll('select[data-searchable]').forEach(_attachSelectSearch);
  }

  if (document.readyState === 'loading'){
    document.addEventListener('DOMContentLoaded', _init);
  } else {
    _init();
  }

  // Exponer para uso manual
  window.lottortAttachFilters = _init;
})();
</script>
</body>"""

src = src.replace(ancla, snippet, 1)
p.write_text(src, encoding="utf-8")
print("OK: FILTROS_DINAMICOS_V1 aplicado en base.html")

