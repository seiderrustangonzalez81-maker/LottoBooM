from pathlib import Path

p = Path("/home/LottoBooM/jugadas/templates/jugadas/apostar.html")
src = p.read_text(encoding="utf-8")

if "_esperarChipFPSaldo" in src:
    print("SKIP: ya aplicado")
    raise SystemExit(0)

# Insertar el polling del chip después de cargarFormasPago
viejo = """  // ═══ 4. Cargar formas de pago (para mostrar chips) ═══
  try {
    if (typeof cargarFormasPago === 'function') {
      cargarFormasPago();
    }
  } catch(e){ console.warn('[apostar] cargarFormasPago error:', e); }"""

nuevo = """  // ═══ 4. Cargar formas de pago (para mostrar chips) ═══
  try {
    if (typeof cargarFormasPago === 'function') {
      cargarFormasPago();
    }
  } catch(e){ console.warn('[apostar] cargarFormasPago error:', e); }

  // ═══ 4b. Clickear chip correcto para setear saldoFP real ═══
  function _esperarChipFPSaldo(intento){
    if (intento > 30){  // max 15s
      console.warn('[apostar] Timeout esperando chips FP, saldoFP quedara en 0');
      if (typeof recalcGlobal === 'function') recalcGlobal();
      return;
    }
    var chips = document.querySelectorAll('.fp-chip');
    if (!chips.length){
      setTimeout(function(){ _esperarChipFPSaldo(intento + 1); }, 500);
      return;
    }
    var encontrado = false;
    chips.forEach(function(ch){
      if (String(ch.dataset.id) === String(data.forma_pago_id)){
        var wasActive = ch.classList.contains('active');
        ch.click();
        encontrado = true;
        console.log('[apostar] Chip FP clickeado:', ch.dataset.n, '| saldo=', ch.dataset.s, '| yaActivo=', wasActive);
      }
    });
    if (!encontrado){
      console.warn('[apostar] Chip FP id=' + data.forma_pago_id + ' no encontrado entre', chips.length, 'chips');
    } else {
      // Recalcular para actualizar el mensaje
      if (typeof recalcGlobal === 'function') recalcGlobal();
    }
  }
  setTimeout(function(){ _esperarChipFPSaldo(0); }, 500);"""

if viejo not in src:
    print("ERROR: no encontre el bloque de cargarFormasPago")
    raise SystemExit(1)

src = src.replace(viejo, nuevo, 1)
p.write_text(src, encoding="utf-8")
print("OK: polling de chip insertado")
print(f"_esperarChipFPSaldo: {src.count('_esperarChipFPSaldo')}")
