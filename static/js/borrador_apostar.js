/* ============================================================
   FIX_BORRADOR_PERSISTENTE_V2
   Persiste el borrador de apostar.html en localStorage.
   - SIN prompt "abandonar sitio"
   - Banner: "Tienes una jugada en edición sin enviar · [Continuar] [Borrar]"
   - Preserva filas tal cual (incluida la vacía del final = opción A)
   - Se borra SOLO al enviar con éxito o al pulsar "Borrar"
   ============================================================ */
(function(){
  'use strict';

  var CTX = window._BORRADOR_CTX || {};
  var USER_ID = CTX.userId || '0';
  var EDIT_MODE = !!CTX.editMode;
  var KEY = 'apostar_borrador_v1_user' + USER_ID;
  var DEBOUNCE_MS = 800;
  var _debTimer = null;
  var _aplicando = false;

  if (EDIT_MODE) return;

  function safeParse(s){ try { return JSON.parse(s); } catch(e){ return null; } }
  function readBorrador(){ try { return safeParse(localStorage.getItem(KEY)); } catch(e){ return null; } }
  function writeBorrador(o){ try { localStorage.setItem(KEY, JSON.stringify(o)); } catch(e){} }
  function clearBorrador(){ try { localStorage.removeItem(KEY); } catch(e){} }
  function getSA(){ return (typeof window.sorteosActivos !== 'undefined') ? window.sorteosActivos : null; }

  function snapshot(){
    var snap = { v:2, ts:Date.now(), clienteId:null, gestorId:null, fecha:null, fpId:null, fpNombre:null, sorteos:{}, orden:[] };
    var selCli = document.getElementById('selCliente');
    var selGes = document.getElementById('selGestorCuenta');
    var inpF   = document.getElementById('inpFecha');
    if (selCli) snap.clienteId = selCli.value || null;
    if (selGes) snap.gestorId  = selGes.value  || null;
    if (inpF)   snap.fecha     = inpF.value     || null;
    var chip = document.querySelector('.fp-chip.active');
    if (chip) {
      snap.fpId     = chip.dataset.id || chip.dataset.fpid || null;
      snap.fpNombre = chip.textContent.trim();
    }
    var sa = getSA();
    if (sa) {
      Object.keys(sa).forEach(function(sid){
        var s = sa[sid]; if (!s) return;
        snap.orden.push(sid);
        snap.sorteos[sid] = {
          nombre: s.nombre || '',
          cerrado: !!s.cerrado,
          tabActual: s.tabActual || null,
          tablasActivas: safeParse(JSON.stringify(s.tablasActivas || {}))
        };
      });
    }
    return snap;
  }

  function hasNumbers(s){
    var sorteos=s&&s.sorteos||{},found=false;
    Object.keys(sorteos).forEach(function(sid){
      var tabs=sorteos[sid]&&sorteos[sid].tablasActivas||{};
      Object.keys(tabs).forEach(function(tk){
        (tabs[tk].rows||[]).forEach(function(row){
          if(String(row.num||'').trim()||String(row.numA||'').trim()||String(row.numB||'').trim())found=true;
        });
      });
    });
    return found;
  }
  function isEligible(s){
    if(!s||!s.clienteId||!(s.fpId||s.fpNombre)||!s.orden||!s.orden.length)return false;
    if(s.gestorId===null && document.getElementById('selGestorCuenta'))return false;
    return hasNumbers(s);
  }
  function isEmpty(s){ return !isEligible(s); }

  function scheduleSave(){
    if (_aplicando) return;
    clearTimeout(_debTimer);
    _debTimer = setTimeout(function(){
      var s = snapshot();
      if (isEmpty(s)) clearBorrador(); else writeBorrador(s);
    }, DEBOUNCE_MS);
  }

  function wait(cond, timeoutMs, done){
    var start = Date.now();
    var iv = setInterval(function(){
      if (cond() || Date.now() - start > timeoutMs) { clearInterval(iv); done(); }
    }, 200);
  }

  function selectFP(snap){
    if (!snap.fpId && !snap.fpNombre) return;
    var chips = document.querySelectorAll('.fp-chip');
    for (var i=0; i<chips.length; i++){
      var c = chips[i];
      var cid = c.dataset.id || c.dataset.fpid || null;
      if (snap.fpId && cid === snap.fpId) { c.click(); return; }
    }
    if (snap.fpNombre) {
      for (var j=0; j<chips.length; j++){
        if (chips[j].textContent.trim().indexOf(snap.fpNombre) !== -1) { chips[j].click(); return; }
      }
    }
  }

  function reabrir(snap){
    var sids = Object.keys(snap.sorteos||{});
    if (!sids.length) { _aplicando = false; return; }
    sids.forEach(function(sid){
      var btn = document.querySelector('.sorteo-btn[data-id="'+sid+'"]');
      if (!btn) return;
      if (!btn.classList.contains('active')) { try { btn.click(); } catch(e){} }
    });
    setTimeout(function(){
      sids.forEach(function(sid){
        var sa = getSA(); if (!sa || !sa[sid]) return;
        var g = snap.sorteos[sid];
        if (g.tablasActivas) sa[sid].tablasActivas = safeParse(JSON.stringify(g.tablasActivas));
        if (g.tabActual)     sa[sid].tabActual     = g.tabActual;
        try {
          if (typeof window.renderTabsSorteo === 'function') window.renderTabsSorteo(sid);
        } catch(e){}
      });
      _aplicando = false;
    }, 900);
  }

  function applySnapshot(snap){
    if (!snap || (snap.v !== 1 && snap.v !== 2)) return;
    _aplicando = true;
    var sg = document.getElementById('selGestorCuenta');
    if (sg && snap.gestorId) {
      if ([].some.call(sg.options, function(o){ return o.value === snap.gestorId; })) sg.value = snap.gestorId;
    }
    var sc = document.getElementById('selCliente');
    if (sc && snap.clienteId) {
      wait(function(){ return [].some.call(sc.options, function(o){ return o.value === snap.clienteId; }); }, 3000, function(){
        sc.value = snap.clienteId;
        sc.dispatchEvent(new Event('change', {bubbles:true}));
        setTimeout(function(){ selectFP(snap); }, 1500);
        setTimeout(function(){ reabrir(snap); }, 2500);
      });
    } else {
      selectFP(snap);
      reabrir(snap);
    }
    var inpF = document.getElementById('inpFecha');
    if (inpF && snap.fecha) inpF.value = snap.fecha;
  }

  function showBanner(snap){
    if (!isEligible(snap) || document.getElementById('borradorBanner')) return;
    var el = document.createElement('div');
    el.id = 'borradorBanner';
    el.style.cssText = 'position:fixed;top:10px;right:10px;z-index:9999;max-width:340px;background:linear-gradient(145deg,#fef3c7,#fde68a);color:#78350f;padding:14px 16px;border-radius:10px;border:2px solid #f59e0b;box-shadow:0 4px 14px rgba(0,0,0,.25);font-family:inherit;font-size:.85rem;';
    el.innerHTML = '📝 <strong>Tienes una apuesta sin guardar</strong><br>'
      + '<span style="font-size:.78rem;display:block;margin-top:6px;">¿Deseas continuar o borrar el borrador?</span>'
      + '<div style="margin-top:10px;display:flex;gap:8px;">'
      + '<button type="button" id="borrCont" style="flex:1;padding:8px 10px;background:#2563eb;color:#fff;border:none;border-radius:6px;font-weight:800;cursor:pointer;font-size:.8rem;">Continuar</button>'
      + '<button type="button" id="borrBorr" style="flex:1;padding:8px 10px;background:#dc2626;color:#fff;border:none;border-radius:6px;font-weight:800;cursor:pointer;font-size:.8rem;">Borrar</button>'
      + '</div>';
    document.body.appendChild(el);
    document.getElementById('borrCont').onclick = function(){ el.remove(); applySnapshot(snap); };
    document.getElementById('borrBorr').onclick = function(){
      clearBorrador();
      el.remove();
      try { if (typeof window.resetAll === 'function') window.resetAll(); } catch(e){}
      setTimeout(function(){ location.reload(); }, 200);
    };
  }

  function attachHooks(){
    ['selCliente','selGestorCuenta','inpFecha'].forEach(function(id){
      var e = document.getElementById(id);
      if (e) { e.addEventListener('change', scheduleSave); e.addEventListener('input', scheduleSave); }
    });
    document.addEventListener('click', function(ev){
      var t = ev.target;
      while (t && t !== document.body){
        if (t.classList && (t.classList.contains('fp-chip') || t.classList.contains('sorteo-btn'))) {
          setTimeout(scheduleSave, 250); return;
        }
        t = t.parentElement;
      }
    }, true);
    ['input','change'].forEach(function(evt){
      document.addEventListener(evt, function(ev){
        var t = ev.target;
        if (t && t.closest && t.closest('.sp-panel')) scheduleSave();
      }, true);
    });
    // SIN beforeunload — el cliente puede salir libremente
  }

  function hookSubmit(){
    if (typeof window.enviarApuesta !== 'function' || window._borradorSubmitHooked) return;
    window._borradorSubmitHooked = true;
    var original = window.enviarApuesta;
    window.enviarApuesta = function(dryRun){
      var result = original.apply(this, arguments);
      if (!dryRun) {
        var started = Date.now();
        var timer = setInterval(function(){
          if (window.location.pathname.indexOf('mis-apuestas') !== -1) { clearBorrador(); clearInterval(timer); }
          if (Date.now()-started > 30000) clearInterval(timer);
        }, 500);
      }
      return result;
    };
  }
  window._borradorDraftApi = {snapshot:snapshot,isEligible:isEligible,hasNumbers:hasNumbers,clear:clearBorrador,read:readBorrador,apply:applySnapshot};

  function init(){
    attachHooks();
    hookSubmit();
    // El borrador se limpia directamente en apostar.html al confirmar éxito
    var snap = readBorrador();
    if (snap && !isEmpty(snap)) {
      // FIX_BORRADOR_EDAD_V1: no mostrar si tiene más de 12h (huérfano)
      var horas = (Date.now() - (snap.ts || 0)) / (1000*60*60);
      if (horas > 12) {
        clearBorrador();
        return;
      }
      setTimeout(function(){ showBanner(snap); }, 1500);
    }
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
