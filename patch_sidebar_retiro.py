from pathlib import Path
import ast, re

# ═══════════════════════════════════════════════════════════════
# 1. Backend: endpoint que devuelve clientes + FPs del gestor
# ═══════════════════════════════════════════════════════════════
p1 = Path("/home/LottoBooM/roles/views.py")
src1 = p1.read_text(encoding="utf-8")

if "def api_clientes_gestor" in src1:
    print("1: SKIP (endpoint ya existe)")
else:
    endpoint = '''

# ═══════════════════════════════════════════════════════════════
# API · Clientes del gestor con sus formas de pago (para retiro rápido)
# ═══════════════════════════════════════════════════════════════
@login_required
def api_clientes_gestor(request):
    """Devuelve clientes del gestor con sus FPs y saldo."""
    from django.db.models import Sum as _Sum

    user = request.user
    es_superadmin = user.is_superuser or user.roles.filter(tipo='superadmin', activo=True).exists()
    es_banco = user.roles.filter(tipo='banco', activo=True).exists()
    es_comercial = user.roles.filter(tipo='comercial', activo=True).exists()

    if not (es_superadmin or es_banco or es_comercial):
        return JsonResponse({'success': False, 'error': 'Sin permisos'}, status=403)

    # Clientes: los que tienen fondo asignado por el user (o por sus comerciales si es banco)
    if es_superadmin:
        qs_fondos = Fondo.objects.filter(activo=True)
    elif es_banco:
        comerciales_ids = list(Subordinacion.objects.filter(jefe=user, activo=True).values_list('subordinado_id', flat=True))
        qs_fondos = Fondo.objects.filter(
            Q(asignado_por=user) | Q(asignado_por__in=comerciales_ids),
            activo=True
        )
    else:
        qs_fondos = Fondo.objects.filter(asignado_por=user, activo=True)

    # Agrupar por cliente
    clientes_map = {}
    for f in qs_fondos.select_related('usuario', 'forma_pago').order_by('usuario__username'):
        if not f.forma_pago:
            continue
        cid = f.usuario_id
        if cid not in clientes_map:
            clientes_map[cid] = {
                'id': cid,
                'nombre': f.usuario.username,
                'fps': []
            }
        clientes_map[cid]['fps'].append({
            'id': f.forma_pago_id,
            'nombre': f.forma_pago.nombre,
            'saldo': float(f.monto or 0),
        })

    clientes = list(clientes_map.values())

    return JsonResponse({
        'success': True,
        'clientes': clientes,
    })

'''
    src1 += endpoint
    p1.write_text(src1, encoding="utf-8")
    print("1: OK (endpoint api_clientes_gestor)")

try:
    ast.parse(src1)
    print("OK: sintaxis views.py")
except SyntaxError as e:
    print("ERROR views:", e)
    raise SystemExit(1)

# URL
pu = Path("/home/LottoBooM/roles/urls.py")
srcurls = pu.read_text(encoding="utf-8")
if "api_clientes_gestor" not in srcurls:
    m = re.search(r"urlpatterns\s*=\s*\[", srcurls)
    srcurls = srcurls[:m.end()] + "\n    path('api/clientes-gestor/', views.api_clientes_gestor, name='api_clientes_gestor')," + srcurls[m.end():]
    pu.write_text(srcurls, encoding="utf-8")
    print("1: OK (URL api_clientes_gestor)")


# ═══════════════════════════════════════════════════════════════
# 2. base.html — enlace + modal de retiro rápido
# ═══════════════════════════════════════════════════════════════
p2 = Path("/home/LottoBooM/templates/base.html")
src2 = p2.read_text(encoding="utf-8")

# Enlace en sidebar
if 'id="sidebarRetiroLink"' in src2:
    print("2a: SKIP (enlace ya existe)")
else:
    viejo = '''<a href="{% url 'roles:recarga_directa' %}" class="menu-item">'''
    m = re.search(
        r"(<a href=\"\{% url 'roles:recarga_directa' %\}\" class=\"menu-item\">.*?</a>\s*)"
        r"(<a href=\"#\" id=\"sidebarLimitesLink\"[^>]*>.*?</a>)",
        src2, re.DOTALL,
    )
    if m:
        # Insertar el retiro DESPUÉS de límites
        enlace_retiro = '''

        <a href="#" id="sidebarRetiroLink" class="menu-item" style="cursor:pointer;">
            <i class="fas fa-hand-holding-usd"></i>
            <span>Retiro rápido</span>
        </a>'''
        src2 = src2[:m.end(2)] + enlace_retiro + src2[m.end(2):]
        p2.write_text(src2, encoding="utf-8")
        print("2a: OK (enlace retiro insertado)")
    else:
        print("2a: ERROR (no encontre bloque recarga+limites)")

# Modal + JS
if "globalRetiroModal" in src2:
    print("2b: SKIP (modal retiro ya existe)")
else:
    modal_retiro = '''

{# ═══════ MODAL GLOBAL DE RETIRO RÁPIDO ═══════ #}
<div id="globalRetiroModal" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.7);z-index:99999;align-items:center;justify-content:center;padding:16px;overflow-y:auto;">
  <div style="background:#fff;border-radius:16px;max-width:560px;width:100%;box-shadow:0 20px 60px rgba(0,0,0,.5);border:2px solid #DC2626;">
    <div style="background:linear-gradient(135deg,#DC2626,#7f1d1d);color:#fff;padding:16px 22px;border-radius:14px 14px 0 0;display:flex;justify-content:space-between;align-items:center;">
      <h5 style="margin:0;font-weight:900;font-size:1rem;">
        <i class="fas fa-hand-holding-usd" style="margin-right:8px;"></i>Retiro rápido
      </h5>
      <button type="button" id="globalRetiroClose" style="background:transparent;border:none;color:#fff;font-size:1.5rem;cursor:pointer;line-height:1;padding:0 6px;">&times;</button>
    </div>
    <div style="padding:18px 22px;">
      <div style="margin-bottom:12px;">
        <label style="font-weight:800;font-size:.72rem;color:#7f1d1d;display:block;margin-bottom:6px;text-transform:uppercase;letter-spacing:.5px;">Cliente</label>
        <select id="globalRetiroCliente" style="width:100%;padding:8px 12px;border-radius:8px;border:1.5px solid #fca5a5;font-weight:700;color:#7f1d1d;background:#fff;font-size:.85rem;font-family:inherit;">
          <option value="">Cargando...</option>
        </select>
      </div>
      <div style="margin-bottom:12px;">
        <label style="font-weight:800;font-size:.72rem;color:#7f1d1d;display:block;margin-bottom:6px;text-transform:uppercase;letter-spacing:.5px;">Forma de pago</label>
        <select id="globalRetiroFP" style="width:100%;padding:8px 12px;border-radius:8px;border:1.5px solid #fca5a5;font-weight:700;color:#7f1d1d;background:#fff;font-size:.85rem;font-family:inherit;">
          <option value="">-- Selecciona cliente primero --</option>
        </select>
      </div>
      <div style="margin-bottom:12px;">
        <label style="font-weight:800;font-size:.72rem;color:#7f1d1d;display:block;margin-bottom:6px;text-transform:uppercase;letter-spacing:.5px;">Motivo</label>
        <select id="globalRetiroMotivo" style="width:100%;padding:8px 12px;border-radius:8px;border:1.5px solid #fca5a5;font-weight:700;color:#7f1d1d;background:#fff;font-size:.85rem;font-family:inherit;">
          <option value="cobro_premios">Cobro de premios</option>
          <option value="donacion_banco">Donacion al banco</option>
          <option value="donacion_comercial">Donacion al comercial</option>
          <option value="donacion_gestor">Donacion al gestor</option>
          <option value="ajuste">Ajuste de fondo</option>
          <option value="retiro_presencial">Retiro presencial</option>
          <option value="otro">Otro (especificar)</option>
        </select>
      </div>
      <div style="margin-bottom:12px;">
        <label style="font-weight:800;font-size:.72rem;color:#7f1d1d;display:block;margin-bottom:6px;text-transform:uppercase;letter-spacing:.5px;">Detalle (si es "Otro")</label>
        <input type="text" id="globalRetiroDetalle" maxlength="200" placeholder="Detalle del retiro" style="width:100%;padding:8px 12px;border-radius:8px;border:1.5px solid #fca5a5;font-weight:700;color:#7f1d1d;background:#fff;font-size:.85rem;font-family:inherit;">
      </div>
      <div style="margin-bottom:12px;">
        <label style="font-weight:800;font-size:.72rem;color:#7f1d1d;display:block;margin-bottom:6px;text-transform:uppercase;letter-spacing:.5px;">Monto a descontar</label>
        <input type="number" id="globalRetiroMonto" step="0.01" min="0.01" placeholder="0" style="width:100%;padding:10px 14px;border-radius:8px;border:1.5px solid #fca5a5;font-weight:900;color:#7f1d1d;background:#fff;font-size:1.1rem;font-family:inherit;">
      </div>
      <div id="globalRetiroError" style="display:none;background:#fee2e2;border:1.5px solid #dc2626;color:#7f1d1d;padding:8px 12px;border-radius:8px;font-weight:700;font-size:.78rem;"></div>
    </div>
    <div style="padding:14px 22px;border-top:1px solid #fca5a5;background:#f9fafb;border-radius:0 0 14px 14px;display:flex;justify-content:space-between;gap:10px;">
      <button type="button" id="globalRetiroCerrar" style="background:#e5e7eb;color:#374151;border:none;padding:10px 20px;border-radius:10px;font-weight:800;cursor:pointer;font-family:inherit;font-size:.85rem;">Cancelar</button>
      <button type="button" id="globalRetiroConfirmar" style="background:linear-gradient(135deg,#DC2626,#7f1d1d);color:#fff;border:none;padding:10px 26px;border-radius:10px;font-weight:900;cursor:pointer;font-family:inherit;font-size:.9rem;">
        <i class="fas fa-check"></i> Confirmar retiro
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
  var selMotivo = document.getElementById('globalRetiroMotivo');
  var inpDetalle = document.getElementById('globalRetiroDetalle');
  var inpMonto = document.getElementById('globalRetiroMonto');
  var errBox = document.getElementById('globalRetiroError');
  var btnClose = document.getElementById('globalRetiroClose');
  var btnCerrar = document.getElementById('globalRetiroCerrar');
  var btnConfirmar = document.getElementById('globalRetiroConfirmar');
  var _clientesCache = null;
  var CSRF = (document.querySelector('[name=csrfmiddlewaretoken]')||{}).value || '';

  function _abrir(){
    modal.style.display = 'flex';
    document.body.style.overflow = 'hidden';
    errBox.style.display = 'none';
    inpMonto.value = '';
    inpDetalle.value = '';
    if (!_clientesCache){ _cargarClientes(); }
    else { _renderClientes(_clientesCache); }
  }
  function _cerrar(){
    modal.style.display = 'none';
    document.body.style.overflow = '';
  }

  if (link) link.addEventListener('click', function(e){ e.preventDefault(); _abrir(); });
  if (btnClose) btnClose.addEventListener('click', _cerrar);
  if (btnCerrar) btnCerrar.addEventListener('click', _cerrar);
  modal.addEventListener('click', function(e){ if (e.target === modal) _cerrar(); });

  function _renderClientes(clientes){
    selCli.innerHTML = '<option value="">-- Selecciona cliente --</option>' + 
      clientes.map(function(c){ return '<option value="'+c.id+'">'+c.nombre+'</option>'; }).join('');
  }

  function _cargarClientes(){
    selCli.innerHTML = '<option value="">Cargando...</option>';
    fetch("{% url 'roles:api_clientes_gestor' %}", {headers:{'Accept':'application/json'}})
      .then(function(r){ return r.json(); })
      .then(function(d){
        if (!d.success){ selCli.innerHTML = '<option value="">Error</option>'; return; }
        _clientesCache = d.clientes || [];
        _renderClientes(_clientesCache);
      })
      .catch(function(e){ selCli.innerHTML = '<option value="">Error: '+e.message+'</option>'; });
  }

  selCli.addEventListener('change', function(){
    var cid = selCli.value;
    if (!cid){ selFP.innerHTML = '<option value="">-- Selecciona cliente primero --</option>'; return; }
    if (!_clientesCache){ return; }
    var cliente = _clientesCache.find(function(c){ return String(c.id) === String(cid); });
    if (!cliente){ selFP.innerHTML = '<option value="">Sin fondos</option>'; return; }
    selFP.innerHTML = '<option value="">-- Selecciona FP --</option>' + 
      cliente.fps.map(function(f){ return '<option value="'+f.id+'">'+f.nombre+' (Saldo: $'+f.saldo.toFixed(2)+')</option>'; }).join('');
  });

  selMotivo.addEventListener('change', function(){
    inpDetalle.style.display = (selMotivo.value === 'otro') ? 'block' : 'none';
  });

  if (btnConfirmar){
    btnConfirmar.addEventListener('click', function(){
      var cid = selCli.value;
      var fpid = selFP.value;
      var monto = parseFloat(inpMonto.value) || 0;
      var motivo = selMotivo.value;
      var detalle = (inpDetalle.value || '').trim();
      errBox.style.display = 'none';

      if (!cid){ errBox.textContent = 'Selecciona un cliente'; errBox.style.display = 'block'; return; }
      if (!fpid){ errBox.textContent = 'Selecciona una FP'; errBox.style.display = 'block'; return; }
      if (monto <= 0){ errBox.textContent = 'Monto mayor a 0'; errBox.style.display = 'block'; return; }

      btnConfirmar.disabled = true;
      btnConfirmar.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Procesando...';

      var fd = new FormData();
      fd.append('usuario_id', cid);
      fd.append('forma_pago_id', fpid);
      fd.append('monto', monto.toFixed(2));
      fd.append('motivo_tipo', motivo);
      fd.append('motivo_detalle', detalle);
      fd.append('csrfmiddlewaretoken', CSRF);

      fetch("{% url 'roles:api_retiro_rapido' %}", {
        method: 'POST', body: fd,
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
      }).then(function(r){ return r.json(); }).then(function(d){
        if (!d.success){
          errBox.textContent = d.error || 'Error';
          errBox.style.display = 'block';
          btnConfirmar.disabled = false;
          btnConfirmar.innerHTML = '<i class="fas fa-check"></i> Confirmar retiro';
          return;
        }
        _cerrar();
        // Recargar clientes para reflejar el nuevo saldo
        _clientesCache = null;
        if (typeof LottoRT !== 'undefined' && LottoRT.toast) LottoRT.toast('Retiro de $' + d.monto.toFixed(2) + '. Nuevo saldo: $' + d.saldo_despues.toFixed(2), 'success');
        else if (window.showToast) showToast('Retiro OK: $' + d.monto.toFixed(2), 'pos');
        else alert('Retiro de $' + d.monto.toFixed(2) + ' realizado. Nuevo saldo: $' + d.saldo_despues.toFixed(2));
        btnConfirmar.disabled = false;
        btnConfirmar.innerHTML = '<i class="fas fa-check"></i> Confirmar retiro';
      }).catch(function(e){
        errBox.textContent = 'Error: ' + e.message;
        errBox.style.display = 'block';
        btnConfirmar.disabled = false;
        btnConfirmar.innerHTML = '<i class="fas fa-check"></i> Confirmar retiro';
      });
    });
  }
})();
</script>
'''

    idx = src2.rfind("</body>")
    if idx > 0:
        src2 = src2[:idx] + modal_retiro + src2[idx:]
        p2.write_text(src2, encoding="utf-8")
        print("2b: OK (modal retiro insertado)")
    else:
        print("2b: ERROR (no </body>)")

print("")
print("--- VERIFICACION ---")
print("sidebarRetiroLink:", src2.count("sidebarRetiroLink"))
print("globalRetiroModal:", src2.count("globalRetiroModal"))
