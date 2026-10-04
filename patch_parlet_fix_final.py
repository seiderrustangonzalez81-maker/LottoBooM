from pathlib import Path

p = Path("/home/LottoBooM/jugadas/templates/jugadas/apostar.html")
src = p.read_text(encoding="utf-8")
cambios = []

# ═══════════════════════════════════════════════════════════════
# REVERT 1 — contarParletsDeFila vuelve a contar posicional
# ═══════════════════════════════════════════════════════════════
viejo1 = """function contarParletsDeFila(row, numDigits, maxNums){
  // PARLET_DEDUP_V1: deduplicar pares por valor (no por posición)
  const { numeros, paresExplicitos } = numerosEnFila(row, numDigits, maxNums);
  const paresSet = new Set();
  for (let i = 0; i < numeros.length; i++){
    for (let j = i + 1; j < numeros.length; j++){
      var a = numeros[i], b = numeros[j];
      // Normalizar: "90x99" y "99x90" son el mismo par
      var key = (a <= b) ? (a + 'x' + b) : (b + 'x' + a);
      paresSet.add(key);
    }
  }
  return paresSet.size + paresExplicitos.length;
}"""

nuevo1 = """function contarParletsDeFila(row, numDigits, maxNums){
  // Cuenta pares POSICIONALES (permite repetidos por valor)
  const { numeros, paresExplicitos } = numerosEnFila(row, numDigits, maxNums);
  const n = numeros.length;
  const nPares = paresExplicitos.length;
  return n * (n - 1) / 2 + nPares;
}"""

if "Cuenta pares POSICIONALES" in src:
    cambios.append("REVERT 1: SKIP")
elif viejo1 in src:
    src = src.replace(viejo1, nuevo1, 1)
    cambios.append("REVERT 1: OK")
else:
    cambios.append("REVERT 1: WARN (no matcheo)")

# ═══════════════════════════════════════════════════════════════
# REVERT 2 — recolectarItemsDeSorteo vuelve a generar 190 items
# ═══════════════════════════════════════════════════════════════
viejo2 = """        if (f === 'parlet'){
          // PARLET_DEDUP_V1: deduplicar pares por valor
          var paresSet = new Set();
          for (let i = 0; i < numeros.length; i++){
            for (let j = i + 1; j < numeros.length; j++){
              var a = numeros[i], b = numeros[j];
              var key = (a <= b) ? (a + 'x' + b) : (b + 'x' + a);
              if (paresSet.has(key)) continue;
              paresSet.add(key);
              items.push({ tipo: f, numero: key, monto: m, sorteo_id:sid });
            }
          }
          paresExplicitos.forEach(p => items.push({ tipo: f, numero: p, monto: m, sorteo_id:sid }));
        }"""

nuevo2 = """        if (f === 'parlet'){
          // Generar pares POSICIONALES (conserva repetidos)
          for (let i = 0; i < numeros.length; i++){
            for (let j = i + 1; j < numeros.length; j++){
              items.push({ tipo: f, numero: numeros[i] + 'x' + numeros[j], monto: m, sorteo_id:sid });
            }
          }
          paresExplicitos.forEach(p => items.push({ tipo: f, numero: p, monto: m, sorteo_id:sid }));
        }"""

if "Generar pares POSICIONALES (conserva repetidos)" in src:
    cambios.append("REVERT 2: SKIP")
elif viejo2 in src:
    src = src.replace(viejo2, nuevo2, 1)
    cambios.append("REVERT 2: OK")
else:
    cambios.append("REVERT 2: WARN (no matcheo)")

# ═══════════════════════════════════════════════════════════════
# FIX 3 — agruparPorNumero ahora cuenta veces + suma monto
# ═══════════════════════════════════════════════════════════════
viejo3 = """function agruparPorNumero(items){
  const porNumero = {};
  items.forEach(i => {
    if (!porNumero[i.tipo]) porNumero[i.tipo] = {};
    const key = (i.tipo === 'posicion' && i.posicion)
      ? `${i.numero}@${i.posicion}`
      : i.numero;
    if (!porNumero[i.tipo][key]) porNumero[i.tipo][key] = 0;
    porNumero[i.tipo][key] += i.monto;
  });
  return porNumero;
}"""

nuevo3 = """function agruparPorNumero(items){
  // PARLET_COUNT_V1: guarda monto unitario y veces (no suma montos)
  const porNumero = {};
  items.forEach(i => {
    if (!porNumero[i.tipo]) porNumero[i.tipo] = {};
    const key = (i.tipo === 'posicion' && i.posicion)
      ? `${i.numero}@${i.posicion}`
      : i.numero;
    if (!porNumero[i.tipo][key]) {
      porNumero[i.tipo][key] = { monto: i.monto, veces: 1 };
    } else {
      porNumero[i.tipo][key].veces += 1;
    }
  });
  return porNumero;
}"""

if "PARLET_COUNT_V1" in src and "guardar monto unitario y veces" not in src:
    pass
if "PARLET_COUNT_V1: guarda monto unitario" in src:
    cambios.append("FIX 3: SKIP")
elif viejo3 in src:
    src = src.replace(viejo3, nuevo3, 1)
    cambios.append("FIX 3: OK (agruparPorNumero cuenta veces)")
else:
    cambios.append("FIX 3: WARN (no matcheo agruparPorNumero)")

# ═══════════════════════════════════════════════════════════════
# FIX 4 — renderMiniResumenSorteo muestra (xN) si veces > 1
# ═══════════════════════════════════════════════════════════════
# Buscar el bloque donde renderiza el monto de parlet y añadir el (xN)
viejo4 = """    if (montos.length === 1){
      const monto = montos[0];
      const d = porMonto[monto];
      const totalCount = d.numeros.length;
      const listaNums = d.numeros.map(n => `<span class="num">${esc(n)}</span>`).join(' ');
      html += `<div class="res-linea">
        <span class="forma">Parlet<span class="forma-count">${totalCount}</span></span>
        <span class="numeros">${listaNums}</span>
        <span class="monto-total">$${parseFloat(monto).toFixed(2)}</span>
      </div>`;
    } else {"""

nuevo4 = """    if (montos.length === 1){
      const monto = montos[0];
      const d = porMonto[monto];
      const totalCount = d.numeros.length;
      // PARLET_COUNT_V1: mostrar (xN) si el par se repite
      const listaNums = d.numeros.map(function(n){
        var veces = (d.vecesMap && d.vecesMap[n]) ? d.vecesMap[n] : 1;
        var sufijo = veces > 1 ? ' <small style="color:#b45309;font-weight:900;">(x' + veces + ')</small>' : '';
        return '<span class="num">' + esc(n) + sufijo + '</span>';
      }).join(' ');
      html += `<div class="res-linea">
        <span class="forma">Parlet<span class="forma-count">${totalCount}</span></span>
        <span class="numeros">${listaNums}</span>
        <span class="monto-total">$${parseFloat(monto).toFixed(2)}</span>
      </div>`;
    } else {"""

if "PARLET_COUNT_V1: mostrar (xN)" in src:
    cambios.append("FIX 4: SKIP")
elif viejo4 in src:
    src = src.replace(viejo4, nuevo4, 1)
    cambios.append("FIX 4: OK (muestra xN en resumen)")
else:
    cambios.append("FIX 4: WARN (no matcheo bloque render parlet)")

p.write_text(src, encoding="utf-8")

print("═══ REPORTE ═══")
for c in cambios:
    print(f"  {c}")
print("")
print("PARLET_COUNT_V1:", src.count("PARLET_COUNT_V1"))
print("PARLET_DEDUP_V1:", src.count("PARLET_DEDUP_V1"), "(debe ser 0)")
