from pathlib import Path

p = Path("/home/LottoBooM/jugadas/templates/jugadas/apostar.html")
src = p.read_text(encoding="utf-8")

if "lottort-apo-polling" in src:
    print("SKIP: ya aplicado")
    raise SystemExit(0)

# Insertar el script antes de "console.log('[apostar] Funciones expuestas"
ancla = "window.autoformatear = autoformatear;"
if ancla not in src:
    print("ERROR: no encontre el ancla")
    raise SystemExit(1)

script_polling = '''
/* ═══════════════════════════════════════════════════════════════
   lottort-apo-polling: Polling del fondo del cliente cada 10s
   Solo cuando hay cliente + FP seleccionados
   ═══════════════════════════════════════════════════════════════ */
(function(){
  var POLL_MS = 10000;
  var timer = null;
  var lastSaldo = null;

  function pollFondo(){
    // Solo si hay cliente y FP seleccionados
    if (!cliente || !fpSel) return;
    var clienteId = cliente.id;

    fetch("{% url 'usuarios:api_state' %}?scope=recarga-directa&cliente_id=" + clienteId, {
      headers: { 'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json' },
      credentials: 'same-origin',
    })
    .then(function(r){ return r.ok ? r.json() : null; })
    .then(function(d){
      if (!d || !d.success) return;

      // Buscar el saldo de la FP seleccionada
      var saldoNuevo = 0;
      var fondos = d.fondos || {};
      // Buscar por nombre (el backend devuelve nombre → monto)
      var chipActivo = document.querySelector('.fp-chip.active');
      if (chipActivo && chipActivo.dataset.n){
        var nomFP = chipActivo.dataset.n;
        // Quitar prefijos como "Tarjeta" exacto
        for (var k in fondos){
          if (k === nomFP || k.indexOf(nomFP) !== -1 || nomFP.indexOf(k) !== -1){
            saldoNuevo = fondos[k];
            break;
          }
        }
      }

      // Si cambió el saldo, actualizar chip + recalcular
      if (lastSaldo !== null && Math.abs(saldoNuevo - lastSaldo) > 0.009){
        // Actualizar saldo global
        saldoFP = saldoNuevo;
        if (typeof recalcGlobal === 'function') recalcGlobal();
        if (typeof toast === 'function') {
          toast('💰 Fondo actualizado: $' + saldoNuevo.toFixed(2), 'success');
        }
      }
      lastSaldo = saldoNuevo;

      // Actualizar el chip visual
      if (chipActivo){
        var strongEl = chipActivo.querySelector('strong');
        if (strongEl && saldoNuevo > 0){
          strongEl.textContent = '$' + saldoNuevo.toFixed(2);
        }
      }
    })
    .catch(function(){ /* silencioso */ });
  }

  function startPolling(){
    if (timer) clearInterval(timer);
    lastSaldo = null;
    timer = setInterval(pollFondo, POLL_MS);
    // Primera llamada a los 2s (dar tiempo a cargar todo)
    setTimeout(pollFondo, 2000);
  }

  function stopPolling(){
    if (timer) { clearInterval(timer); timer = null; }
  }

  // Escuchar cambios de cliente y FP
  var _pollBound = false;
  function tryBind(){
    if (_pollBound) return;
    var selCli = document.getElementById('selCliente');
    var listaFP = document.getElementById('listaFP');
    if (!selCli || !listaFP) { setTimeout(tryBind, 500); return; }
    _pollBound = true;

    selCli.addEventListener('change', function(){
      stopPolling();
      if (this.value) startPolling();
    });

    listaFP.addEventListener('click', function(e){
      if (e.target.closest('.fp-chip')){
        stopPolling();
        setTimeout(function(){
          if (fpSel) startPolling();
        }, 500);
      }
    });

    // Si ya hay cliente seleccionado al cargar
    if (selCli.value) startPolling();
  }
  tryBind();

  // Al volver a la pestaña
  document.addEventListener('visibilitychange', function(){
    if (!document.hidden && cliente && fpSel){
      pollFondo();
    }
  });
})();

'''

src = src.replace(ancla, script_polling + ancla, 1)
p.write_text(src, encoding="utf-8")
print("OK: polling agregado a apostar.html")

# Verificaciones
assert "lottort-apo-polling" in src
assert "pollFondo" in src
print("OK verificacion")
