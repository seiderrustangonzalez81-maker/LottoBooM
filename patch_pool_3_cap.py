from pathlib import Path

p = Path("/home/LottoBooM/jugadas/templates/jugadas/apostar.html")
src = p.read_text(encoding="utf-8")

if "CAP_POOL_V1" in src:
    print("SKIP: ya aplicado")
    raise SystemExit(0)

# Ancla: después de "const nPlays = contarParletsDeFila(row, def.numDigits, def.maxNums);"
viejo = """      if (tieneParlet && tieneCandado && (f === 'parlet' || f === 'candado')){
        const inpParlet = cont.querySelector('input[data-row="' + i + '"][data-form="parlet"]');
        const inpCand   = cont.querySelector('input[data-row="' + i + '"][data-form="candado"]');
        const nPlays = contarParletsDeFila(row, def.numDigits, def.maxNums);"""

nuevo = """      if (tieneParlet && tieneCandado && (f === 'parlet' || f === 'candado')){
        const inpParlet = cont.querySelector('input[data-row="' + i + '"][data-form="parlet"]');
        const inpCand   = cont.querySelector('input[data-row="' + i + '"][data-form="candado"]');
        const nPlays = contarParletsDeFila(row, def.numDigits, def.maxNums);

        // ═══ CAP_POOL_V1: capar monto si supera pool del gestor ═══
        try {
          var _valRaw = parseFloat(this.value) || 0;
          if (_valRaw > 0 && nPlays >= 1){
            var _poolParl = (typeof _getPool === 'function') ? _getPool(sid, 'parlet') : 0;
            if (_poolParl > 0){
              var _maxParl = _poolParl;
              var _maxCand = _poolParl * nPlays;
              var _esParlet = (f === 'parlet');
              var _maxActual = _esParlet ? _maxParl : _maxCand;
              if (_valRaw > _maxActual){
                var _valCap = Math.floor(_maxActual * 100) / 100;
                this.value = _valCap.toFixed(2);
                if (typeof toast === 'function'){
                  toast('⚠️ ' + (_esParlet ? 'Parlet' : 'Candado') + ' capado a $' + _valCap.toFixed(2) + ' por límite del gestor', 'warning');
                }
              }
            }
          }
        } catch(_eCap){ console.warn('[CAP_POOL]', _eCap); }
        // ═══ FIN CAP_POOL_V1 ═══"""

if viejo not in src:
    print("ERROR: no encontre el bloque exacto")
    print("Corre: grep -n 'tieneParlet && tieneCandado' -A 5 jugadas/templates/jugadas/apostar.html")
    raise SystemExit(1)

src = src.replace(viejo, nuevo, 1)
p.write_text(src, encoding="utf-8")
print("OK: CAP_POOL_V1 aplicado")
print("CAP_POOL_V1:", src.count("CAP_POOL_V1"))
print("_getPool:", src.count("_getPool"))
