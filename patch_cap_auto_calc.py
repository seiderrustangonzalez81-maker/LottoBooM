from pathlib import Path
import ast

p = Path("/home/LottoBooM/jugadas/templates/jugadas/apostar.html")
src = p.read_text(encoding="utf-8")

# Reemplazar TODO el bloque de la rama else (parlet + candado) con la versión corregida
viejo = """        } else {
          const val = parseFloat(this.value);
          if (f === 'parlet'){
            row.montos['parlet'] = this.value;
            if (inpCand){
              // parlet * nPlays siempre exacto (no hay decimales infinitos)
              const totalCand = (val * nPlays).toFixed(2);
              row.montos['candado'] = totalCand;
              inpCand.value = totalCand;
              inpCand.readOnly = true;
              inpCand.classList.add('monto-blocked');
            }
          } else { // candado
            row.montos['candado'] = this.value;
            // CAP_CANDADO_V2: solo capar si excede pool*nPlays, no tocar parlet
            // (el usuario ve el candado tal cual lo escribió)
          }
        }"""

nuevo = """        } else {
          var val = parseFloat(this.value) || 0;
          var _poolParl = (typeof _getPool === 'function') ? _getPool(sid, 'parlet') : 0;

          if (f === 'parlet'){
            // ═══ CAP_PARLET_V3: capar parlet al pool disponible del gestor ═══
            if (_poolParl > 0 && val > _poolParl){
              val = _poolParl;
              this.value = val.toFixed(2);
              if (typeof toast === 'function'){
                toast('⚠️ Parlet capado a $' + val.toFixed(2) + ' por límite disponible', 'warning');
              }
            }
            row.montos['parlet'] = this.value;
            if (inpCand){
              // Auto-calcular candado = parlet * nPlays
              const totalCand = (val * nPlays).toFixed(2);
              row.montos['candado'] = totalCand;
              inpCand.value = totalCand;
              inpCand.readOnly = true;
              inpCand.classList.add('monto-blocked');
            }
          } else { // candado
            // ═══ CAP_CANDADO_V3: capar candado a pool * nPlays ═══
            var _maxCand = _poolParl * nPlays;
            if (_poolParl > 0 && nPlays > 0 && val > _maxCand){
              val = _maxCand;
              this.value = val.toFixed(2);
              if (typeof toast === 'function'){
                toast('⚠️ Candado capado a $' + val.toFixed(2) + ' por límite disponible', 'warning');
              }
            }
            row.montos['candado'] = this.value;
            if (inpParlet){
              // Auto-calcular parlet = candado / nPlays (TRUNCADO)
              var percap = Math.floor((val / nPlays) * 100) / 100;
              row.montos['parlet'] = percap.toFixed(2);
              inpParlet.value = percap.toFixed(2);
              inpParlet.readOnly = true;
              inpParlet.classList.add('monto-blocked');
            }
          }
        }"""

if "CAP_PARLET_V3" in src:
    print("SKIP: ya aplicado")
    raise SystemExit(0)

if viejo not in src:
    print("ERROR: no encontre el bloque else original")
    print("Corre: sed -n '2880,2920p' jugadas/templates/jugadas/apostar.html")
    raise SystemExit(1)

src = src.replace(viejo, nuevo, 1)
p.write_text(src, encoding="utf-8")
print("OK: bloque parlet/candado reescrito")
print("CAP_PARLET_V3:", src.count("CAP_PARLET_V3"))
print("CAP_CANDADO_V3:", src.count("CAP_CANDADO_V3"))
