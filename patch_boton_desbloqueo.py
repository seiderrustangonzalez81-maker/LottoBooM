from pathlib import Path

p = Path("/home/LottoBooM/jugadas/templates/jugadas/apostar.html")
src = p.read_text(encoding="utf-8")

if "lottort-btn-desbloquear" in src:
    print("SKIP: ya aplicado")
    raise SystemExit(0)

# Modificar el banner para añadir botón
viejo = """      contLock.innerHTML = '<span style="font-size:1.1rem;">🔒</span><div>Límite alcanzado<br><span style="font-weight:600;font-size:.72rem;opacity:.85;">Has usado todo tu saldo disponible. No puedes agregar ni modificar jugadas. Confirma la apuesta o reduce el monto.</span></div>';"""

nuevo = """      contLock.innerHTML = '<span style="font-size:1.1rem;">🔒</span><div style="flex:1;">Límite alcanzado<br><span style="font-weight:600;font-size:.72rem;opacity:.85;">Has usado todo tu saldo disponible. Confirma o reduce un monto.</span></div><button type="button" id="lottort-btn-desbloquear" style="background:#fff;border:1.5px solid #d97706;color:#78350f;padding:6px 12px;border-radius:8px;font-weight:800;font-size:.72rem;cursor:pointer;white-space:nowrap;font-family:inherit;">✏️ Editar / Reducir</button>';
      setTimeout(function(){
        var btn = document.getElementById('lottort-btn-desbloquear');
        if (btn && !btn.dataset.bound){
          btn.dataset.bound = '1';
          btn.addEventListener('click', function(){
            // Desbloquear temporalmente
            document.querySelectorAll('.lottort-cliente-locked').forEach(function(t){
              t.classList.remove('lottort-cliente-locked');
              t.style.pointerEvents = '';
              t.style.opacity = '';
              t.style.filter = '';
            });
            document.querySelectorAll('.lottort-lock-overlay').forEach(function(o){ o.remove(); });
            document.querySelectorAll('.add-row').forEach(function(b){
              b.disabled = false;
              b.style.opacity = '';
              b.style.cursor = '';
            });
            var msg = document.getElementById('lottort-lock-msg');
            if (msg) msg.remove();
            // Avisar al usuario
            if (typeof toast === 'function') {
              toast('✏️ Edita los montos. Si vuelves a superar el límite, se bloqueará de nuevo.', 'warning');
            }
          });
        }
      }, 50);"""

if viejo not in src:
    print("ERROR: no encontre el banner del bloqueo")
    raise SystemExit(1)

src = src.replace(viejo, nuevo, 1)
p.write_text(src, encoding="utf-8")
print("OK: boton de desbloqueo agregado")

assert "lottort-btn-desbloquear" in src
print("OK verificacion")
