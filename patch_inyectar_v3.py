from pathlib import Path
import re

p = Path("/home/LottoBooM/jugadas/templates/jugadas/apostar.html")
src = p.read_text(encoding="utf-8")

idx_ini = src.find("function inyectarLineasBoleta(data) {")
idx_fin = src.find("if (editBoletaEl) {")

if idx_ini == -1 or idx_fin == -1:
    print("ERROR: no encontre las funciones")
    raise SystemExit(1)

nueva_funcion = '''function inyectarLineasBoleta(data) {
  console.log('[apostar] Inyectando líneas de la boleta...');
  console.log('[apostar] Total lineas a inyectar:', (data.lineas || []).length);

  var stats = { inyectadas: 0, falladas: 0, saltadas: 0 };
  var detallesFallos = [];

  var porSorteo = {};
  (data.lineas || []).forEach(function(l){
    if (!porSorteo[l.sorteo_id]) porSorteo[l.sorteo_id] = [];
    porSorteo[l.sorteo_id].push(l);
  });

  (data.sorteo_ids || []).forEach(function(sid){
    var s = sorteosActivos[sid] || sorteosActivos[String(sid)];
    if (!s || !s.cargado){
      console.warn('[apostar] Sorteo', sid, 'no cargado, salto sus lineas');
      return;
    }

    var lineas = porSorteo[sid] || [];

    // Limpiar filas existentes
    Object.keys(s.tablasActivas).forEach(function(tk){
      s.tablasActivas[tk].rows = [];
    });

    lineas.forEach(function(l){
      var tipoNorm = (l.tipo || '').toLowerCase().trim();
      var tk = FJ_TO_TABLE[tipoNorm];

      if (!tk){
        // Fallback: buscar match parcial
        var keys = Object.keys(FJ_TO_TABLE);
        for (var i = 0; i < keys.length; i++){
          if (tipoNorm.indexOf(keys[i]) !== -1 || keys[i].indexOf(tipoNorm) !== -1){
            tk = FJ_TO_TABLE[keys[i]];
            console.warn('[apostar] Match parcial:', tipoNorm, '→', keys[i], '→', tk);
            break;
          }
        }
      }

      if (!tk){
        console.warn('[apostar] NO MAPEO para tipo:', tipoNorm, '| linea:', l);
        stats.falladas++;
        detallesFallos.push(tipoNorm + ':' + l.numero);
        return;
      }

      var def = TABLE_DEFS[tk];
      var st = s.tablasActivas[tk];
      if (!st){
        console.log('[apostar] Creando tabla faltante:', tk, 'para sorteo', sid);
        st = { forms: def.forms.slice(), rows: [newRow(def.forms, def.kind)] };
        s.tablasActivas[tk] = st;
      }

      try {
        if (def.kind === 'single') {
          var montoKey = parseFloat(l.monto).toFixed(2);
          var row = st.rows.find(function(r){ return r._mk === montoKey; });
          if (!row) {
            row = newRow(st.forms, def.kind);
            row._mk = montoKey;
            st.rows.push(row);
          }
          row.num = row.num ? (row.num + ' ' + l.numero) : l.numero;
          st.forms.forEach(function(f){ row.montos[f] = montoKey; });
          stats.inyectadas++;

        } else if (def.kind === 'multi') {
          var fNorm = resolverForma(tipoNorm, def);
          if (!st.forms.includes(fNorm)){
            console.warn('[apostar] Forma', fNorm, 'no está en tabla', tk, 'forms:', st.forms);
            stats.falladas++;
            return;
          }
          var row2 = st.rows.find(function(r){ return r.num === l.numero; });
          if (!row2) {
            row2 = newRow(st.forms, def.kind);
            row2.num = l.numero;
            st.rows.push(row2);
          }
          row2.montos[fNorm] = parseFloat(l.monto).toFixed(2);
          stats.inyectadas++;

        } else if (def.kind === 'vs_groups') {
          var partes = String(l.numero).split('x');
          if (partes.length !== 2) {
            stats.falladas++;
            return;
          }
          var row3 = st.rows.find(function(r){ return r.numA === partes[0] && r.numB === partes[1]; });
          if (!row3) {
            row3 = newRow(st.forms, def.kind);
            row3.numA = partes[0];
            row3.numB = partes[1];
            row3.monto = parseFloat(l.monto).toFixed(2);
            st.rows.push(row3);
          }
          stats.inyectadas++;

        } else if (def.kind === 'posiciones') {
          // TODO: soportar posiciones
          stats.falladas++;
        } else {
          console.warn('[apostar] kind no soportado:', def.kind);
          stats.falladas++;
        }
      } catch(e){
        console.error('[apostar] Error inyectando linea:', l, e);
        stats.falladas++;
      }
    });

    // Asegurar al menos una fila por tabla
    Object.keys(s.tablasActivas).forEach(function(tk){
      if (s.tablasActivas[tk].rows.length === 0) {
        s.tablasActivas[tk].rows = [newRow(s.tablasActivas[tk].forms, TABLE_DEFS[tk].kind)];
      }
    });

    renderTabsSorteo(sid);
  });

  if (typeof recalcGlobal === 'function') recalcGlobal();
  console.log('[apostar] Boleta precargada:', stats, 'Fallos:', detallesFallos);

  // Feedback
  if (stats.inyectadas > 0 && typeof toast === 'function'){
    toast('✅ ' + stats.inyectadas + ' jugada(s) restaurada(s)', 'success');
  }
  if (stats.falladas > 0 && typeof toast === 'function'){
    toast('⚠️ ' + stats.falladas + ' jugada(s) no se pudieron restaurar: ' + detallesFallos.slice(0,3).join(', '), 'warning');
  }

  return stats;
}

'''

src_new = src[:idx_ini] + nueva_funcion + src[idx_fin:]
p.write_text(src_new, encoding="utf-8")
print("OK: inyectarLineasBoleta reescrita con debug")
