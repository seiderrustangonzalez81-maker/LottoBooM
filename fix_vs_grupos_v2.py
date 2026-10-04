# -*- coding: utf-8 -*-
"""
VS grupos: abreviaturas (PA/T/D) + múltiples números + dedup intra-grupo.
Con validación de sintaxis JS antes de aplicar. Rollback automático si falla.
"""
import re, shutil, datetime, subprocess, sys
from pathlib import Path

APOSTAR = Path('/home/LottoBooM/jugadas/templates/jugadas/apostar.html')
TS = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')

t = APOSTAR.read_text(encoding='utf-8')
orig = t

# ═══════════════════════════════════════════════════════════
# 1. Reemplazar autoformatearGrupo (más robusto)
# ═══════════════════════════════════════════════════════════
viejo_afg = '''function autoformatearGrupo(texto, numDigits){
  numDigits = numDigits || 2;
  const s = String(texto).toUpperCase();
  const tieneEspacioFinal = /\\s$/.test(s);
  const digitsOnly = s.replace(/[^0-9]/g, '');
  const partes = digitsOnly.match(new RegExp('.{1,' + numDigits + '}', 'g')) || [];
  const out = [];
  const vistos = new Set();
  partes.forEach(p => {
    if (p && !vistos.has(p)){ out.push(p); vistos.add(p); }
  });
  let result = out.join(' ');
  if (out.length && tieneEspacioFinal) result += ' ';
  return result;
}'''

nuevo_afg = '''function autoformatearGrupo(texto, numDigits){
  // FIX_VS_GRUPOS_V2: acepta PA, T0-T9, D0-D9 + múltiples números
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
  for (let k = 0; k < tokens.length; k++){
    const tok = tokens[k];
    // Abreviatura completa: PA, T5, D3
    if (/^(PA|T\\d|D\\d)$/.test(tok)){ pushUnique(tok); continue; }
    // Abreviatura en progreso: P, T, D (al final del texto)
    if (/^(P|T|D)$/.test(tok)){ pushUnique(tok); continue; }
    // Solo dígitos: agrupar en bloques de numDigits
    if (/^\\d+$/.test(tok)){
      if (tok.length % numDigits === 0){
        const partes = tok.match(new RegExp('.{1,' + numDigits + '}', 'g')) || [];
        partes.forEach(function(p){ pushUnique(p); });
      } else {
        pushUnique(tok);
      }
      continue;
    }
  }
  let result = out.join(' ');
  if (out.length && tieneEspacioFinal) result += ' ';
  return result;
}

// FIX_VS_GRUPOS_V2: expande un grupo A o B a lista de números únicos
function expandirGrupoVS(texto, numDigits){
  numDigits = numDigits || 2;
  const s = String(texto || '').toUpperCase().trim();
  if (!s) return [];
  const tokens = s.split(/\\s+/).filter(function(t){ return t.length; });
  const set = new Set();
  for (let k = 0; k < tokens.length; k++){
    const tok = tokens[k];
    const exp = expandirToken(tok, numDigits);
    exp.forEach(function(n){ set.add(n); });
  }
  return Array.from(set);
}'''

if viejo_afg in t:
    t = t.replace(viejo_afg, nuevo_afg, 1)
    print('OK: autoformatearGrupo reemplazado + expandirGrupoVS añadido')
elif 'FIX_VS_GRUPOS_V2' in t:
    print('-- ya estaba parcheado')
    raise SystemExit(0)
else:
    print('!! bloque autoformatearGrupo no encontrado')
    sys.exit(1)

# ═══════════════════════════════════════════════════════════
# 2. recolectarItemsDeSorteo — vs_groups con expandir
# ═══════════════════════════════════════════════════════════
viejo_rec = '''      if (def.kind === 'vs_groups'){
        const numsA = (row.numA||'').trim().split(/\\s+/).filter(x => x.length === 2);
        const numsB = (row.numB||'').trim().split(/\\s+/).filter(x => x.length === 2);
        const monto = parseFloat(row.monto) || 0;'''

nuevo_rec = '''      if (def.kind === 'vs_groups'){
        // FIX_VS_GRUPOS_V2: expandir abreviaturas
        const numsA = expandirGrupoVS(row.numA, def.numDigits);
        const numsB = expandirGrupoVS(row.numB, def.numDigits);
        const monto = parseFloat(row.monto) || 0;'''

if viejo_rec in t:
    t = t.replace(viejo_rec, nuevo_rec, 1)
    print('OK: recolectarItemsDeSorteo vs_groups')
else:
    print('!! bloque recolectar vs_groups no encontrado')

# ═══════════════════════════════════════════════════════════
# 3. calcRowTotal — vs_groups con expandir
# ═══════════════════════════════════════════════════════════
viejo_crt = '''  if (kind === 'vs_groups'){
    const numsA = (row.numA||'').trim().split(/\\s+/).filter(x => x.length === 2);
    const numsB = (row.numB||'').trim().split(/\\s+/).filter(x => x.length === 2);
    const combos = numsA.length * numsB.length;
    const monto = parseFloat(row.monto) || 0;
    return monto * combos;
  }'''

nuevo_crt = '''  if (kind === 'vs_groups'){
    // FIX_VS_GRUPOS_V2: expandir abreviaturas
    const numsA = expandirGrupoVS(row.numA, numDigits);
    const numsB = expandirGrupoVS(row.numB, numDigits);
    const combos = numsA.length * numsB.length;
    const monto = parseFloat(row.monto) || 0;
    return monto * combos;
  }'''

if viejo_crt in t:
    t = t.replace(viejo_crt, nuevo_crt, 1)
    print('OK: calcRowTotal vs_groups')
else:
    print('-- bloque calcRowTotal vs_groups no encontrado (puede usar otro formato)')

# ═══════════════════════════════════════════════════════════
# 4. Contador renderTabsSorteo — vs_groups con expandir
# ═══════════════════════════════════════════════════════════
viejo_cnt = '''      if (def.kind === 'vs_groups'){
        const nA = (r.numA||'').trim().split(/\\s+/).filter(x=>x.length===2).length;
        const nB = (r.numB||'').trim().split(/\\s+/).filter(x=>x.length===2).length;
        return acc + (nA * nB);
      }'''

nuevo_cnt = '''      if (def.kind === 'vs_groups'){
        // FIX_VS_GRUPOS_V2: expandir para contador real
        const nA = expandirGrupoVS(r.numA, def.numDigits).length;
        const nB = expandirGrupoVS(r.numB, def.numDigits).length;
        return acc + (nA * nB);
      }'''

if viejo_cnt in t:
    t = t.replace(viejo_cnt, nuevo_cnt, 1)
    print('OK: contador renderTabsSorteo vs_groups')
else:
    print('-- bloque contador no encontrado (puede usar otro formato)')

# ═══════════════════════════════════════════════════════════
# 5. VALIDACIÓN DE SINTAXIS JS
# ═══════════════════════════════════════════════════════════
print()
print('Validando sintaxis...')

# Extraer el bloque <script> final
blocks = re.findall(r'<script>([\s\S]*?)</script>', t)
if not blocks:
    print('!! no se encontró <script>')
    sys.exit(1)
js = blocks[-1]

# Guardar temporal para validar
tmp_js = Path('/tmp/vs_check.js')
tmp_js.write_text(js, encoding='utf-8')

# Validar con node si está disponible
validado = False
try:
    r = subprocess.run(['which', 'node'], capture_output=True, text=True)
    if r.returncode == 0:
        r = subprocess.run(['node', '--check', str(tmp_js)],
                          capture_output=True, text=True, timeout=10)
        if r.returncode == 0:
            print('✅ node --check: sintaxis OK')
            validado = True
        else:
            print('❌ node --check: ERROR')
            print(r.stderr)
            sys.exit(1)
    else:
        print('-- node no disponible, usando balance de llaves')
except Exception as e:
    print(f'-- validación con node falló: {e}')

if not validado:
    # Fallback: balance de llaves/paréntesis/corchetes
    b = js.count('{') - js.count('}')
    p = js.count('(') - js.count(')')
    c = js.count('[') - js.count(']')
    if b == 0 and p == 0 and c == 0:
        print(f'✅ Balance OK: llaves={b} parens={p} corch={c}')
    else:
        print(f'❌ DESBALANCE: llaves={b} parens={p} corch={c}')
        sys.exit(1)

# ═══════════════════════════════════════════════════════════
# 6. APLICAR (solo si pasó validación)
# ═══════════════════════════════════════════════════════════
if t == orig:
    print('Sin cambios')
    sys.exit(0)

bak = APOSTAR.with_suffix(APOSTAR.suffix + '.bak_vs2_' + TS)
shutil.copy2(APOSTAR, bak)
print(f'Backup: {bak.name}')
APOSTAR.write_text(t, encoding='utf-8')
print('GUARDADO')
print()
print('FIX_VS_GRUPOS_V2 COMPLETO')
