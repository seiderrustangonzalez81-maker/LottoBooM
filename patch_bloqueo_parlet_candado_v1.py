from pathlib import Path

p = Path("/home/LottoBooM/jugadas/templates/jugadas/apostar.html")
src = p.read_text(encoding="utf-8")

if "BLOQUEO_PARLET_CANDADO_V1" in src:
    print("SKIP: ya aplicado")
    raise SystemExit(0)

# ═══════════════════════════════════════════════════════════════
# 1) Insertar helper justo antes de renderMiniResumenSorteo
# ═══════════════════════════════════════════════════════════════
ancla_1 = "/* ═══════════════════════════════════════════════════════════════\n   MINI RESUMEN POR SORTEO"
nuevo_1 = r"""/* ═══════════════════════════════════════════════════════════════
   BLOQUEO_PARLET_CANDADO_V1
   Con 0 o 1 números no hay parlets posibles → ambos inputs
   (parlet y candado) quedan disabled hasta que existan >= 2 números.
   ═══════════════════════════════════════════════════════════════ */
function actualizarBloqueoParletCandado(cont, st, row, i, def){
  if (!cont || !st || !row || !def) return;
  var tieneParlet  = st.forms.includes('parlet');
  var tieneCandado = st.forms.includes('candado');
  if (!tieneParlet && !tieneCandado) return;

  var inpParlet = cont.querySelector('input[data-row="' + i + '"][data-form="parlet"]');
  var inpCand   = cont.querySelector('input[data-row="' + i + '"][data-form="candado"]');
  if (!inpParlet && !inpCand) return;

  var nPlays = 0;
  try { nPlays = contarParletsDeFila(row, def.numDigits, def.maxNums); } catch(_){}
  var sinNumeros = (nPlays < 1);

  function aplicar(inp, formKey){
    if (!inp) return;
    if (sinNumeros){
      inp.disabled = true;
      inp.readOnly = true;
      inp.value = '';
      inp.classList.add('monto-sin-numeros');
      inp.classList.remove('monto-blocked');
      inp.setAttribute('placeholder', '—');
      inp.setAttribute('title', 'Añade al menos 2 números para activar');
      row.montos[formKey] = '';
    } else {
      inp.disabled = false;
      inp.classList.remove('monto-sin-numeros');
      inp.setAttribute('placeholder', '0');
      // readOnly / monto-blocked los maneja la lógica de vínculo existente
      if (!inp.classList.contains('monto-blocked')){
        inp.readOnly = false;
        inp.removeAttribute('title');
      }
    }
  }

  aplicar(inpParlet, 'parlet');
  aplicar(inpCand,   'candado');
}

/* ═══════════════════════════════════════════════════════════════
   MINI RESUMEN POR SORTEO"""

if ancla_1 not in src:
    print("ERROR: no encontré el ancla 1 (comentario MINI RESUMEN)")
    raise SystemExit(1)
src = src.replace(ancla_1, nuevo_1, 1)
print("OK 1: helper actualizarBloqueoParletCandado insertado")


# ═══════════════════════════════════════════════════════════════
# 2) Hook inicial: al final de bindTablaEventsSorteo
# ═══════════════════════════════════════════════════════════════
ancla_2 = """  // Evaluación inicial (tras el render)
  setTimeout(function(){
    try { evaluarExcepcionesSorteo(sid, cont); }
    catch(e){ console.warn('[EXC]', e); }
  }, 50);
  // ═══ FIN EXCEPCIONES_POR_FILA_V1 ═══
}"""

nuevo_2 = """  // Evaluación inicial (tras el render)
  setTimeout(function(){
    try { evaluarExcepcionesSorteo(sid, cont); }
    catch(e){ console.warn('[EXC]', e); }
  }, 50);
  // ═══ FIN EXCEPCIONES_POR_FILA_V1 ═══

  // ═══ BLOQUEO_PARLET_CANDADO_V1: estado inicial por fila ═══
  try {
    st.rows.forEach(function(r, idx){
      actualizarBloqueoParletCandado(cont, st, r, idx, def);
    });
  } catch(e){ console.warn('[BLOQUEO_PC]', e); }
  // ═══ FIN BLOQUEO_PARLET_CANDADO_V1 ═══
}"""

if ancla_2 not in src:
    print("ERROR: no encontré el ancla 2 (cierre bindTablaEventsSorteo)")
    raise SystemExit(1)
src = src.replace(ancla_2, nuevo_2, 1)
print("OK 2: hook inicial en bindTablaEventsSorteo")


# ═══════════════════════════════════════════════════════════════
# 3) Hook en handler num-inp (tras recalcularVinculoParletCandado)
# ═══════════════════════════════════════════════════════════════
ancla_3 = """      // FIX_CANDADO_PARLET_V1: recalcular vínculo tras editar números
      try { recalcularVinculoParletCandado(cont, st, st.rows[i], i, def); } catch(_){}"""

nuevo_3 = """      // FIX_CANDADO_PARLET_V1: recalcular vínculo tras editar números
      try { recalcularVinculoParletCandado(cont, st, st.rows[i], i, def); } catch(_){}
      // BLOQUEO_PARLET_CANDADO_V1: reevaluar si hay <2 números
      try { actualizarBloqueoParletCandado(cont, st, st.rows[i], i, def); } catch(_){}"""

if ancla_3 not in src:
    print("ERROR: no encontré el ancla 3 (handler num-inp)")
    raise SystemExit(1)
src = src.replace(ancla_3, nuevo_3, 1)
print("OK 3: hook en handler num-inp")


# ═══════════════════════════════════════════════════════════════
# 4) CSS para el estado disabled
# ═══════════════════════════════════════════════════════════════
if "monto-sin-numeros" not in src:
    css = """
  /* BLOQUEO_PARLET_CANDADO_V1 */
  input.monto.monto-sin-numeros{
    background: #f3f4f6 !important;
    color: #9ca3af !important;
    border-color: #e5e7eb !important;
    cursor: not-allowed !important;
    opacity: 0.7;
  }
  input.monto.monto-sin-numeros::placeholder{
    color: #d1d5db;
    font-weight: 700;
  }
"""
    idx = src.find("</style>")
    if idx == -1:
        print("WARN: no encontré </style>, CSS no insertado")
    else:
        src = src[:idx] + css + src[idx:]
        print("OK 4: CSS insertado")
else:
    print("SKIP 4: CSS ya existe")

p.write_text(src, encoding="utf-8")

print()
print("═══ Resumen ═══")
print("actualizarBloqueoParletCandado:", src.count("actualizarBloqueoParletCandado"))
print("BLOQUEO_PARLET_CANDADO_V1     :", src.count("BLOQUEO_PARLET_CANDADO_V1"))
print("monto-sin-numeros             :", src.count("monto-sin-numeros"))
