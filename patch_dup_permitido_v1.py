from pathlib import Path

p = Path("/home/LottoBooM/jugadas/templates/jugadas/apostar.html")
src = p.read_text(encoding="utf-8")

if "FIX_DUP_NUM_V1" in src:
    print("SKIP: ya aplicado")
    raise SystemExit(0)

# Bloque exacto observado en autoformatear (línea 3706)
viejo = """function autoformatear(texto, numDigits, maxNums){
  var s = String(texto || '').toUpperCase().replace(/[^0-9PATDX\\s]/g, '');
  var tieneEspacioFinal = /\\s$/.test(s);
  var tokens = s.split(/\\s+/).filter(function(t){ return t.length; });
  var out = [];
  var vistos = {};
  var pushUnique = function(val){
    if (!val) return;
    if (!vistos[val]){ out.push(val); vistos[val] = true; }
  };"""

nuevo = """function autoformatear(texto, numDigits, maxNums){
  var s = String(texto || '').toUpperCase().replace(/[^0-9PATDX\\s]/g, '');
  var tieneEspacioFinal = /\\s$/.test(s);
  var tokens = s.split(/\\s+/).filter(function(t){ return t.length; });
  var out = [];
  // FIX_DUP_NUM_V1: permitir tokens repetidos (el cliente puede querer 25 25)
  // El límite superior sigue impuesto por maxNums al final de la función.
  var pushUnique = function(val){
    if (!val) return;
    out.push(val);
  };"""

if viejo not in src:
    print("ERROR: no encontré el header exacto de autoformatear")
    print("Pégame este bloque exacto:")
    print("  sed -n '3706,3720p' jugadas/templates/jugadas/apostar.html")
    raise SystemExit(1)

src = src.replace(viejo, nuevo, 1)
p.write_text(src, encoding="utf-8")
print("OK: FIX_DUP_NUM_V1 aplicado")
print("FIX_DUP_NUM_V1 count:", src.count("FIX_DUP_NUM_V1"))
