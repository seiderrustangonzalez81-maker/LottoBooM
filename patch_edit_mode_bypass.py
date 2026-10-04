from pathlib import Path

# ═══════════════════════════════════════════════════════════════
# PATCH 1: Backend — agregar cliente_nombre
# ═══════════════════════════════════════════════════════════════
p1 = Path("/home/LottoBooM/jugadas/views.py")
src1 = p1.read_text(encoding="utf-8")

viejo = "                    'cliente_id': b.usuario_id,"
nuevo = "                    'cliente_id': b.usuario_id,\n                    'cliente_nombre': (b.usuario.username if b.usuario else ''),"

if "'cliente_nombre':" in src1:
    print("PATCH 1: SKIP (ya existe)")
elif viejo in src1:
    src1 = src1.replace(viejo, nuevo, 1)
    p1.write_text(src1, encoding="utf-8")
    print("PATCH 1: OK (cliente_nombre añadido)")
else:
    print("PATCH 1: ERROR (no encontre cliente_id)")

# ═══════════════════════════════════════════════════════════════
# PATCH 2: Frontend — ES_SOLO_EDITAR + bypass
# ═══════════════════════════════════════════════════════════════
p2 = Path("/home/LottoBooM/jugadas/templates/jugadas/apostar.html")
src2 = p2.read_text(encoding="utf-8")

# ── 2.1: Definir ES_SOLO_EDITAR ──
viejo_21 = 'const ES_CLIENTE = {{ es_cliente|yesno:"true,false" }};'
nuevo_21 = ('const ES_CLIENTE = {{ es_cliente|yesno:"true,false" }};\n'
            "const ES_SOLO_EDITAR = (new URLSearchParams(window.location.search)).get('modo_editar') === '1';")

if "const ES_SOLO_EDITAR" in src2:
    print("PATCH 2.1: SKIP")
elif viejo_21 in src2:
    src2 = src2.replace(viejo_21, nuevo_21, 1)
    print("PATCH 2.1: OK")
else:
    print("PATCH 2.1: ERROR")

# ── 2.2: Bypass de saldo en recalcGlobal ──
viejo_22 = """  const disponibleTotal = saldoFP + bonoDisp + postpagoPendiente;
  let ok = cliente && ordenSorteos.length > 0 && items.length > 0;
  if (ok){
    if (ES_CLIENTE){"""

nuevo_22 = """  const disponibleTotal = saldoFP + bonoDisp + postpagoPendiente;
  let ok = cliente && ordenSorteos.length > 0 && items.length > 0;
  // ES_SOLO_EDITAR: en modo editar no se cobra
  if (ok && ES_SOLO_EDITAR){
    // no requiere FP ni saldo
  } else if (ok){
    if (ES_CLIENTE){"""

if "if (ok && ES_SOLO_EDITAR){" in src2:
    print("PATCH 2.2: SKIP")
elif viejo_22 in src2:
    src2 = src2.replace(viejo_22, nuevo_22, 1)
    print("PATCH 2.2: OK")
else:
    print("PATCH 2.2: ERROR")

# ── 2.3: Mensaje distinto en edit mode ──
viejo_23 = """  const contSaldo = $('saldoMsgContainer');
  if (contSaldo){
    if (deficit > 0){"""

nuevo_23 = """  const contSaldo = $('saldoMsgContainer');
  if (contSaldo){
    if (ES_SOLO_EDITAR){
      contSaldo.innerHTML = '<div class="saldo-info"><span class="icon">✏️</span><div>Modo edición<span class="detalle">No se cobrará nuevamente. El total ya fue descontado en la boleta original.</span></div></div>';
    } else if (deficit > 0){"""

if "Modo edición<span" in src2:
    print("PATCH 2.3: SKIP")
elif viejo_23 in src2:
    src2 = src2.replace(viejo_23, nuevo_23, 1)
    print("PATCH 2.3: OK")
else:
    print("PATCH 2.3: ERROR")

# ── 2.4: Cliente dinámico ──
viejo_24 = """  var selCli = document.getElementById('selCliente');
  if (!selCli){ console.error('[apostar] No existe #selCliente'); return; }
  selCli.value = String(data.cliente_id);
  selCli.dispatchEvent(new Event('change'));
  console.log('[apostar] Cliente seleccionado:', selCli.value);"""

nuevo_24 = """  var selCli = document.getElementById('selCliente');
  if (!selCli){ console.error('[apostar] No existe #selCliente'); return; }
  var _existeCli = false;
  for (var _i = 0; _i < selCli.options.length; _i++){
    if (String(selCli.options[_i].value) === String(data.cliente_id)){
      _existeCli = true; break;
    }
  }
  if (!_existeCli){
    console.log('[apostar] Cliente ' + data.cliente_id + ' no en dropdown, añadiendo...');
    var _opt = document.createElement('option');
    _opt.value = String(data.cliente_id);
    _opt.textContent = (data.cliente_nombre || 'Cliente') + ' (edit)';
    _opt.dataset.nombre = data.cliente_nombre || 'Cliente';
    _opt.dataset.telefono = '';
    _opt.dataset.saldo = '0';
    _opt.dataset.bonos = '0';
    _opt.dataset.rol = 'cliente';
    selCli.appendChild(_opt);
  }
  selCli.value = String(data.cliente_id);
  selCli.dispatchEvent(new Event('change'));
  console.log('[apostar] Cliente seleccionado:', selCli.value);"""

if "no en dropdown, añadiendo" in src2:
    print("PATCH 2.4: SKIP")
elif viejo_24 in src2:
    src2 = src2.replace(viejo_24, nuevo_24, 1)
    print("PATCH 2.4: OK")
else:
    print("PATCH 2.4: ERROR")

# ── 2.5: FP forzada en modo editar ──
viejo_25 = """      if (!encontrado){
        console.warn('[apostar] No encontre chip FP id=' + data.forma_pago_id);
        console.log('[apostar] Chips disponibles:', Array.from(chips).map(c => c.dataset.id + '=' + c.dataset.n));
      }"""

nuevo_25 = """      if (!encontrado){
        if (ES_SOLO_EDITAR){
          fpSel = String(data.forma_pago_id);
          _estadoDebug.fpOk = true;
          console.log('[apostar] Modo editar: FP forzada =', fpSel);
        } else {
          console.warn('[apostar] No encontre chip FP id=' + data.forma_pago_id);
        }
      }"""

if "Modo editar: FP forzada" in src2:
    print("PATCH 2.5: SKIP")
elif viejo_25 in src2:
    src2 = src2.replace(viejo_25, nuevo_25, 1)
    print("PATCH 2.5: OK")
else:
    print("PATCH 2.5: ERROR")

p2.write_text(src2, encoding="utf-8")

# Verificar
import ast
try:
    ast.parse(src1)
    print("\nOK: Python sintaxis correcta")
except SyntaxError as e:
    print(f"\nERROR Python: {e}")

print(f"\nES_SOLO_EDITAR: {src2.count('ES_SOLO_EDITAR')}")
print(f"cliente_nombre: {src1.count('cliente_nombre')}")
