from pathlib import Path

p = Path("/home/LottoBooM/jugadas/templates/jugadas/apostar.html")
src = p.read_text(encoding="utf-8")
cambios = []

# ═══════════════════════════════════════════════════════════════
# FIX 1 — Bloque candado → parlet (línea ~2816)
# ═══════════════════════════════════════════════════════════════
viejo1 = """            if (inpParlet){
              const percap = val / nPlays;
              row.montos['parlet'] = percap.toFixed(2);
              inpParlet.value = percap.toFixed(2);
              inpParlet.readOnly = true;
              inpParlet.classList.add('monto-blocked');
            }"""

nuevo1 = """            if (inpParlet){
              // TRUNCAR (no redondear) para que percap * nPlays <= candado
              const percap = Math.floor((val / nPlays) * 100) / 100;
              row.montos['parlet'] = percap.toFixed(2);
              inpParlet.value = percap.toFixed(2);
              // El candado REAL cobrado = percap * nPlays (puede ser < val)
              const candadoReal = (percap * nPlays).toFixed(2);
              row.montos['candado'] = candadoReal;
              if (inpCand) inpCand.value = candadoReal;
              inpParlet.readOnly = true;
              inpParlet.classList.add('monto-blocked');
            }"""

if "Math.floor((val / nPlays) * 100) / 100" in src:
    cambios.append("FIX 1: SKIP")
elif viejo1 in src:
    src = src.replace(viejo1, nuevo1, 1)
    cambios.append("FIX 1: OK")
else:
    cambios.append("FIX 1: ERROR")

# ═══════════════════════════════════════════════════════════════
# FIX 2 — recalcularVinculoParletCandado (línea ~3111)
# ═══════════════════════════════════════════════════════════════
viejo2 = """  if (parletBlocked && vCand > 0){
    const percap = vCand / nPlays;
    row.montos['parlet'] = percap.toFixed(2);
    inpParlet.value = percap.toFixed(2);
  }"""

nuevo2 = """  if (parletBlocked && vCand > 0){
    const percap = Math.floor((vCand / nPlays) * 100) / 100;
    row.montos['parlet'] = percap.toFixed(2);
    inpParlet.value = percap.toFixed(2);
    const candadoReal = (percap * nPlays).toFixed(2);
    row.montos['candado'] = candadoReal;
    if (inpCand) inpCand.value = candadoReal;
  }"""

if "Math.floor((vCand / nPlays) * 100) / 100" in src:
    cambios.append("FIX 2: SKIP")
elif viejo2 in src:
    src = src.replace(viejo2, nuevo2, 1)
    cambios.append("FIX 2: OK")
else:
    cambios.append("FIX 2: WARN (no matcheo exacto, revisar)")

# ═══════════════════════════════════════════════════════════════
# FIX 3 — Candado desde parlet: NO redondear, ya es exacto
# (parlet es la base, candado = parlet * nPlays siempre exacto)
# ═══════════════════════════════════════════════════════════════
viejo3 = """          if (f === 'parlet'){
            row.montos['parlet'] = this.value;
            if (inpCand){
              const totalCand = val * nPlays;
              row.montos['candado'] = totalCand.toFixed(2);
              inpCand.value = totalCand.toFixed(2);
              inpCand.readOnly = true;
              inpCand.classList.add('monto-blocked');
            }
          }"""

nuevo3 = """          if (f === 'parlet'){
            row.montos['parlet'] = this.value;
            if (inpCand){
              // parlet * nPlays siempre exacto (no hay decimales infinitos)
              const totalCand = (val * nPlays).toFixed(2);
              row.montos['candado'] = totalCand;
              inpCand.value = totalCand;
              inpCand.readOnly = true;
              inpCand.classList.add('monto-blocked');
            }
          }"""

if "parlet * nPlays siempre exacto" in src:
    cambios.append("FIX 3: SKIP")
elif viejo3 in src:
    src = src.replace(viejo3, nuevo3, 1)
    cambios.append("FIX 3: OK (solo comentario, sin cambio funcional)")
else:
    cambios.append("FIX 3: SKIP (opcional)")

# ═══════════════════════════════════════════════════════════════
p.write_text(src, encoding="utf-8")

print("═══ REPORTE ═══")
for c in cambios:
    print(f"  {c}")
print("")
print("Math.floor( / nPlays):", src.count("Math.floor"))
print("toFixed(2) en percap:", src.count("percap.toFixed(2)"))
