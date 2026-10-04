from pathlib import Path

p = Path("/home/LottoBooM/jugadas/templates/jugadas/apostar.html")
src = p.read_text(encoding="utf-8")

# Marcadores exactos para delimitar el bloque
inicio = "function autoformatearGrupo(texto, numDigits){"
fin = "// FIX_VS_GRUPOS_V2: expande un grupo A o B a lista de números únicos"

idx_ini = src.find(inicio)
idx_fin = src.find(fin)

if idx_ini == -1 or idx_fin == -1 or idx_fin <= idx_ini:
    print("ERROR: no encontre los marcadores")
    print("idx_ini:", idx_ini, "idx_fin:", idx_fin)
    raise SystemExit(1)

nueva_funcion = '''function autoformatearGrupo(texto, numDigits){
  // VS grupos: acepta PA, T0-T9, D0-D9 + auto-separa cada numDigits (2 por defecto)
  numDigits = numDigits || 2;
  const s = String(texto).toUpperCase();
  const tieneEspacioFinal = /\\s$/.test(s);
  const limpio = s.replace(/[^0-9PATD\\s]/g, '');
  const tokens = limpio.split(/\\s+/).filter(function(t){ return t.length; });
  const out = [];
  const vistos = new Set();
  const pushUnique = function(v){
    if (v && !vistos.has(v)){ out.push(v); vistos.add(v); }
  };
  const dividirEnBloques = function(str){
    const partes = [];
    for (let i = 0; i < str.length; i += numDigits){
      partes.push(str.slice(i, i + numDigits));
    }
    return partes;
  };
  let bufferDigitos = '';
  for (let k = 0; k < tokens.length; k++){
    const tok = tokens[k];
    const esUltimo = (k === tokens.length - 1);
    if (/^(PA|T\\d|D\\d)$/.test(tok)){
      if (bufferDigitos){ dividirEnBloques(bufferDigitos).forEach(pushUnique); bufferDigitos = ''; }
      pushUnique(tok);
      continue;
    }
    if (esUltimo && /^(P|T|D)$/.test(tok)){
      if (bufferDigitos){ dividirEnBloques(bufferDigitos).forEach(pushUnique); bufferDigitos = ''; }
      pushUnique(tok);
      continue;
    }
    if (/^\\d+$/.test(tok)){
      bufferDigitos += tok;
      if (esUltimo){
        dividirEnBloques(bufferDigitos).forEach(pushUnique);
        bufferDigitos = '';
      }
      continue;
    }
  }
  if (bufferDigitos){ dividirEnBloques(bufferDigitos).forEach(pushUnique); }
  let result = out.join(' ');
  if (out.length && tieneEspacioFinal) result += ' ';
  return result;
}

'''

# Reemplazar entre idx_ini y idx_fin
src_new = src[:idx_ini] + nueva_funcion + src[idx_fin:]
p.write_text(src_new, encoding="utf-8")
print("OK: autoformatearGrupo reemplazada")

# Verificacion rapida
assert "bufferDigitos" in src_new
assert "dividirEnBloques" in src_new
print("OK: bufferDigitos + dividirEnBloques presentes")
