from pathlib import Path

p = Path("/home/LottoBooM/jugadas/templates/jugadas/apostar.html")
src = p.read_text(encoding="utf-8")

idx_ini = src.find("function inyectarLineasBoleta(data) {")
idx_fin = src.find("if (editBoletaEl) {")

if idx_ini == -1 or idx_fin == -1:
    print("ERROR: no encontre las funciones")
    raise SystemExit(1)

nueva = '''function inyectarLineasBoleta(data) {
  console.log('[apostar] Inyectando líneas de la boleta (con agrupación)...');
  console.log('[apostar] Total lineas a inyectar:', (data.lineas || []).length);

  var stats = { inyectadas: 0, falladas: 0, filas: 0 };
  var detallesFallos = [];

  var porSorteo = {};
  (data.lineas || []).forEach(function(l){
    if (!porSorteo[l.sorteo_id]) porSorteo[l.sorteo_id] = [];
    porSorteo[l.sorteo_id].push(l);
  });

  (data.sorteo_ids || []).forEach(function(sid){
    var s = sorteosActivos[sid] || sorteosActivos[String(sid)];
    if (!s || !s.cargado){
      console.warn('[apostar] Sorteo', sid, 'no cargado');
      return;
    }

    var lineas = porSorteo[sid] || [];

    // Limpiar filas existentes
    Object.keys(s.tablasActivas).forEach(function(tk){
      s.tablasActivas[tk].rows = [];
    });

    // Agrupar lineas por tabla
    var lineasPorTabla = {};
    lineas.forEach(function(l){
      var tipoNorm = (l.tipo || '').toLowerCase().trim();
      var tk = FJ_TO_TABLE[tipoNorm];
      if (!tk){
        var keys = Object.keys(FJ_TO_TABLE);
        for (var i = 0; i < keys.length; i++){
          if (tipoNorm.indexOf(keys[i]) !== -1 || keys[i].indexOf(tipoNorm) !== -1){
            tk = FJ_TO_TABLE[keys[i]];
            break;
          }
        }
      }
      if (!tk){
        stats.falladas++;
        detallesFallos.push(tipoNorm + ':' + l.numero);
        return;
      }
      if (!lineasPorTabla[tk]) lineasPorTabla[tk] = [];
      lineasPorTabla[tk].push({ l: l, tipoNorm: tipoNorm });
    });

    // Procesar cada tabla
    Object.keys(lineasPorTabla).forEach(function(tk){
      var def = TABLE_DEFS[tk];
      var st = s.tablasActivas[tk];
      if (!st){
        st = { forms: def.forms.slice(), rows: [] };
        s.tablasActivas[tk] = st;
      }

      var items = lineasPorTabla[tk];

      // ═══════════════════════════════════════════════════════════
      // SINGLE (pick3, pick4, pick5, tripleta, vs100)
      // Agrupar por monto
      // ═══════════════════════════════════════════════════════════
      if (def.kind === 'single'){
        var porMonto = {};
        items.forEach(function(it){
          var m = parseFloat(it.l.monto).toFixed(2);
          if (!porMonto[m]) porMonto[m] = [];
          porMonto[m].push(it.l.numero);
        });
        Object.keys(porMonto).forEach(function(m){
          var row = newRow(st.forms, def.kind);
          row.num = porMonto[m].join(' ');
          row._mk = m;
          st.forms.forEach(function(f){ row.montos[f] = m; });
          st.rows.push(row);
          stats.inyectadas += porMonto[m].length;
          stats.filas++;
        });

      // ═══════════════════════════════════════════════════════════
      // MULTI (pick2, pf, fijo, corridos, parlet, candado)
      // Agrupar por firma de montos (por número)
      // ═══════════════════════════════════════════════════════════
      } else if (def.kind === 'multi'){
        // Mapa: numero → { forma: monto }
        var porNumero = {};
        items.forEach(function(it){
          var fNorm = resolverForma(it.tipoNorm, def);
          if (!st.forms.includes(fNorm)){
            stats.falladas++;
            detallesFallos.push(fNorm + ':' + it.l.numero);
            return;
          }
          var monto = parseFloat(it.l.monto).toFixed(2);
          if (!porNumero[it.l.numero]) porNumero[it.l.numero] = {};
          porNumero[it.l.numero][fNorm] = monto;
        });

        // Agrupar números por firma (montos idénticos en todas sus formas)
        var grupos = {};
        Object.keys(porNumero).forEach(function(num){
          var montos = porNumero[num];
          var firma = Object.keys(montos).sort().map(function(f){
            return f + '=' + montos[f];
          }).join('|');
          if (!grupos[firma]) grupos[firma] = { numeros: [], montos: montos };
          grupos[firma].numeros.push(num);
        });

        Object.keys(grupos).forEach(function(firma){
          var g = grupos[firma];
          var row = newRow(st.forms, def.kind);
          row.num = g.numeros.join(' ');
          st.forms.forEach(function(f){
            row.montos[f] = g.montos[f] || '';
          });
          st.rows.push(row);
          stats.inyectadas += g.numeros.length;
          stats.filas++;
        });

      // ═══════════════════════════════════════════════════════════
      // VS_GROUPS (vs, vspf, vspick2, pick2vspf)
      // Agrupar por (numA + monto) → múltiples numB
      // ═══════════════════════════════════════════════════════════
      } else if (def.kind === 'vs_groups'){
        var gruposVS = {};
        items.forEach(function(it){
          var partes = String(it.l.numero).split('x');
          if (partes.length !== 2){
            stats.falladas++;
            return;
          }
          var a = partes[0].trim();
          var b = partes[1].trim();
          var monto = parseFloat(it.l.monto).toFixed(2);
          var firma = a + '=' + monto;
          if (!gruposVS[firma]){
            gruposVS[firma] = { numA: a, monto: monto, numBs: [] };
          }
          gruposVS[firma].numBs.push(b);
        });

        Object.keys(gruposVS).forEach(function(firma){
          var g = gruposVS[firma];
          var row = newRow(st.forms, def.kind);
          row.numA = g.numA;
          row.numB = g.numBs.join(' ');
          row.monto = g.monto;
          st.rows.push(row);
          stats.inyectadas += g.numBs.length;
          stats.filas++;
        });

      } else if (def.kind === 'posiciones'){
        // TODO: agrupar por posición
        items.forEach(function(it){
          var partes = String(it.l.numero || '').split('@');
          stats.falladas++;
        });
      } else {
        console.warn('[apostar] kind no soportado:', def.kind);
        stats.falladas += items.length;
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

  if (stats.inyectadas > 0 && typeof toast === 'function'){
    toast('✅ ' + stats.filas + ' fila(s) · ' + stats.inyectadas + ' jugada(s) restauradas', 'success');
  }
  if (stats.falladas > 0 && typeof toast === 'function'){
    toast('⚠️ ' + stats.falladas + ' jugada(s) no se pudieron restaurar', 'warning');
  }

  return stats;
}

'''

src_new = src[:idx_ini] + nueva + src[idx_fin:]
p.write_text(src_new, encoding="utf-8")
print("OK: inyectarLineasBoleta reescrita con agrupación")

# Verificar
assert "var grupos = {}" in src_new
assert "var gruposVS = {}" in src_new
assert "var porMonto = {}" in src_new
print("OK: agrupación single + multi + vs_groups presente")
