from pathlib import Path

p = Path("/home/LottoBooM/jugadas/templates/jugadas/apostar.html")
src = p.read_text(encoding="utf-8")

if "numerosMap" in src and "FIX_REPETIDOS_V1" in src:
    print("SKIP: ya aplicado")
    raise SystemExit(0)

viejo = """function numerosEnFila(row, numDigits, maxNums){
  const num = (row.num || '').trim();
  if (!num) return { numeros: [], paresExplicitos: [] };

  const tokens = num.split(/\\s+/).filter(function(x){ return x; });
  const numerosSet = new Set();
  const paresExplicitos = [];   // Array (permite repetidos)

  for (let ti = 0; ti < tokens.length; ti++){
    const tok = tokens[ti];
    const tokUpper = tok.toUpperCase();

    // Detectar X/x (case-insensitive)
    if (tokUpper.indexOf('X') !== -1){
      const parts = tokUpper.split('X').map(function(p){ return p.replace(/\\D/g, ''); });
      if (parts.length === 2 && parts[0].length && parts[1].length){
        paresExplicitos.push(parts[0] + 'x' + parts[1]);   // siempre 'x' minuscula
      } else if (parts.length >= 2 && parts[0].length){
        // Mal formado, tomar los primeros 2 + siguientes 2
        const all = tokUpper.replace(/[^0-9]/g, '');
        if (all.length >= 4){
          paresExplicitos.push(all.slice(0,2) + 'x' + all.slice(2,4));
        }
      }
      continue;
    }

    const exp = expandirToken(tok, numDigits);
    exp.forEach(function(n){ numerosSet.add(n); });
  }

  let nums = Array.from(numerosSet);
  if (maxNums && nums.length > maxNums) nums = nums.slice(0, maxNums);

  return {
    numeros: nums,
    paresExplicitos: paresExplicitos
  };
}"""

nuevo = """function numerosEnFila(row, numDigits, maxNums){
  const num = (row.num || '').trim();
  if (!num) return { numeros: [], paresExplicitos: [] };

  const tokens = num.split(/\\s+/).filter(function(x){ return x; });
  // FIX_REPETIDOS_V1: Map para contar apariciones (max 2 por numero)
  const numerosMap = new Map();
  const paresExplicitos = [];   // Array (permite repetidos)

  for (let ti = 0; ti < tokens.length; ti++){
    const tok = tokens[ti];
    const tokUpper = tok.toUpperCase();

    // Detectar X/x (case-insensitive)
    if (tokUpper.indexOf('X') !== -1){
      const parts = tokUpper.split('X').map(function(p){ return p.replace(/\\D/g, ''); });
      if (parts.length === 2 && parts[0].length && parts[1].length){
        paresExplicitos.push(parts[0] + 'x' + parts[1]);
      } else if (parts.length >= 2 && parts[0].length){
        const all = tokUpper.replace(/[^0-9]/g, '');
        if (all.length >= 4){
          paresExplicitos.push(all.slice(0,2) + 'x' + all.slice(2,4));
        }
      }
      continue;
    }

    const exp = expandirToken(tok, numDigits);
    exp.forEach(function(n){
      const actual = numerosMap.get(n) || 0;
      if (actual < 2) numerosMap.set(n, actual + 1);
    });
  }

  // Reconstruir array preservando duplicados (max 2 por numero)
  let nums = [];
  numerosMap.forEach(function(veces, n){
    for (let k = 0; k < veces; k++) nums.push(n);
  });
  if (maxNums && nums.length > maxNums) nums = nums.slice(0, maxNums);

  return {
    numeros: nums,
    paresExplicitos: paresExplicitos
  };
}"""

if viejo not in src:
    print("ERROR: no matcheo el bloque exacto")
    raise SystemExit(1)

src = src.replace(viejo, nuevo, 1)
p.write_text(src, encoding="utf-8")
print("OK: numerosEnFila con FIX_REPETIDOS_V1")
print("numerosMap:", src.count("numerosMap"))
print("FIX_REPETIDOS_V1:", src.count("FIX_REPETIDOS_V1"))
