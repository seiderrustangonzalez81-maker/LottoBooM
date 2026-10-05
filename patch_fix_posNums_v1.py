from pathlib import Path

p = Path("/home/LottoBooM/jugadas/templates/jugadas/apostar.html")
src = p.read_text(encoding="utf-8")

if "FIX_POSNUMS_V1" in src:
    print("SKIP: ya aplicado")
    raise SystemExit(0)

cambios = 0

# ══════════════════════════════════════════════════════════════
# Fix 1: renderTabsSorteo — nValidos para posiciones
# ══════════════════════════════════════════════════════════════
viejo1 = """    const nValidos = st.rows.reduce((acc, r)=>{
      if (def.kind === 'posiciones'){
        return acc + r.posNums.filter(x => x && String(x).length).length;
      }"""

nuevo1 = """    const nValidos = st.rows.reduce((acc, r)=>{
      // FIX_POSNUMS_V1: usar la nueva forma del row (num, monto)
      if (def.kind === 'posiciones'){
        var nums = String(r.num || '').trim().split(/\\s+/).filter(function(x){ return x.length === 2; });
        return acc + nums.length;
      }"""

if viejo1 in src:
    src = src.replace(viejo1, nuevo1, 1)
    print("OK: renderTabsSorteo parcheado")
    cambios += 1
else:
    print("WARN 1: no encontré el bloque nValidos")

# ══════════════════════════════════════════════════════════════
# Fix 2: _sorteoTieneJugadas
# ══════════════════════════════════════════════════════════════
viejo2 = """      if (def.kind === 'posiciones'){
        for (var p = 0; p < 3; p++){
          if ((row.posNums[p] || '').trim() && parseFloat(row.posMontos[p]) > 0) tiene = true;
        }
      } else if (def.kind === 'vs_groups'){"""

nuevo2 = """      if (def.kind === 'posiciones'){
        // FIX_POSNUMS_V1: nueva forma del row
        var numsPos = String(row.num || '').trim().split(/\\s+/).filter(function(x){ return x.length === 2; });
        if (numsPos.length && parseFloat(row.monto) > 0) tiene = true;
      } else if (def.kind === 'vs_groups'){"""

if viejo2 in src:
    src = src.replace(viejo2, nuevo2, 1)
    print("OK: _sorteoTieneJugadas parcheado")
    cambios += 1
else:
    print("WARN 2: no encontré el bloque _sorteoTieneJugadas")

# ══════════════════════════════════════════════════════════════
# Fix 3: inyectarLineasBoleta — buscar y limpiar las referencias viejas
# ══════════════════════════════════════════════════════════════
# Verificar si quedan referencias a posNums/posMontos en el archivo
residuales = src.count("posNums") + src.count("posMontos")
print(f"Referencias residuales a posNums/posMontos: {residuales}")

if residuales > 0:
    # Buscar cada una para mostrar dónde
    lines = src.split("\n")
    for i, ln in enumerate(lines, 1):
        if "posNums" in ln or "posMontos" in ln:
            print(f"  Línea {i}: {ln.strip()[:100]}")

p.write_text(src, encoding="utf-8")
print(f"\n✅ {cambios} cambio(s) aplicado(s)")
