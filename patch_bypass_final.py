from pathlib import Path

p = Path("/home/LottoBooM/jugadas/templates/jugadas/apostar.html")
src = p.read_text(encoding="utf-8")

cambios = []

# ═══════════════════════════════════════════════════════════════
# FIX 1: Bypass en la validación ES_CLIENTE
# ═══════════════════════════════════════════════════════════════
viejo1 = """      // Cliente: exige FP seleccionada + saldo suficiente
      ok = !!fpSel && total <= disponibleTotal;"""

nuevo1 = """      // Cliente: exige FP seleccionada + saldo suficiente
      // ES_SOLO_EDITAR: en modo editar no requiere validación de saldo
      ok = ES_SOLO_EDITAR || (!!fpSel && total <= disponibleTotal);"""

if "ok = ES_SOLO_EDITAR || (!!fpSel && total <= disponibleTotal);" in src:
    cambios.append("FIX 1: SKIP (ya aplicado)")
elif viejo1 in src:
    src = src.replace(viejo1, nuevo1, 1)
    cambios.append("FIX 1: OK (bypass ES_CLIENTE)")
else:
    # Variante sin comentario
    viejo1b = "      ok = !!fpSel && total <= disponibleTotal;"
    if viejo1b in src:
        src = src.replace(viejo1b, "      ok = ES_SOLO_EDITAR || (!!fpSel && total <= disponibleTotal);", 1)
        cambios.append("FIX 1: OK (variante sin comentario)")
    else:
        cambios.append("FIX 1: ERROR (no encontre 'ok = !!fpSel && total <= disponibleTotal;')")

# ═══════════════════════════════════════════════════════════════
# FIX 2: No bloquear con esClienteAgotado en modo editar
# ═══════════════════════════════════════════════════════════════
viejo2 = "const esClienteAgotado = ES_CLIENTE && !!fpSel && total > 0 && total > disponibleTotal;"
nuevo2 = "const esClienteAgotado = !ES_SOLO_EDITAR && ES_CLIENTE && !!fpSel && total > 0 && total > disponibleTotal;"

if "const esClienteAgotado = !ES_SOLO_EDITAR" in src:
    cambios.append("FIX 2: SKIP (ya aplicado)")
elif viejo2 in src:
    src = src.replace(viejo2, nuevo2, 1)
    cambios.append("FIX 2: OK (no bloquea en modo editar)")
else:
    cambios.append("FIX 2: ERROR (no encontre esClienteAgotado)")

# ═══════════════════════════════════════════════════════════════
# FIX 3: Ocultar el mensaje "Saldo insuficiente" en modo editar
# ═══════════════════════════════════════════════════════════════
viejo3 = """    if (deficit > 0){
      // FASE1_POSTPAGO_V1_FRONTEND: gestor verá postpago (deuda), cliente verá error
      if (!ES_CLIENTE && (chipEspecial === 'postpago' || (!chipEspecial && fpSel))){"""

nuevo3 = """    if (ES_SOLO_EDITAR){
      contSaldo.innerHTML = '<div class="saldo-info"><span class="icon">✏️</span><div>Modo edición<span class="detalle">No se cobrará nuevamente. El total ya fue descontado en la boleta original.</span></div></div>';
    } else if (deficit > 0){
      // FASE1_POSTPAGO_V1_FRONTEND: gestor verá postpago (deuda), cliente verá error
      if (!ES_CLIENTE && (chipEspecial === 'postpago' || (!chipEspecial && fpSel))){"""

if "No se cobrará nuevamente. El total ya fue descontado" in src:
    cambios.append("FIX 3: SKIP (ya aplicado)")
elif viejo3 in src:
    src = src.replace(viejo3, nuevo3, 1)
    cambios.append("FIX 3: OK (mensaje modo edición)")
else:
    cambios.append("FIX 3: ERROR (no encontre bloque de deficit)")

p.write_text(src, encoding="utf-8")

# Reporte
print("═══ REPORTE ═══")
for c in cambios:
    print(f"  {c}")

# Verificar sintaxis básica
import ast
print(f"\nES_SOLO_EDITAR: {src.count('ES_SOLO_EDITAR')}")
print(f"Modo edición: {src.count('Modo edición')}")
print(f"ok = ES_SOLO_EDITAR: {src.count('ok = ES_SOLO_EDITAR')}")
print(f"!ES_SOLO_EDITAR: {src.count('!ES_SOLO_EDITAR')}")
