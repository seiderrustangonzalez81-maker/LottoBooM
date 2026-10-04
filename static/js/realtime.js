/* ═══════════════════════════════════════════════════════════════
   REALTIME_ONLINE_V1 · Polling de saldos + estado online
   Uso:
     <tr data-cliente-id="42">
       <td class="cliente-saldo">$0.00</td>
       <td><span class="status-dot"></span></td>
     </tr>
     Realtime.initClientes([...ids], {interval: 4000});
   ═══════════════════════════════════════════════════════════════ */
window.Realtime = (function(){
  'use strict';

  function fetchSaldos(ids){
    var qs = ids.map(function(i){ return 'ids[]=' + encodeURIComponent(i); }).join('&');
    return fetch('/roles/api/saldos-clientes/?' + qs, {credentials:'same-origin'})
      .then(function(r){ return r.ok ? r.json() : null; })
      .catch(function(){ return null; });
  }

  function aplicar(rows, porId){
    var actualizados = 0;
    Object.keys(rows).forEach(function(id){
      var c = porId[id];
      var nodos = rows[id];
      if (!c) return;
      nodos.forEach(function(n){
        var s = n.querySelector('.cliente-saldo, .saldo-valor, [data-saldo]');
        if (s) s.textContent = '$' + (c.saldo || 0).toFixed(2);
        var d = n.querySelector('.status-dot, [data-online]');
        if (d) d.classList.toggle('online', !!c.online);
      });
      actualizados++;
    });
    var el = document.getElementById('realtime-ts');
    if (el) el.textContent = '· ' + new Date().toLocaleTimeString();
    return actualizados;
  }

  function initClientes(ids, opts){
    opts = opts || {};
    var interval = opts.interval || 4000;
    ids = (ids || []).filter(Boolean);
    if (!ids.length) return;

    function tick(){
      fetchSaldos(ids).then(function(d){
        if (!d || !d.success) return;
        var porId = {};
        d.clientes.forEach(function(c){ porId[c.id] = c; });
        var rows = {};
        document.querySelectorAll('[data-cliente-id]').forEach(function(n){
          var id = parseInt(n.dataset.clienteId, 10);
          if (!id) return;
          if (!rows[id]) rows[id] = [];
          rows[id].push(n);
        });
        aplicar(rows, porId);
        // Actualizar KPI online
        var kpi = document.getElementById('kpiOnline');
        if (kpi) {
          var n = d.clientes.filter(function(c){ return c.online; }).length;
          kpi.textContent = n;
        }
      });
    }

    tick();
    setInterval(tick, interval);
  }

  function initSaldoUnico(clienteId, opts){
    opts = opts || {};
    var interval = opts.interval || 3000;
    if (!clienteId) return;

    function tick(){
      fetch('/roles/api/saldo-cliente/' + clienteId + '/', {credentials:'same-origin'})
        .then(function(r){ return r.ok ? r.json() : null; })
        .then(function(d){
          if (!d || !d.success) return;
          var s = document.getElementById('srSaldo') || document.querySelector('[data-saldo-cliente]');
          if (s) s.textContent = '$' + (d.saldo_total || 0).toFixed(2);
          var dot = document.getElementById('srDot') || document.querySelector('[data-online-cliente]');
          if (dot) dot.classList.toggle('online', !!d.online);
          var ts = document.getElementById('srTs') || document.getElementById('realtime-ts');
          if (ts) ts.textContent = 'Actualizado ' + new Date().toLocaleTimeString();
          var fps = document.getElementById('srFPs');
          if (fps && d.fondos_por_fp){
            var html = '';
            Object.keys(d.fondos_por_fp).forEach(function(k){
              html += '<span class="fp-chip-mini">' + k + ': $' +
                      (d.fondos_por_fp[k]||0).toFixed(2) + '</span>';
            });
            fps.innerHTML = html;
          }
        })
        .catch(function(){});
    }
    tick();
    setInterval(tick, interval);
  }

  return { initClientes: initClientes, initSaldoUnico: initSaldoUnico };
})();
