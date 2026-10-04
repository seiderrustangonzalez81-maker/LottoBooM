from pathlib import Path

p = Path("/home/LottoBooM/jugadas/templates/jugadas/apostar.html")
src = p.read_text(encoding="utf-8")

if "POSICIONES_SINGLE_COLUMN_V1" in src:
    print("SKIP: ya aplicado")
    raise SystemExit(0)

# ══════════════════════════════════════════════════════════════
# 1. newRow para posiciones
# ══════════════════════════════════════════════════════════════
viejo = """  if (kind === 'posiciones'){
    return { posNums: ['', '', ''], posMontos: ['', '', ''] };
  }"""
nuevo = """  // POSICIONES_SINGLE_COLUMN_V1
  if (kind === 'posiciones'){
    return { posicion: '1', num: '', monto: '' };
  }"""
if viejo not in src:
    print("ERROR 1: newRow"); raise SystemExit(1)
src = src.replace(viejo, nuevo, 1)

# ══════════════════════════════════════════════════════════════
# 2. renderTablaActivaSorteo — HTML de la tabla de posiciones
# ══════════════════════════════════════════════════════════════
viejo = """  if (def.kind === 'posiciones'){
    html = '<div class="tabla-panel"><div class="table-wrap"><table class="tabla-ap pos-col"><thead><tr>';
    html += '<th class="num-col">Pos 1</th><th class="monto-col">$1</th>';
    html += '<th class="num-col">Pos 2</th><th class="monto-col">$2</th>';
    html += '<th class="num-col">Pos 3</th><th class="monto-col">$3</th>';
    html += '<th class="total-col">Total</th><th class="del-col"></th>';
    html += '</tr></thead><tbody>';
    st.rows.forEach((row, i)=>{
      html += `<tr data-row="${i}">`;
      for (let p = 0; p < 3; p++){
        html += `<td class="num-col"><textarea rows="1" class="pos-num" data-row="${i}" data-pos="${p}" placeholder="00" maxlength="2" autocomplete="off">${esc(row.posNums[p]||'')}</textarea></td>`;
        html += `<td class="monto-col"><input type="number" step="0.01" min="0" class="monto pos-monto" value="${esc(row.posMontos[p]||'')}" data-row="${i}" data-pos="${p}" placeholder="0" autocomplete="off"></td>`;
      }
      const tot = calcRowTotal(row, st.forms, def.numDigits, def.kind, def.maxNums);
      html += `<td class="total-col"><span class="total" data-tot="${i}">${fmtMoney(tot)}</span></td>`;
      html += `<td class="del-col"><button type="button" class="del" data-del="${i}" title="Eliminar"><i class="fas fa-times"></i></button></td>`;
      html += '</tr>';
    });
    html += '</tbody></table></div>';
    html += `<button type="button" class="add-row" data-add="1"><i class="fas fa-plus"></i> Añadir fila</button>`;
    html += '</div>';
  } else if (def.kind === 'vs_groups'){"""

nuevo = """  // POSICIONES_SINGLE_COLUMN_V1
  if (def.kind === 'posiciones'){
    html = '<div class="tabla-panel"><div class="table-wrap"><table class="tabla-ap pos-col"><thead><tr>';
    html += '<th class="possel-col">Pos</th>';
    html += '<th class="num-col">Números</th>';
    html += '<th class="monto-col">Monto</th>';
    html += '<th class="total-col">Total</th>';
    html += '<th class="del-col"></th>';
    html += '</tr></thead><tbody>';
    st.rows.forEach((row, i)=>{
      const pos = String(row.posicion || '1');
      html += `<tr data-row="${i}">`;
      html += `<td class="possel-col"><select class="pos-sel" data-row="${i}">`
            + `<option value="1"${pos==='1'?' selected':''}>1</option>`
            + `<option value="2"${pos==='2'?' selected':''}>2</option>`
            + `<option value="3"${pos==='3'?' selected':''}>3</option>`
            + `</select></td>`;
      html += `<td class="num-col"><textarea rows="1" class="pos-num" data-row="${i}" placeholder="12 34 56" autocomplete="off">${esc(row.num||'')}</textarea></td>`;
      html += `<td class="monto-col"><input type="number" step="0.01" min="0" class="monto pos-monto" value="${esc(row.monto||'')}" data-row="${i}" placeholder="0" autocomplete="off"></td>`;
      const tot = calcRowTotal(row, st.forms, def.numDigits, def.kind, def.maxNums);
      html += `<td class="total-col"><span class="total" data-tot="${i}">${fmtMoney(tot)}</span></td>`;
      html += `<td class="del-col"><button type="button" class="del" data-del="${i}" title="Eliminar"><i class="fas fa-times"></i></button></td>`;
      html += '</tr>';
    });
    html += '</tbody></table></div>';
    html += `<button type="button" class="add-row" data-add="1"><i class="fas fa-plus"></i> Añadir fila</button>`;
    html += '</div>';
  } else if (def.kind === 'vs_groups'){"""
if viejo not in src:
    print("ERROR 2: renderTablaActivaSorteo"); raise SystemExit(1)
src = src.replace(viejo, nuevo, 1)

# ══════════════════════════════════════════════════════════════
# 3. Handlers .pos-num y .pos-monto (bindTablaEventsSorteo)
# ══════════════════════════════════════════════════════════════
viejo = r"""  cont.querySelectorAll('.pos-num').forEach(inp=>{
    inp.addEventListener('input', function(){
      const i = parseInt(this.dataset.row);
      const p = parseInt(this.dataset.pos);
      const v = this.value.replace(/\D/g,'').slice(0, 2);
      this.value = v;
      st.rows[i].posNums[p] = v;
      autoResizeTextarea(this);
      const cell = cont.querySelector(`[data-tot="${i}"]`);
      if (cell) cell.textContent = fmtMoney(calcRowTotal(st.rows[i], st.forms, def.numDigits, def.kind, def.maxNums));
      recalcGlobal();
      renderMiniResumenSorteo(sid);
    });
  });

  cont.querySelectorAll('.pos-monto').forEach(inp=>{
    inp.addEventListener('input', function(){
      const i = parseInt(this.dataset.row);
      const p = parseInt(this.dataset.pos);
      st.rows[i].posMontos[p] = this.value;
      const cell = cont.querySelector(`[data-tot="${i}"]`);
      if (cell) cell.textContent = fmtMoney(calcRowTotal(st.rows[i], st.forms, def.numDigits, def.kind, def.maxNums));
      recalcGlobal();
      renderMiniResumenSorteo(sid);
    });
  });"""

nuevo = r"""  // POSICIONES_SINGLE_COLUMN_V1
  cont.querySelectorAll('.pos-sel').forEach(sel=>{
    sel.addEventListener('change', function(){
      const i = parseInt(this.dataset.row);
      st.rows[i].posicion = this.value;
    });
  });

  cont.querySelectorAll('.pos-num').forEach(inp=>{
    inp.addEventListener('input', function(){
      const i = parseInt(this.dataset.row);
      const formatted = autoformatearPosiciones(this.value);
      this.value = formatted;
      st.rows[i].num = formatted;
      autoResizeTextarea(this);
      const cell = cont.querySelector(`[data-tot="${i}"]`);
      if (cell) cell.textContent = fmtMoney(calcRowTotal(st.rows[i], st.forms, def.numDigits, def.kind, def.maxNums));
      recalcGlobal();
      renderMiniResumenSorteo(sid);
    });
  });

  cont.querySelectorAll('.pos-monto').forEach(inp=>{
    inp.addEventListener('input', function(){
      const i = parseInt(this.dataset.row);
      st.rows[i].monto = this.value;
      const cell = cont.querySelector(`[data-tot="${i}"]`);
      if (cell) cell.textContent = fmtMoney(calcRowTotal(st.rows[i], st.forms, def.numDigits, def.kind, def.maxNums));
      recalcGlobal();
      renderMiniResumenSorteo(sid);
    });
  });"""
if viejo not in src:
    print("ERROR 3: handlers pos-num"); raise SystemExit(1)
src = src.replace(viejo, nuevo, 1)

# ══════════════════════════════════════════════════════════════
# 4. autoformatearPosiciones (nueva función)
# ══════════════════════════════════════════════════════════════
viejo = "function autoformatearSoloParlet(texto){"
nuevo = r"""// POSICIONES_SINGLE_COLUMN_V1: agrupa dígitos de a 2, separados por espacio
function autoformatearPosiciones(texto){
  var s = String(texto || '').replace(/[^0-9\s]/g, '');
  var tieneEspacioFinal = /\s$/.test(s);
  var digitos = s.replace(/\s+/g, '');
  var out = [];
  for (var i = 0; i < digitos.length; i += 2){
    out.push(digitos.slice(i, i + 2));
  }
  var result = out.join(' ');
  if (out.length && tieneEspacioFinal) result += ' ';
  return result;
}

function autoformatearSoloParlet(texto){"""
if viejo not in src:
    print("ERROR 4: autoformatearSoloParlet"); raise SystemExit(1)
src = src.replace(viejo, nuevo, 1)

# ══════════════════════════════════════════════════════════════
# 5. recolectarItemsDeSorteo
# ══════════════════════════════════════════════════════════════
viejo = """      if (def.kind === 'posiciones'){
        for (let p = 0; p < 3; p++){
          const num = (row.posNums[p] || '').trim();
          const m = parseFloat(row.posMontos[p]) || 0;
          if (num && m > 0){
            items.push({ tipo:'posicion', numero:num, monto:m, posicion:p+1, sorteo_id:sid });
          }
        }
        return;
      }"""
nuevo = """      // POSICIONES_SINGLE_COLUMN_V1
      if (def.kind === 'posiciones'){
        const pos = parseInt(row.posicion) || 1;
        const nums = String(row.num || '').trim().split(/\\s+/).filter(function(x){ return x.length === 2; });
        const m = parseFloat(row.monto) || 0;
        if (m > 0){
          nums.forEach(function(num){
            items.push({ tipo:'posicion', numero:num, monto:m, posicion:pos, sorteo_id:sid });
          });
        }
        return;
      }"""
if viejo not in src:
    print("ERROR 5: recolectarItems"); raise SystemExit(1)
src = src.replace(viejo, nuevo, 1)

# ══════════════════════════════════════════════════════════════
# 6. calcRowTotal
# ══════════════════════════════════════════════════════════════
viejo = """  if (kind === 'posiciones'){
    let total = 0;
    for (let i = 0; i < 3; i++) total += parseFloat(row.posMontos[i]) || 0;
    return total;
  }"""
nuevo = """  // POSICIONES_SINGLE_COLUMN_V1
  if (kind === 'posiciones'){
    const nums = String(row.num || '').trim().split(/\\s+/).filter(function(x){ return x.length === 2; });
    const m = parseFloat(row.monto) || 0;
    return m * nums.length;
  }"""
if viejo not in src:
    print("ERROR 6: calcRowTotal"); raise SystemExit(1)
src = src.replace(viejo, nuevo, 1)

# ══════════════════════════════════════════════════════════════
# 7. evaluarExcepcionesSorteo
# ══════════════════════════════════════════════════════════════
viejo = """    if (def.kind === 'posiciones'){
      for (var p = 0; p < 3; p++){
        var n = String((row.posNums && row.posNums[p]) || '').trim();
        var m = parseFloat(row.posMontos && row.posMontos[p]) || 0;
        if (n && m > 0) piezas.push({ num: n, formaKey: 'posicion', monto: m });
      }
    } else {"""
nuevo = """    // POSICIONES_SINGLE_COLUMN_V1
    if (def.kind === 'posiciones'){
      var nums = String(row.num || '').trim().split(/\\s+/).filter(function(x){ return x.length === 2; });
      var m = parseFloat(row.monto) || 0;
      if (m > 0){
        nums.forEach(function(n){
          piezas.push({ num: n, formaKey: 'posicion', monto: m });
        });
      }
    } else {"""
if viejo not in src:
    print("ERROR 7: evaluarExcepciones"); raise SystemExit(1)
src = src.replace(viejo, nuevo, 1)

# ══════════════════════════════════════════════════════════════
# 8. CSS desktop
# ══════════════════════════════════════════════════════════════
viejo = """  .tabla-ap.pos-col th.num-col,.tabla-ap.pos-col td.num-col{ width:18%; }
  .tabla-ap.pos-col th.monto-col,.tabla-ap.pos-col td.monto-col{ width:15%; }
  .tabla-ap.pos-col th.total-col,.tabla-ap.pos-col td.total-col{ width:20%; }"""
nuevo = """  /* POSICIONES_SINGLE_COLUMN_V1 */
  .tabla-ap.pos-col th.possel-col,
  .tabla-ap.pos-col td.possel-col{ width:10%; }
  .tabla-ap.pos-col th.num-col,
  .tabla-ap.pos-col td.num-col{ width:38%; }
  .tabla-ap.pos-col th.monto-col,
  .tabla-ap.pos-col td.monto-col{ width:18%; }
  .tabla-ap.pos-col th.total-col,
  .tabla-ap.pos-col td.total-col{ width:22%; }
  .tabla-ap.pos-col th.del-col,
  .tabla-ap.pos-col td.del-col{ width:12%; }
  .tabla-ap .pos-sel{
    width: 100%;
    padding: 6px 2px;
    border: 1.5px solid #c8ead4;
    border-radius: 5px;
    background: var(--blue-bg);
    color: var(--blue-text-strong);
    font-weight: 700;
    font-size: .78rem;
    text-align: center;
    cursor: pointer;
    font-family: inherit;
  }
  .tabla-ap .pos-sel:focus{
    outline: none;
    border-color: var(--v-500);
    background: #fff;
    box-shadow: 0 0 0 2px rgba(34,197,94,.15);
  }"""
if viejo not in src:
    print("ERROR 8: CSS desktop"); raise SystemExit(1)
src = src.replace(viejo, nuevo, 1)

# ══════════════════════════════════════════════════════════════
# 9. CSS mobile
# ══════════════════════════════════════════════════════════════
viejo = """    .tabla-ap.pos-col th.num-col,.tabla-ap.pos-col td.num-col{ width:20%; }
    .tabla-ap.pos-col th.monto-col,.tabla-ap.pos-col td.monto-col{ width:16%; }
    .tabla-ap.pos-col th.total-col,.tabla-ap.pos-col td.total-col{ width:20%; }"""
nuevo = """    .tabla-ap.pos-col th.possel-col,
    .tabla-ap.pos-col td.possel-col{ width:13%; }
    .tabla-ap.pos-col th.num-col,
    .tabla-ap.pos-col td.num-col{ width:32%; }
    .tabla-ap.pos-col th.monto-col,
    .tabla-ap.pos-col td.monto-col{ width:19%; }
    .tabla-ap.pos-col th.total-col,
    .tabla-ap.pos-col td.total-col{ width:24%; }
    .tabla-ap.pos-col th.del-col,
    .tabla-ap.pos-col td.del-col{ width:12%; }
    .tabla-ap .pos-sel{ padding: 3px 1px; font-size: .62rem; border-radius: 4px; }"""
if viejo not in src:
    print("ERROR 9: CSS mobile"); raise SystemExit(1)
src = src.replace(viejo, nuevo, 1)

# ══════════════════════════════════════════════════════════════
# 10. inyectarLineasBoleta (preload al editar)
# ══════════════════════════════════════════════════════════════
viejo = """      } else if (def.kind === 'posiciones'){
        // TODO: agrupar por posición
        items.forEach(function(it){
          var partes = String(it.l.numero || '').split('@');
          stats.falladas++;
        });
      } else {"""
nuevo = """      } else if (def.kind === 'posiciones'){
        // POSICIONES_SINGLE_COLUMN_V1: agrupar por posición
        var porPos = {};
        items.forEach(function(it){
          var pos = String(it.l.posicion || 1);
          if (!porPos[pos]) porPos[pos] = { nums: [], monto: parseFloat(it.l.monto).toFixed(2) };
          porPos[pos].nums.push(it.l.numero);
        });
        Object.keys(porPos).forEach(function(pos){
          var g = porPos[pos];
          var row = newRow(st.forms, def.kind);
          row.posicion = pos;
          row.num = g.nums.join(' ');
          row.monto = g.monto;
          st.rows.push(row);
          stats.inyectadas += g.nums.length;
          stats.filas++;
        });
      } else {"""
if viejo not in src:
    print("WARN 10: inyectarLineasBoleta no encontrado (skip)")
else:
    src = src.replace(viejo, nuevo, 1)

p.write_text(src, encoding="utf-8")
print("OK: POSICIONES_SINGLE_COLUMN_V1 aplicado")
print("  · newRow")
print("  · renderTablaActivaSorteo")
print("  · bindTablaEventsSorteo")
print("  · autoformatearPosiciones (nueva)")
print("  · recolectarItemsDeSorteo")
print("  · calcRowTotal")
print("  · evaluarExcepcionesSorteo")
print("  · CSS desktop + mobile")
print("  · inyectarLineasBoleta (preload)")
