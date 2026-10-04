from pathlib import Path
import re

p = Path("/home/LottoBooM/templates/base.html")
src = p.read_text(encoding="utf-8")

# 1. Enlace en sidebar (después de sidebarLimitesLink)
if 'id="sidebarRetiroLink"' in src:
    print("1: SKIP (enlace ya existe)")
else:
    patron = re.compile(
        r"(<a href=\"#\" id=\"sidebarLimitesLink\"[^>]*>.*?</a>)",
        re.DOTALL,
    )
    m = patron.search(src)
    if m:
        enlace = '''

        <a href="#" id="sidebarRetiroLink" class="menu-item" style="cursor:pointer;">
            <i class="fas fa-hand-holding-usd"></i>
            <span>Retiro rápido</span>
        </a>'''
        src = src[:m.end()] + enlace + src[m.end():]
        print("1: OK (enlace insertado)")
    else:
        print("1: ERROR (no encontre sidebarLimitesLink)")

# 2. Modal + JS
if "globalRetiroModal" in src:
    print("2: SKIP (modal ya existe)")
else:
    modal = '''

<div id="globalRetiroModal" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.7);z-index:99999;align-items:center;justify-content:center;padding:16px;overflow-y:auto;">
  <div style="background:#fff;border-radius:16px;max-width:560px;width:100%;box-shadow:0 20px 60px rgba(0,0,0,.5);border:2px solid #DC2626;">
    <div style="background:linear-gradient(135deg,#DC2626,#7f1d1d);color:#fff;padding:16px 22px;border-radius:14px 14px 0 0;display:flex;justify-content:space-between;align-items:center;">
      <h5 style="margin:0;font-weight:900;font-size:1rem;"><i class="fas fa-hand-holding-usd" style="margin-right:8px;"></i>Retiro rapido</h5>
      <button type="button" id="globalRetiroClose" style="background:transparent;border:none;color:#fff;font-size:1.5rem;cursor:pointer;line-height:1;padding:0 6px;">&times;</button>
    </div>
    <div style="padding:18px 22px;">
      <div style="margin-bottom:12px;">
        <label style="font-weight:800;font-size:.72rem;color:#7f1d1d;display:block;margin-bottom:6px;text-transform:uppercase;">Cliente</label>
        <select id="globalRetiroCliente" style="width:100%;padding:8px 12px;border-radius:8px;border:1.5px solid #fca5a5;font-weight:700;color:#7f1d1d;background:#fff;font-size:.85rem;font-family:inherit;">
          <option value="">Cargando...</option>
        </select>
      </div>
      <div style="margin-bottom:12px;">
        <label style="font-weight:800;font-size:.72rem;color:#7f1d1d;display:block;margin-bottom:6px;text-transform:uppercase;">Forma de pago</label>
        <select id="globalRetiroFP" style="width:100%;padding:8px 12px;border-radius:8px;border:1.5px solid #fca5a5;font-weight:700;color:#7f1d1d;background:#fff;font-size:.85rem;font-family:inherit;">
          <option value="">-- Selecciona cliente --</option>
        </select>
      </div>
      <div style="margin-bottom:12px;">
        <label style="font-weight:800;font-size:.72rem;color:#7f1d1d;display:block;margin-bottom:6px;text-transform:uppercase;">Motivo</label>
        <select id="globalRetiroMotivo" style="width:100%;padding:8px 12px;border-radius:8px;border:1.5px solid #fca5a5;font-weight:700;color:#7f1d1d;background:#fff;font-size:.85rem;font-family:inherit;">
          <option value="cobro_premios">Cobro de premios</option>
          <option value="donacion_banco">Donacion al banco</option>
          <option value="donacion_comercial">Donacion al comercial</option>
          <option value="donacion_gestor">Donacion al gestor</option>
          <option value="ajuste">Ajuste de fondo</option>
          <option value="retiro_presencial">Retiro presencial</option>
          <option value="otro">Otro</option>
        </select>
      </div>
      <div style="margin-bottom:12px;">
        <label style="font-weight:800;font-size:.72rem;color:#7f1d1d;display:block;margin-bottom:6px;text-transform:uppercase;">Detalle (si Otro)</label>
        <input type="text" id="globalRetiroDetalle" maxlength="200" style="width:100%;padding:8px 12px;border-radius:8px;border:1.5px solid #fca5a5;font-weight:700;color:#7f1d1d;background:#fff;font-size:.85rem;font-family:inherit;">
      </div>
      <div style="margin-bottom:12px;">
        <label style="font-weight:800;font-size:.72rem;color:#7f1d1d;display:block;margin-bottom:6px;text-transform:uppercase;">Monto</label>
        <input type="number" id="globalRetiroMonto" step="0.01" min="0.01" placeholder="0" style="width:100%;padding:10px 14px;border-radius:8px;border:1.5px solid #fca5a5;font-weight:900;color:#7f1d1d;background:#fff;font-size:1.1rem;font-family:inherit;">
      </div>
      <div id="globalRetiroError" style="display:none;background:#fee2e2;border:1.5px solid #dc2626;color:#7f1d1d;padding:8px 12px;border-radius:8px;font-weight:700;font-size:.78rem;"></div>
    </div>
    <div style="padding:14px 22px;border-top:1px solid #fca5a5;background:#f9fafb;border-radius:0 0 14px 14px;display:flex;justify-content:space-between;gap:10px;">
      <button type="button" id="globalRetiroCerrar" style="background:#e5e7eb;color:#374151;border:none;padding:10px 20px;border-radius:10px;font-weight:800;cursor:pointer;font-family:inherit;font-size:.85rem;">Cancelar</button>
      <button type="button" id="globalRetiroConfirmar" style="background:linear-gradient(135deg,#DC2626,#7f1d1d);color:#fff;border:none;padding:10px 26px;border-radius:10px;font-weight:900;cursor:pointer;font-family:inherit;font-size:.9rem;">
        <i class="fas fa-check"></i> Confirmar
      </button>
    </div>
  </div>
</div>

<script>
(function(){
  var modal = document.getElementById('globalRetiroModal');
  if (!modal) return;
  var link = document.getElementById('sidebarRetiroLink');
  var selCli = document.getElementById('globalRetiroCliente');
  var selFP = document.getElementById('globalRetiroFP');
  var selMot = document.getElementById('globalRetiroMotivo');
  var inpDet = document.getElementById('globalRetiroDetalle');
  var inpMonto = document.getElementById('globalRetiroMonto');
  var errBox = document.getElementById('globalRetiroError');
  var btnCerrar = document.getElementById('globalRetiroCerrar');
  var btnClose = document.getElementById('globalRetiroClose');
  var btnConf = document.getElementById('globalRetiroConfirmar');
  var _cache = null;
  var CSRF = (document.querySelector('[name=csrfmiddlewaretoken]')||{}).value || '';

  function _abrir(){
    modal.style.display = 'flex';
    document.body.style.overflow = 'hidden';
    errBox.style.display = 'none';
    inpMonto.value = '';
    inpDet.value = '';
    if (_cache) _render(_cache);
    else _cargar();
  }
  function _cerrar(){
    modal.style.display = 'none';
    document.body.style.overflow = '';
  }
  function _render(clientes){
    selCli.innerHTML = '<option value="">-- Selecciona cliente --</option>' + clientes.map(function(c){
      return '<option value="' + c.id + '">' + c.nombre + '</option>';
    }).join('');
  }
  function _cargar(){
    selCli.innerHTML = '<option value="">Cargando...</option>';
    fetch("{% url 'roles:api_clientes_gestor' %}", {headers:{'Accept':'application/json'}})
      .then(function(r){ return r.json(); })
      .then(function(d){
        if (!d.success){ selCli.innerHTML = '<option value="">Error</option>'; return; }
        _cache = d.clientes || [];
        _render(_cache);
      })
      .catch(function(e){ selCli.innerHTML = '<option value="">Error: ' + e.message + '</option>'; });
  }

  if (link) link.addEventListener('click', function(e){ e.preventDefault(); _abrir(); });
  if (btnClose) btnClose.addEventListener('click', _cerrar);
  if (btnCerrar) btnCerrar.addEventListener('click', _cerrar);
  modal.addEventListener('click', function(e){ if (e.target === modal) _cerrar(); });

  selCli.addEventListener('change', function(){
    var cid = selCli.value;
    if (!cid){ selFP.innerHTML = '<option value="">-- Selecciona cliente --</option>'; return; }
    if (!_cache) return;
    var cli = _cache.find(function(c){ return String(c.id) === String(cid); });
    if (!cli){ selFP.innerHTML = '<option value="">Sin fondos</option>'; return; }
    selFP.innerHTML = '<option value="">-- Selecciona FP --</option>' + cli.fps.map(function(f){
      return '<option value="' + f.id + '">' + f.nombre + ' (Saldo: $' + f.saldo.toFixed(2) + ')</option>';
    }).join('');
  });

  selMot.addEventListener('change', function(){
    inpDet.style.display = (selMot.value === 'otro') ? 'block' : 'none';
  });

  btnConf.addEventListener('click', function(){
    var cid = selCli.value;
    var fpid = selFP.value;
    var monto = parseFloat(inpMonto.value) || 0;
    errBox.style.display = 'none';
    if (!cid){ errBox.textContent = 'Selecciona cliente'; errBox.style.display = 'block'; return; }
    if (!fpid){ errBox.textContent = 'Selecciona FP'; errBox.style.display = 'block'; return; }
    if (monto <= 0){ errBox.textContent = 'Monto mayor a 0'; errBox.style.display = 'block'; return; }

    btnConf.disabled = true;
    btnConf.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Procesando...';

    var fd = new FormData();
    fd.append('usuario_id', cid);
    fd.append('forma_pago_id', fpid);
    fd.append('monto', monto.toFixed(2));
    fd.append('motivo_tipo', selMot.value);
    fd.append('motivo_detalle', inpDet.value.trim());
    fd.append('csrfmiddlewaretoken', CSRF);

    fetch("{% url 'roles:api_retiro_rapido' %}", {method:'POST', body:fd, headers:{'X-Requested-With':'XMLHttpRequest'}})
      .then(function(r){ return r.json(); })
      .then(function(d){
        btnConf.disabled = false;
        btnConf.innerHTML = '<i class="fas fa-check"></i> Confirmar';
        if (!d.success){
          errBox.textContent = d.error || 'Error';
          errBox.style.display = 'block';
          return;
        }
        _cerrar();
        _cache = null;
        alert('Retiro de $' + d.monto.toFixed(2) + ' OK. Nuevo saldo: $' + d.saldo_despues.toFixed(2));
      })
      .catch(function(e){
        btnConf.disabled = false;
        btnConf.innerHTML = '<i class="fas fa-check"></i> Confirmar';
        errBox.textContent = 'Error: ' + e.message;
        errBox.style.display = 'block';
      });
  });
})();
</script>
'''

    idx = src.rfind("</body>")
    if idx > 0:
        src = src[:idx] + modal + src[idx:]
        print("2: OK (modal insertado)")
    else:
        print("2: ERROR (no </body>)")

p.write_text(src, encoding="utf-8")
print("OK: base.html actualizado")
print("sidebarRetiroLink:", src.count("sidebarRetiroLink"))
print("globalRetiroModal:", src.count("globalRetiroModal"))
