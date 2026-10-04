from pathlib import Path
import re

p = Path("/home/LottoBooM/jugadas/templates/jugadas/apostar.html")
src = p.read_text(encoding="utf-8")

# Localizar la función completa
idx_ini = src.find("function preloadBoletaEdit(data) {")
idx_fin = src.find("function inyectarLineasBoleta(data) {")

if idx_ini == -1 or idx_fin == -1:
    print("ERROR: no encontre las funciones")
    raise SystemExit(1)

nueva_funcion = '''function preloadBoletaEdit(data) {
  console.log('=== [apostar] INICIO PRECARGA ===');
  console.log('[apostar] Data:', JSON.stringify(data, null, 2));

  var _estadoDebug = {
    clienteOk: false,
    fpOk: false,
    sorteosOk: false,
    jugadasInyectadas: 0,
    jugadasFalladas: 0,
  };

  // ─── 1. Seleccionar cliente ───
  var selCli = document.getElementById('selCliente');
  if (!selCli){
    console.error('[apostar] No existe #selCliente');
    return;
  }
  selCli.value = String(data.cliente_id);
  selCli.dispatchEvent(new Event('change'));
  console.log('[apostar] Cliente seleccionado:', selCli.value);
  _estadoDebug.clienteOk = true;

  // ─── 2. Esperar chips de FP ───
  waitFor(function(){ return document.querySelector('.fp-chip'); }, 8000)
    .catch(function(e){
      console.warn('[apostar] Timeout esperando chips FP:', e.message);
    })
    .then(function(){
      var chips = document.querySelectorAll('.fp-chip');
      var encontrado = false;
      chips.forEach(function(ch){
        if (String(ch.dataset.id) === String(data.forma_pago_id)){
          ch.click();
          encontrado = true;
          _estadoDebug.fpOk = true;
          console.log('[apostar] Chip FP clickeado:', ch.dataset.n);
        }
      });
      if (!encontrado){
        console.warn('[apostar] No encontre chip FP id=' + data.forma_pago_id);
        console.log('[apostar] Chips disponibles:', Array.from(chips).map(c => c.dataset.id + '=' + c.dataset.n));
      }
    })
    // ─── 3. Esperar botones de sorteo ───
    .then(function(){
      return waitFor(function(){ return document.querySelector('.sorteo-btn'); }, 10000);
    })
    .catch(function(e){
      console.error('[apostar] Timeout esperando .sorteo-btn:', e.message);
      try {
        // Forzar carga
        cargarSorteos();
      } catch(_){}
      return waitFor(function(){ return document.querySelector('.sorteo-btn'); }, 5000);
    })
    .then(function(){
      var inpFecha = document.getElementById('inpFecha');
      if (inpFecha && data.fecha_sorteo) inpFecha.value = data.fecha_sorteo;

      // ─── 4. Activar sorteos ───
      var activados = 0;
      var noEncontrados = [];
      (data.sorteo_ids || []).forEach(function(sid){
        var btn = document.querySelector('.sorteo-btn[data-id="' + sid + '"]');
        if (btn){
          if (!btn.classList.contains('active')){
            btn.click();
            console.log('[apostar] Sorteo clickeado:', sid);
          } else {
            console.log('[apostar] Sorteo ya estaba activo:', sid);
          }
          activados++;
        } else {
          noEncontrados.push(sid);
          console.warn('[apostar] No existe boton para sorteo', sid, '(probablemente cerrado)');
        }
      });
      console.log('[apostar] Sorteos activados:', activados, 'de', (data.sorteo_ids || []).length);
      if (noEncontrados.length){
        console.warn('[apostar] Sorteos no encontrados:', noEncontrados);
        if (typeof toast === 'function'){
          toast('⚠️ ' + noEncontrados.length + ' sorteo(s) ya cerrado(s) no se pudieron restaurar', 'warning');
        }
      }
    })
    // ─── 5. Esperar a que carguen configs ───
    .then(function(){
      return waitFor(function(){
        if (typeof sorteosActivos === 'undefined') return false;
        var ids = data.sorteo_ids || [];
        if (!ids.length) return true;
        return ids.every(function(sid){
          var s = sorteosActivos[String(sid)] || sorteosActivos[sid];
          if (!s) return true; // ya no está activo, no bloquear
          return s.cargado;
        });
      }, 25000);
    })
    .catch(function(e){
      console.warn('[apostar] Timeout esperando configs. Estado:',
        Object.keys(sorteosActivos || {}).map(function(k){
          return k + '=' + (sorteosActivos[k].cargado ? 'OK' : 'pending');
        }).join(', ')
      );
    })
    // ─── 6. Inyectar jugadas ───
    .then(function(){
      console.log('[apostar] Inyectando lineas...');
      try {
        var resultado = inyectarLineasBoleta(data);
        _estadoDebug.jugadasInyectadas = resultado ? resultado.inyectadas : 0;
        _estadoDebug.jugadasFalladas = resultado ? resultado.falladas : 0;
      } catch(e){
        console.error('[apostar] Error inyectando lineas:', e);
      }
      console.log('=== [apostar] FIN PRECARGA ===', _estadoDebug);

      // Feedback visual
      if (typeof toast === 'function'){
        if (_estadoDebug.jugadasInyectadas > 0){
          toast('🔄 ' + _estadoDebug.jugadasInyectadas + ' jugada(s) restaurada(s)', 'success');
        }
        if (_estadoDebug.jugadasFalladas > 0){
          toast('⚠️ ' + _estadoDebug.jugadasFalladas + ' jugada(s) no se pudieron restaurar', 'warning');
        }
      }
    });
}

'''

src_new = src[:idx_ini] + nueva_funcion + src[idx_fin:]
p.write_text(src_new, encoding="utf-8")
print("OK: preloadBoletaEdit reescrita")

import ast
print("OK: patch generado")

