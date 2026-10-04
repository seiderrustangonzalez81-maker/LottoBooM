from pathlib import Path

p = Path("/home/LottoBooM/jugadas/templates/jugadas/apostar.html")
src = p.read_text(encoding="utf-8")

if "EXCEPCIONES_POR_FILA_V1" in src:
    print("SKIP: ya aplicado")
    raise SystemExit(0)

# ═══ 5a) Normalizar acentos en _getPoolYConsumido ═══
viejo_5a = """  var nombreLower = String(formaNombre || '').toLowerCase().trim();
  // Buscar por nombre (case-insensitive) en las formas cacheadas
  for (var fjId in data) {
    var info = data[fjId];
    var infoNombre = String(info.forma_nombre || '').toLowerCase().trim();"""

nuevo_5a = r"""  var nombreLower = String(formaNombre || '').toLowerCase().trim()
    .normalize('NFD').replace(/[\u0300-\u036f]/g, '');
  // Buscar por nombre (case+accent-insensitive) en las formas cacheadas
  for (var fjId in data) {
    var info = data[fjId];
    var infoNombre = String(info.forma_nombre || '').toLowerCase().trim()
      .normalize('NFD').replace(/[\u0300-\u036f]/g, '');"""

if viejo_5a not in src:
    print("ERROR: no encontré el bloque 5a en _getPoolYConsumido")
    raise SystemExit(1)
src = src.replace(viejo_5a, nuevo_5a, 1)
print("OK: 5a — acentos normalizados en _getPoolYConsumido")


# ═══ 5b) Inyectar evaluador + listener delegado ═══
viejo_5b = """  const addBtn = cont.querySelector('[data-add]');
  if (addBtn) addBtn.addEventListener('click', ()=>{
    st.rows.push(newRow(st.forms, def.kind));
    renderTabsSorteo(sid);
    renderMiniResumenSorteo(sid);
  });
}
"""

nuevo_5b = r"""  const addBtn = cont.querySelector('[data-add]');
  if (addBtn) addBtn.addEventListener('click', ()=>{
    st.rows.push(newRow(st.forms, def.kind));
    renderTabsSorteo(sid);
    renderMiniResumenSorteo(sid);
  });

  // ═══ EXCEPCIONES_POR_FILA_V1: listener delegado ═══
  if (!cont._excBound){
    cont._excBound = true;
    cont.addEventListener('input', function(ev){
      var t = ev.target;
      if (!t || !t.matches) return;
      if (!t.matches('.num-inp, .pos-num, .vs-numA, .vs-numB, .monto')) return;
      clearTimeout(cont._excT);
      cont._excT = setTimeout(function(){
        try { evaluarExcepcionesSorteo(sid, cont); }
        catch(e){ console.warn('[EXC]', e); }
      }, 100);
    });
  }
  // Evaluación inicial (tras el render)
  setTimeout(function(){
    try { evaluarExcepcionesSorteo(sid, cont); }
    catch(e){ console.warn('[EXC]', e); }
  }, 50);
  // ═══ FIN EXCEPCIONES_POR_FILA_V1 ═══
}

/* ═══════════════════════════════════════════════════════════════
   EXCEPCIONES_POR_FILA_V1
   Marca <tr class="fila-excede"> cuando el monto de alguna jugada
   supera el disponible (pool - consumido) del número según
   _getPoolYConsumido(sid, formaKey, numero).
   ═══════════════════════════════════════════════════════════════ */
function evaluarExcepcionesSorteo(sid, cont){
  if (!cont) return;
  var s = sorteosActivos[sid];
  if (!s) return;
  var tk  = s.tabActual;
  var st  = s.tablasActivas && s.tablasActivas[tk];
  var def = (typeof TABLE_DEFS !== 'undefined') ? TABLE_DEFS[tk] : null;
  if (!st || !def) return;

  // Disparar carga del pool una sola vez por sorteo
  if (typeof _cargarPoolPorNumero === 'function' && !s._poolTriggered){
    s._poolTriggered = true;
    try { _cargarPoolPorNumero(sid); } catch(_){}
  }

  // v1: vs_groups queda fuera (combinatoria A×B)
  if (def.kind === 'vs_groups') return;

  cont.querySelectorAll('tr[data-row]').forEach(function(tr){
    var i = parseInt(tr.dataset.row);
    var row = st.rows[i];
    if (!row) return;

    var piezas = [];   // {num, formaKey, monto}

    if (def.kind === 'posiciones'){
      for (var p = 0; p < 3; p++){
        var n = String((row.posNums && row.posNums[p]) || '').trim();
        var m = parseFloat(row.posMontos && row.posMontos[p]) || 0;
        if (n && m > 0) piezas.push({ num: n, formaKey: 'posicion', monto: m });
      }
    } else {
      var rawNum = String(row.num || '').trim();
      if (!rawNum){
        _limpiarFilaExcede(tr);
        return;
      }
      var partes = rawNum.split(/[\s,]+/).filter(Boolean);
      var forms  = st.forms || [];
      forms.forEach(function(f){
        var m = parseFloat(row.montos && row.montos[f]) || 0;
        if (m <= 0) return;
        partes.forEach(function(pp){
          piezas.push({ num: pp, formaKey: f, monto: m });
        });
      });
    }

    var motivos = [];
    piezas.forEach(function(it){
      var info = _getPoolYConsumido(sid, it.formaKey, it.num);
      if (!info || info.pool <= 0) return;   // sin pool → no validamos
      if (it.monto > info.disponible + 0.001){
        var falta = (it.monto - info.disponible).toFixed(2);
        motivos.push(it.formaKey + ' ' + it.num + ' → falta $' + falta);
      }
    });

    if (motivos.length){
      tr.classList.add('fila-excede');
      tr.setAttribute('data-excede', '1');
      tr.setAttribute('data-motivo', motivos.join(' · '));
      tr.setAttribute('title', motivos.join('\n'));
    } else {
      _limpiarFilaExcede(tr);
    }
  });
}

function _limpiarFilaExcede(tr){
  tr.classList.remove('fila-excede');
  tr.removeAttribute('data-excede');
  tr.removeAttribute('data-motivo');
  tr.removeAttribute('title');
}
"""

if viejo_5b not in src:
    print("ERROR: no encontré el anclaje 5b (addBtn + cierre)")
    raise SystemExit(1)
src = src.replace(viejo_5b, nuevo_5b, 1)
print("OK: 5b — evaluador + listener delegado")


# ═══ 5c) CSS ═══
if "tr.fila-excede" not in src:
    css = """
  /* EXCEPCIONES_POR_FILA_V1 */
  tr.fila-excede{
    background: #fef2f2 !important;
    box-shadow: inset 3px 0 0 #dc2626;
  }
  tr.fila-excede input,
  tr.fila-excede textarea{
    border-color: #dc2626 !important;
    box-shadow: 0 0 0 1px rgba(220,38,38,.25) !important;
  }
  tr.fila-excede td.total-col .total{
    color: #dc2626;
    font-weight: 700;
  }
"""
    idx = src.find("</style>")
    if idx == -1:
        print("WARN: no encontré </style>, CSS no insertado")
    else:
        src = src[:idx] + css + src[idx:]
        print("OK: 5c — CSS insertado")
else:
    print("SKIP: CSS ya existe")

p.write_text(src, encoding="utf-8")

# Validación JS mínima
if src.count("EXCEPCIONES_POR_FILA_V1") < 3:
    print("WARN: marca EXCEPCIONES_POR_FILA_V1 aparece menos de 3 veces")
if src.count("evaluarExcepcionesSorteo") < 3:
    print("WARN: evaluarExcepcionesSorteo aparece menos de 3 veces")

print("✅ Patch 5 aplicado")
