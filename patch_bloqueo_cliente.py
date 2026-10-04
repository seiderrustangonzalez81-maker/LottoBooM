from pathlib import Path

p = Path("/home/LottoBooM/jugadas/templates/jugadas/apostar.html")
src = p.read_text(encoding="utf-8")

if "lottort-cliente-locked" in src:
    print("SKIP: ya aplicado")
    raise SystemExit(0)

viejo = """  if (ok){
    if (ES_CLIENTE){
      // Cliente: exige FP seleccionada + saldo suficiente
      ok = !!fpSel && total <= disponibleTotal;
    } else {"""

nuevo = """  // ═══════════════════════════════════════════════════════════════
  // 🔒 Bloqueo automático cuando el cliente agota su fondo
  // ═══════════════════════════════════════════════════════════════
  const esClienteAgotado = ES_CLIENTE && !!fpSel && total > 0 && total >= disponibleTotal;

  document.querySelectorAll('.tabla-ap').forEach(function(t){
    t.classList.toggle('lottort-cliente-locked', esClienteAgotado);
    t.style.pointerEvents = esClienteAgotado ? 'none' : '';
    t.style.opacity = esClienteAgotado ? '0.55' : '';
    t.style.filter = esClienteAgotado ? 'grayscale(0.5)' : '';
    t.style.position = 'relative';
  });

  document.querySelectorAll('.add-row').forEach(function(b){
    b.disabled = esClienteAgotado;
    b.style.opacity = esClienteAgotado ? '0.4' : '';
    b.style.cursor = esClienteAgotado ? 'not-allowed' : '';
  });

  // Overlay visual sobre cada tabla
  document.querySelectorAll('.tabla-panel').forEach(function(panel){
    var existente = panel.querySelector('.lottort-lock-overlay');
    if (esClienteAgotado){
      if (!existente){
        var ov = document.createElement('div');
        ov.className = 'lottort-lock-overlay';
        ov.style.cssText = 'position:absolute;inset:0;display:flex;align-items:center;justify-content:center;pointer-events:none;z-index:5;';
        ov.innerHTML = '<div style="background:rgba(220,38,38,.92);color:#fff;padding:14px 26px;border-radius:12px;font-weight:900;font-size:1rem;letter-spacing:1px;transform:rotate(-8deg);box-shadow:0 8px 32px rgba(0,0,0,.35);text-shadow:0 1px 2px rgba(0,0,0,.4);">🔒 LÍMITE ALCANZADO</div>';
        panel.style.position = 'relative';
        panel.appendChild(ov);
      }
    } else {
      if (existente) existente.remove();
    }
  });

  // Banner amarillo explicativo
  var contLock = document.getElementById('lottort-lock-msg');
  if (esClienteAgotado){
    if (!contLock){
      contLock = document.createElement('div');
      contLock.id = 'lottort-lock-msg';
      contLock.style.cssText = 'background:linear-gradient(145deg,#fef3c7,#fde68a);border:1.5px solid #f59e0b;color:#78350f;padding:.75rem 1rem;border-radius:10px;margin-bottom:10px;font-weight:800;font-size:.82rem;display:flex;gap:8px;align-items:flex-start;box-shadow:3px 3px 0 #d97706;';
      contLock.innerHTML = '<span style="font-size:1.1rem;">🔒</span><div>Límite alcanzado<br><span style="font-weight:600;font-size:.72rem;opacity:.85;">Has usado todo tu saldo disponible. No puedes agregar ni modificar jugadas. Confirma la apuesta o reduce el monto.</span></div>';
      var saldoCont = document.getElementById('saldoMsgContainer');
      if (saldoCont && saldoCont.parentNode){
        saldoCont.parentNode.insertBefore(contLock, saldoCont);
      }
    }
  } else {
    if (contLock) contLock.remove();
  }

  if (ok){
    if (ES_CLIENTE){
      // Cliente: exige FP seleccionada + saldo suficiente
      ok = !!fpSel && total <= disponibleTotal;
    } else {"""

if viejo not in src:
    print("ERROR: no encontre el bloque exacto de validacion")
    raise SystemExit(1)

src = src.replace(viejo, nuevo, 1)
p.write_text(src, encoding="utf-8")
print("OK: bloqueo cliente aplicado")

# Verificacion
assert "lottort-cliente-locked" in src
assert "LÍMITE ALCANZADO" in src
assert "esClienteAgotado" in src
print("OK verificacion")
