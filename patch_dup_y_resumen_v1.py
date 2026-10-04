from pathlib import Path
import re

p = Path("/home/LottoBooM/jugadas/templates/jugadas/apostar.html")
src = p.read_text(encoding="utf-8")

cambios = []

# ═══════════════════════════════════════════════════════════════
# FIX A — autoformatear: permitir números repetidos
# ═══════════════════════════════════════════════════════════════
if "FIX_DUP_NUM_V1" in src:
    print("SKIP A: FIX_DUP_NUM_V1 ya aplicado")
else:
    viejo_a = """  var out = [];
  var vistos = {};
  var pushUnique = function(val){
    if (!val) return;
    if (!vistos[val]){ out.push(val); vistos[val] = true; }
  };"""
    nuevo_a = """  var out = [];
  // FIX_DUP_NUM_V1: permitir tokens repetidos (el cliente puede querer 25 25)
  // El límite superior sigue impuesto por maxNums al final de la función.
  var pushUnique = function(val){
    if (!val) return;
    out.push(val);
  };"""
    if viejo_a in src:
        src = src.replace(viejo_a, nuevo_a, 1)
        print("OK A: autoformatear ahora permite duplicados")
    else:
        print("WARN A: no encontré el header de autoformatear")

# ═══════════════════════════════════════════════════════════════
# FIX B1 — parlet: .toFixed sobre {monto,veces} + llenar vecesMap
# ═══════════════════════════════════════════════════════════════
viejo_b1 = """  Object.keys(agrupado).forEach(tipo=>{
      Object.keys(agrupado[tipo]).forEach(num=>{
        const montoKey = agrupado[tipo][num].toFixed(2);
        if (!porMonto[montoKey]) porMonto[montoKey] = { numeros: [], tipos: new Set() };
        porMonto[montoKey].numeros.push(num);
        porMonto[montoKey].tipos.add(tipo);
      });
    });"""
nuevo_b1 = """  Object.keys(agrupado).forEach(tipo=>{
      Object.keys(agrupado[tipo]).forEach(num=>{
        const _info = agrupado[tipo][num];
        const montoKey = _info.monto.toFixed(2);
        if (!porMonto[montoKey]) porMonto[montoKey] = { numeros: [], tipos: new Set(), vecesMap: {} };
        porMonto[montoKey].numeros.push(num);
        porMonto[montoKey].vecesMap[num] = _info.veces;
        porMonto[montoKey].tipos.add(tipo);
      });
    });"""
if viejo_b1 in src:
    src = src.replace(viejo_b1, nuevo_b1, 1)
    print("OK B1: parlet — .monto.toFixed + vecesMap poblado")
else:
    print("WARN B1: no encontré bloque parlet")

# ═══════════════════════════════════════════════════════════════
# FIX B2 — posición
# ═══════════════════════════════════════════════════════════════
viejo_b2 = '<span class="monto-total">$${grupo[k].toFixed(2)}</span>'
nuevo_b2 = '<span class="monto-total">$${grupo[k].monto.toFixed(2)}</span>'
if viejo_b2 in src:
    src = src.replace(viejo_b2, nuevo_b2, 1)
    print("OK B2: posición — .monto.toFixed")
else:
    print("WARN B2: no encontré línea posición")

# ═══════════════════════════════════════════════════════════════
# FIX B3 — resto de formas
# ═══════════════════════════════════════════════════════════════
viejo_b3 = "const montoKey = grupo[num].toFixed(2);"
nuevo_b3 = "const montoKey = grupo[num].monto.toFixed(2);"
if viejo_b3 in src:
    src = src.replace(viejo_b3, nuevo_b3, 1)
    print("OK B3: resto — .monto.toFixed")
else:
    print("WARN B3: no encontré 'grupo[num].toFixed(2)' (quizá está distinto)")

# ═══════════════════════════════════════════════════════════════
# FIX B4 — barrido final: cualquier otro .toFixed(2) sospechoso
#         sobre accesos por corchete a grupos de agruparPorNumero
# ═══════════════════════════════════════════════════════════════
pat = re.compile(r"(\b(?:agrupado\[tipo\]\[num\]|grupo\[[a-z]+\]|porNumero\[[^\]]+\]\[[^\]]+\]))\.toFixed\(2\)")
src, n = pat.subn(r"\1.monto.toFixed(2)", src)
if n:
    print(f"OK B4: barrido final — {n} ocurrencias adicionales")

# ═══════════════════════════════════════════════════════════════
# Guardar
# ═══════════════════════════════════════════════════════════════
p.write_text(src, encoding="utf-8")

print()
print("═══ Resumen ═══")
print(f"FIX_DUP_NUM_V1         : {src.count('FIX_DUP_NUM_V1')}")
print(f"vecesMap populado      : {src.count('vecesMap[num] = _info.veces')}")
print(f"'grupo[num].monto'     : {src.count('grupo[num].monto')}")
print(f"'grupo[k].monto'       : {src.count('grupo[k].monto')}")
