from pathlib import Path

p = Path("/home/LottoBooM/jugadas/templates/jugadas/apostar.html")
src = p.read_text(encoding="utf-8")

if "lottort-cierre-auto" in src:
    print("SKIP: ya aplicado")
    raise SystemExit(0)

# ═══════════════════════════════════════════════════════════════
# 1) Modal HTML de urgencia
# ═══════════════════════════════════════════════════════════════
modal_html = '''
{# ═══════ MODAL CIERRE AUTOMÁTICO ═══════ #}
<div class="modal fade" id="modalCierreAuto" tabindex="-1" aria-hidden="true" data-bs-backdrop="static" data-bs-keyboard="false">
  <div class="modal-dialog modal-dialog-centered">
    <div class="modal-content" style="border-radius:16px;border:3px solid #DC2626;animation:shk 0.5s ease-in-out;">
      <div class="modal-header" style="background:linear-gradient(135deg,#DC2626,#7f1d1d);color:#fff;border-bottom:2px solid #450a0a;">
        <h5 class="modal-title fw-bold" style="text-shadow:0 1px 2px rgba(0,0,0,.4);">
          <i class="fas fa-exclamation-triangle me-2" style="color:#fde047;"></i>
          ¡CIERRE INMINENTE!
        </h5>
      </div>
      <div class="modal-body" style="text-align:center;">
        <div id="caSorteoNombre" style="font-weight:900;font-size:1.15rem;color:#7f1d1d;margin-bottom:10px;">—</div>
        <div style="background:#fee2e2;border:2px dashed #dc2626;border-radius:12px;padding:14px;margin-bottom:16px;">
          <div style="font-size:.72rem;text-transform:uppercase;font-weight:800;color:#7f1d1d;letter-spacing:.5px;">Tiempo para confirmar</div>
          <div id="caCountdown" style="font-size:3rem;font-weight:900;color:#DC2626;font-family:'Courier New',monospace;line-height:1;margin-top:6px;">10</div>
          <div style="font-size:.65rem;color:#991b1b;font-weight:600;margin-top:4px;">segundos</div>
        </div>
        <div style="font-size:.82rem;color:#7f1d1d;font-weight:700;margin-bottom:14px;">
          Introduce tu contraseña para confirmar la apuesta o <span style="color:#DC2626;">se cancelará</span>.
        </div>
        <input type="password" id="caPassword" class="form-control" placeholder="Contraseña"
               style="border-radius:10px;border:2px solid #dc2626;text-align:center;font-weight:800;font-size:1.05rem;padding:10px;"
               autocomplete="off">
        <div id="caError" style="display:none;background:#fee2e2;border:1.5px solid #dc2626;color:#7f1d1d;padding:6px 10px;border-radius:8px;margin-top:10px;font-weight:700;font-size:.75rem;"></div>
      </div>
      <div class="modal-footer" style="border-top:2px solid #fca5a5;justify-content:center;">
        <button type="button" class="btn fw-bold" id="caConfirmar"
                style="background:linear-gradient(135deg,#DC2626,#7f1d1d);color:#fff;border-radius:10px;padding:10px 32px;font-size:.9rem;">
          <i class="fas fa-check"></i> Confirmar apuesta
        </button>
      </div>
    </div>
  </div>
</div>
<style>
@keyframes shk{0%,100%{transform:translateX(0);}25%{transform:translateX(-6px);}75%{transform:translateX(6px);}}
</style>
'''

# Insertar antes del modalPreview
if 'id="modalPreview"' in src:
    src = src.replace('<div class="modal fade" id="modalPreview"', modal_html + '\n<div class="modal fade" id="modalPreview"', 1)
else:
    idx = src.rfind("{% endblock %}")
    src = src[:idx] + modal_html + src[idx:]
print("OK: modal cierre automatico agregado")

# ═══════════════════════════════════════════════════════════════
# 2) Guardar segundos restantes en sorteosActivos
# ═══════════════════════════════════════════════════════════════
# Modificar agregarPanelSorteo para aceptar minutosRestantes
viejo_agregar = """function agregarPanelSorteo(sid, nombre){
  if (sorteosActivos[sid]) return;
  const btn = document.querySelector(`.sorteo-btn[data-id="${sid}"]`);
  const cerrado = btn ? btn.dataset.cerrado === '1' : false;
  sorteosActivos[sid] = {
    id: sid, nombre: nombre,
    cerrado: cerrado,
    formas_juego: [], tablasActivas: {}, tabActual: null, cargado: false
  };
  ordenSorteos.push(sid);
  renderPanelSorteo(sid);
  cargarConfigSorteo(sid);
}"""

nuevo_agregar = """function agregarPanelSorteo(sid, nombre, minutosRestantes){
  if (sorteosActivos[sid]) return;
  const btn = document.querySelector(`.sorteo-btn[data-id="${sid}"]`);
  const cerrado = btn ? btn.dataset.cerrado === '1' : false;
  var segs = (typeof minutosRestantes === 'number' && minutosRestantes > 0) ? minutosRestantes * 60 : null;
  sorteosActivos[sid] = {
    id: sid, nombre: nombre,
    cerrado: cerrado,
    minutos_restantes: minutosRestantes,
    cierra_en: segs ? Date.now() + segs * 1000 : null,
    forma_cancelada: false,
    formas_juego: [], tablasActivas: {}, tabActual: null, cargado: false
  };
  ordenSorteos.push(sid);
  renderPanelSorteo(sid);
  cargarConfigSorteo(sid);
  // Arrancar timer si aplica
  if (typeof _iniciarTimerCierre === 'function') _iniciarTimerCierre();
}"""

if viejo_agregar not in src:
    print("WARN: no pude modificar agregarPanelSorteo (forma distinta)")
else:
    src = src.replace(viejo_agregar, nuevo_agregar, 1)
    print("OK: agregarPanelSorteo guarda timer")

# ═══════════════════════════════════════════════════════════════
# 3) Modificar el click de sorteos para pasar minutos_restantes
# ═══════════════════════════════════════════════════════════════
viejo_click = """          } else {
            b.classList.add('active');
            agregarPanelSorteo(sid, nombre);
          }"""
nuevo_click = """          } else {
            b.classList.add('active');
            var mins = parseInt(b.dataset.minutos || '0', 10) || 0;
            agregarPanelSorteo(sid, nombre, mins);
          }"""

if viejo_click not in src:
    print("WARN: no encontre el click de sorteos")
else:
    src = src.replace(viejo_click, nuevo_click, 1)
    print("OK: click de sorteos pasa minutos")

# ═══════════════════════════════════════════════════════════════
# 4) Guardar minutos_restantes en el boton de sorteo
# ═══════════════════════════════════════════════════════════════
viejo_boton = '''        return `
          <button type="button" class="sorteo-btn${extraCls}" data-id="${s.id}" data-nombre="${esc(s.nombre)}" data-cerrado="${cerrado ? '1' : '0'}">
            <span>${esc(s.nombre)}</span>
            ${badge}
          </button>`;'''

nuevo_boton = '''        return `
          <button type="button" class="sorteo-btn${extraCls}" data-id="${s.id}" data-nombre="${esc(s.nombre)}" data-cerrado="${cerrado ? '1' : '0'}" data-minutos="${s.minutos_restantes || 0}">
            <span>${esc(s.nombre)}</span>
            ${badge}
          </button>`;'''

if viejo_boton not in src:
    print("WARN: no encontre el template del boton de sorteo")
else:
    src = src.replace(viejo_boton, nuevo_boton, 1)
    print("OK: boton de sorteo incluye minutos_restantes")

# ═══════════════════════════════════════════════════════════════
# 5) Sistema de timers + modal (al final del script)
# ═══════════════════════════════════════════════════════════════
sistema_timers = r'''
/* ═══════════════════════════════════════════════════════════════
   lottort-cierre-auto: Sistema de cierre automático
   - Countdown visible en cada tab (< 5min)
   - Modal de urgencia a T-15s con countdown 10s
   - Cancela el sorteo si no se confirma
   ═══════════════════════════════════════════════════════════════ */
var _caTimerInterval = null;
var _caModalAbierto = false;
var _caSorteoActual = null;
var _caCountdownInterval = null;

function _iniciarTimerCierre(){
  if (_caTimerInterval) return;
  _caTimerInterval = setInterval(_tickCierre, 1000);
}

function _tickCierre(){
  var ahora = Date.now();
  Object.keys(sorteosActivos).forEach(function(sid){
    var s = sorteosActivos[sid];
    if (!s.cierra_en || s.forma_cancelada) return;
    var restante = Math.max(0, Math.floor((s.cierra_en - ahora) / 1000));

    // Actualizar countdown visual en el tab si < 5min
    var btn = document.querySelector('.sorteo-btn[data-id="' + sid + '"]');
    if (btn && restante > 0 && restante < 300){
      var sh = btn.querySelector('.sh');
      if (sh){
        var mm = Math.floor(restante / 60);
        var ss = String(restante % 60).padStart(2, '0');
        sh.textContent = '⏱ ' + mm + ':' + ss;
        sh.style.color = restante < 60 ? '#dc2626' : '#b45309';
        sh.style.fontWeight = '800';
      }
    }

    // Disparar modal a T-15s (solo cliente y comercial)
    if (!_caModalAbierto && restante <= 15 && restante > 0 && !ES_BANCO_O_SUPER){
      if (!s.cargado) return;  // esperar config
      var tieneJugadas = _sorteoTieneJugadas(sid);
      if (tieneJugadas){
        _caSorteoActual = sid;
        _abrirModalCierre(sid);
      }
    }

    // Si llegó a 0 sin confirmar → marcar como cancelable (el backend lo rechazará después)
    if (restante === 0 && !s.forma_cancelada){
      s.forma_cancelada = true;
    }
  });
}

function _sorteoTieneJugadas(sid){
  var s = sorteosActivos[sid];
  if (!s || !s.tablasActivas) return false;
  var tiene = false;
  Object.keys(s.tablasActivas).forEach(function(tk){
    var def = TABLE_DEFS[tk];
    var st = s.tablasActivas[tk];
    if (!def || !st) return;
    st.rows.forEach(function(row){
      if (tiene) return;
      if (def.kind === 'posiciones'){
        for (var p = 0; p < 3; p++){
          if ((row.posNums[p] || '').trim() && parseFloat(row.posMontos[p]) > 0) tiene = true;
        }
      } else if (def.kind === 'vs_groups'){
        if (row.numA && row.numB && parseFloat(row.monto) > 0) tiene = true;
      } else {
        if ((row.num || '').trim()){
          s.forms.forEach(function(f){
            if (parseFloat(row.montos[f]) > 0) tiene = true;
          });
        }
      }
    });
  });
  return tiene;
}

function _abrirModalCierre(sid){
  if (_caModalAbierto) return;
  _caModalAbierto = true;
  var s = sorteosActivos[sid];
  if (!s) return;

  document.getElementById('caSorteoNombre').textContent = s.nombre;
  document.getElementById('caPassword').value = '';
  document.getElementById('caPassword').disabled = false;
  document.getElementById('caError').style.display = 'none';

  var modalEl = document.getElementById('modalCierreAuto');
  var modal = new bootstrap.Modal(modalEl);
  modal.show();

  // Focus al input
  setTimeout(function(){
    var inp = document.getElementById('caPassword');
    if (inp) inp.focus();
  }, 300);

  // Countdown 10s
  var restante = 10;
  var cdEl = document.getElementById('caCountdown');
  if (cdEl) cdEl.textContent = restante;

  _caCountdownInterval = setInterval(function(){
    restante--;
    if (cdEl) cdEl.textContent = restante;
    if (restante <= 0){
      _cancelarPorTiempo();
    }
  }, 1000);
}

function _cancelarPorTiempo(){
  if (_caCountdownInterval){ clearInterval(_caCountdownInterval); _caCountdownInterval = null; }
  var sid = _caSorteoActual;
  if (!sid) return;

  // Cerrar modal
  var modalEl = document.getElementById('modalCierreAuto');
  var modal = bootstrap.Modal.getInstance(modalEl);
  if (modal) modal.hide();
  _caModalAbierto = false;
  _caSorteoActual = null;

  // Cancelar el sorteo del carrito
  var s = sorteosActivos[sid];
  var nombreSorteo = s ? s.nombre : 'sorteo';

  // Quitar panel
  if (typeof quitarPanelSorteo === 'function') quitarPanelSorteo(sid);

  // Toast rojo
  if (typeof toast === 'function'){
    toast('⏰ Tu jugada para <b>' + nombreSorteo + '</b> se canceló por no confirmar en el tiempo solicitado.', 'danger');
  } else {
    alert('Tu jugada para ' + nombreSorteo + ' se canceló por no confirmar en el tiempo solicitado.');
  }

  // Reset si no quedan sorteos
  if (!ordenSorteos.length){
    var cont = document.getElementById('panelesSorteo');
    if (cont) cont.innerHTML = '';
    if (typeof actualizarCountSorteos === 'function') actualizarCountSorteos();
    if (typeof recalcGlobal === 'function') recalcGlobal();
  }
}

// Hook del botón confirmar y Enter en el input
document.addEventListener('DOMContentLoaded', function(){
  var btnConf = document.getElementById('caConfirmar');
  var inpPwd = document.getElementById('caPassword');

  function confirmarUrgente(){
    if (!_caSorteoActual) return;
    var pwd = (inpPwd.value || '').trim();
    if (!pwd){
      document.getElementById('caError').textContent = 'Introduce la contraseña.';
      document.getElementById('caError').style.display = 'block';
      return;
    }
    inpPwd.disabled = true;
    btnConf.disabled = true;
    btnConf.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Verificando...';

    fetch("{% url 'jugadas:api_verificar_password' %}", {
      method: 'POST',
      headers: { 'X-CSRFToken': CSRF, 'Content-Type': 'application/json' },
      body: JSON.stringify({ password: pwd })
    })
    .then(function(r){ return r.json(); })
    .then(function(d){
      if (!d.success){
        inpPwd.disabled = false;
        btnConf.disabled = false;
        btnConf.innerHTML = '<i class="fas fa-check"></i> Confirmar apuesta';
        document.getElementById('caError').textContent = 'Contraseña incorrecta.';
        document.getElementById('caError').style.display = 'block';
        return;
      }
      // Contraseña OK → cancelar countdown, cerrar modal, guardar
      if (_caCountdownInterval){ clearInterval(_caCountdownInterval); _caCountdownInterval = null; }
      var modalEl = document.getElementById('modalCierreAuto');
      var modal = bootstrap.Modal.getInstance(modalEl);
      if (modal) modal.hide();
      _caModalAbierto = false;
      _caSorteoActual = null;

      // Guardar directamente (sin preview por urgencia)
      var b = document.getElementById('btnGo');
      if (b) { b.disabled = true; b.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Guardando...'; }
      enviarApuesta(false);
    })
    .catch(function(e){
      inpPwd.disabled = false;
      btnConf.disabled = false;
      btnConf.innerHTML = '<i class="fas fa-check"></i> Confirmar apuesta';
      document.getElementById('caError').textContent = 'Error de conexión.';
      document.getElementById('caError').style.display = 'block';
    });
  }

  if (btnConf){
    btnConf.addEventListener('click', confirmarUrgente);
  }
  if (inpPwd){
    inpPwd.addEventListener('keydown', function(e){
      if (e.key === 'Enter'){ e.preventDefault(); confirmarUrgente(); }
    });
  }
});

'''

# Insertar antes de "console.log('[apostar] Funciones expuestas"
ancla_js = "window.autoformatear = autoformatear;"
if ancla_js not in src:
    print("WARN: no encontre el ancla final del JS")
else:
    src = src.replace(ancla_js, sistema_timers + ancla_js, 1)
    print("OK: sistema de timers agregado")

# Exponer la funcion al scope global para que agregarPanelSorteo la encuentre
if "window._iniciarTimerCierre = _iniciarTimerCierre;" not in src:
    src = src.replace(
        "window.autoformatear = autoformatear;",
        "window._iniciarTimerCierre = _iniciarTimerCierre;\nwindow.autoformatear = autoformatear;",
        1,
    )
    print("OK: _iniciarTimerCierre expuesta")

p.write_text(src, encoding="utf-8")

# Verificacion
assert "lottort-cierre-auto" in src
assert "modalCierreAuto" in src
assert "_abrirModalCierre" in src
assert "_cancelarPorTiempo" in src
print("OK: todas las marcas presentes")

# Sintaxis basica
import re
if src.count("<script") != src.count("</script>"):
    print("WARN: desbalance de <script> tags")
else:
    print("OK: scripts balanceados")
