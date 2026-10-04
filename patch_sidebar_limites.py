from pathlib import Path
import ast

# ═══════════════════════════════════════════════════════════════
# 1. Endpoint: gestores + sorteos disponibles para el usuario
# ═══════════════════════════════════════════════════════════════
p1 = Path("/home/LottoBooM/roles/views.py")
src1 = p1.read_text(encoding="utf-8")

if "def api_gestores_disponibles" in src1:
    print("1: SKIP (endpoint ya existe)")
else:
    endpoint = '''

# ═══════════════════════════════════════════════════════════════
# API · Gestores y sorteos disponibles para consultar limites
# ═══════════════════════════════════════════════════════════════
@login_required
def api_gestores_disponibles(request):
    """Devuelve gestores que el usuario puede consultar + sorteos activos."""
    user = request.user
    es_superadmin = user.is_superuser or user.roles.filter(tipo='superadmin', activo=True).exists()
    es_banco = user.roles.filter(tipo='banco', activo=True).exists()
    es_comercial = user.roles.filter(tipo='comercial', activo=True).exists()

    if not (es_superadmin or es_banco or es_comercial):
        return JsonResponse({'success': False, 'error': 'Sin permisos'}, status=403)

    gestores = []
    if es_superadmin:
        # Todos los bancos + comerciales + él mismo
        gestores.append({'id': user.id, 'nombre': user.username + ' (yo)', 'tipo': 'superadmin'})
        for u in User.objects.filter(roles__tipo='banco', roles__activo=True, is_active=True).distinct():
            if u.id != user.id:
                gestores.append({'id': u.id, 'nombre': u.username, 'tipo': 'banco'})
        for u in User.objects.filter(roles__tipo='comercial', roles__activo=True, is_active=True).distinct():
            if u.id != user.id:
                gestores.append({'id': u.id, 'nombre': u.username, 'tipo': 'comercial'})
    elif es_banco:
        gestores.append({'id': user.id, 'nombre': user.username + ' (yo)', 'tipo': 'banco'})
        comerciales_ids = Subordinacion.objects.filter(jefe=user, activo=True).values_list('subordinado_id', flat=True)
        for u in User.objects.filter(id__in=comerciales_ids, is_active=True).order_by('username'):
            gestores.append({'id': u.id, 'nombre': u.username, 'tipo': 'comercial'})
    else:
        # Comercial: solo él mismo
        gestores.append({'id': user.id, 'nombre': user.username + ' (yo)', 'tipo': 'comercial'})

    # Sorteos activos
    sorteos = []
    for s in Sorteo.objects.filter(activo=True).order_by('nombre'):
        sorteos.append({'id': s.id, 'nombre': s.nombre})

    return JsonResponse({
        'success': True,
        'gestores': gestores,
        'sorteos': sorteos,
    })

'''
    src1 = src1 + endpoint
    p1.write_text(src1, encoding="utf-8")
    print("1: OK (endpoint api_gestores_disponibles)")

try:
    ast.parse(src1)
    print("OK: sintaxis views.py")
except SyntaxError as e:
    print("ERROR views:", e)
    raise SystemExit(1)

# URL
import re
pu = Path("/home/LottoBooM/roles/urls.py")
srcurls = pu.read_text(encoding="utf-8")
if "api_gestores_disponibles" not in srcurls:
    m = re.search(r"urlpatterns\s*=\s*\[", srcurls)
    srcurls = srcurls[:m.end()] + "\n    path('api/gestores-disponibles/', views.api_gestores_disponibles, name='api_gestores_disponibles')," + srcurls[m.end():]
    pu.write_text(srcurls, encoding="utf-8")
    print("1: OK (URL api_gestores_disponibles)")


# ═══════════════════════════════════════════════════════════════
# 2. Sidebar: enlace solo para gestores
# ═══════════════════════════════════════════════════════════════
p2 = Path("/home/LottoBooM/templates/base.html")
src2 = p2.read_text(encoding="utf-8")

if "sidebarLimitesLink" in src2:
    print("2: SKIP (enlace ya existe)")
else:
    # Buscar dónde ponerlo: cerca de historial_movimientos
    viejo = '''<a href="{% url 'roles:historial_movimientos' %}" class="menu-item">'''
    
    nuevo = '''{% if not es_cliente_sidebar %}
    <a href="#" id="sidebarLimitesLink" class="menu-item" style="cursor:pointer;">
      <i class="fas fa-chart-bar"></i>
      <span>Límites y dosis</span>
    </a>
    {% endif %}
    <a href="{% url 'roles:historial_movimientos' %}" class="menu-item">'''
    
    if viejo in src2:
        src2 = src2.replace(viejo, nuevo, 1)
        print("2: OK (enlace insertado antes de historial_movimientos)")
    else:
        print("2: ERROR (no encontre historial_movimientos)")
        # Buscar otra ancla
        anchors = ['<a href="{% url \'roles:historial_movimientos\' %}"',
                   '<a href="{% url \'roles:recarga_directa\' %}"']
        for anchor in anchors:
            if anchor in src2:
                src2 = src2.replace(anchor, f'<a href="#" id="sidebarLimitesLink" class="menu-item"><i class="fas fa-chart-bar"></i><span>Límites y dosis</span></a>\n{anchor}', 1)
                print(f"2: OK (enlace insertado via {anchor[:40]})")
                break

# Asegurar variable es_cliente_sidebar en el contexto global
# (o usar una variable existente)

p2.write_text(src2, encoding="utf-8")
print("2: template base.html actualizado")


# ═══════════════════════════════════════════════════════════════
# 3. Modal global + JS en base.html
# ═══════════════════════════════════════════════════════════════
if "globalLimitesModal" in src2:
    print("3: SKIP (modal ya existe)")
else:
    modal_html = '''

{# ═══════ MODAL GLOBAL DE LÍMITES Y DOSIS ═══════ #}
<div id="globalLimitesModal" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.7);z-index:99999;align-items:center;justify-content:center;padding:16px;overflow-y:auto;">
  <div style="background:#fff;border-radius:16px;max-width:640px;width:100%;box-shadow:0 20px 60px rgba(0,0,0,.5);border:2px solid #4f46e5;">
    <div style="background:linear-gradient(135deg,#4f46e5,#3730a3);color:#fff;padding:16px 22px;border-radius:14px 14px 0 0;display:flex;justify-content:space-between;align-items:center;">
      <h5 style="margin:0;font-weight:900;font-size:1rem;">
        <i class="fas fa-chart-bar" style="margin-right:8px;"></i>Límites y dosis
      </h5>
      <button type="button" id="globalLimitesClose" style="background:transparent;border:none;color:#fff;font-size:1.5rem;cursor:pointer;line-height:1;padding:0 6px;">&times;</button>
    </div>
    <div style="padding:18px 22px;">
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:16px;">
        <div>
          <label style="font-weight:800;font-size:.72rem;color:#3730a3;display:block;margin-bottom:6px;text-transform:uppercase;letter-spacing:.5px;">Gestor</label>
          <select id="globalLimitesGestor" style="width:100%;padding:8px 12px;border-radius:8px;border:1.5px solid #c7d2fe;font-weight:700;color:#3730a3;background:#fff;font-size:.85rem;font-family:inherit;">
            <option value="">Cargando...</option>
          </select>
        </div>
        <div>
          <label style="font-weight:800;font-size:.72rem;color:#3730a3;display:block;margin-bottom:6px;text-transform:uppercase;letter-spacing:.5px;">Sorteo</label>
          <select id="globalLimitesSorteo" style="width:100%;padding:8px 12px;border-radius:8px;border:1.5px solid #c7d2fe;font-weight:700;color:#3730a3;background:#fff;font-size:.85rem;font-family:inherit;">
            <option value="">Cargando...</option>
          </select>
        </div>
      </div>
      <div id="globalLimitesContenido" style="min-height:150px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:14px;text-align:center;color:#6B7280;font-size:.85rem;">
        Selecciona gestor y sorteo para ver los límites
      </div>
    </div>
    <div style="padding:14px 22px;border-top:1px solid #c7d2fe;background:#f9fafb;border-radius:0 0 14px 14px;text-align:right;">
      <button type="button" id="globalLimitesCerrar" style="background:#e5e7eb;color:#374151;border:none;padding:10px 20px;border-radius:10px;font-weight:800;cursor:pointer;font-family:inherit;font-size:.85rem;">Cerrar</button>
    </div>
  </div>
</div>

<script>
(function(){
  var modal = document.getElementById('globalLimitesModal');
  if (!modal) return;

  var link = document.getElementById('sidebarLimitesLink');
  var selGestor = document.getElementById('globalLimitesGestor');
  var selSorteo = document.getElementById('globalLimitesSorteo');
  var cont = document.getElementById('globalLimitesContenido');
  var btnClose = document.getElementById('globalLimitesClose');
  var btnCerrar = document.getElementById('globalLimitesCerrar');
  var _cargado = false;

  function _abrir(){
    modal.style.display = 'flex';
    document.body.style.overflow = 'hidden';
    if (!_cargado){
      _cargado = true;
      _cargarDatos();
    }
  }
  function _cerrar(){
    modal.style.display = 'none';
    document.body.style.overflow = '';
  }

  if (link) link.addEventListener('click', function(e){ e.preventDefault(); _abrir(); });
  if (btnClose) btnClose.addEventListener('click', _cerrar);
  if (btnCerrar) btnCerrar.addEventListener('click', _cerrar);
  modal.addEventListener('click', function(e){ if (e.target === modal) _cerrar(); });

  function _cargarDatos(){
    fetch("{% url 'roles:api_gestores_disponibles' %}", {headers: {'Accept':'application/json'}})
      .then(function(r){ return r.json(); })
      .then(function(d){
        if (!d.success){ cont.textContent = 'Error al cargar'; return; }
        selGestor.innerHTML = '<option value="">-- Selecciona --</option>' + 
          (d.gestores||[]).map(function(g){ return '<option value="'+g.id+'">'+g.nombre+'</option>'; }).join('');
        selSorteo.innerHTML = '<option value="">-- Selecciona --</option>' + 
          (d.sorteos||[]).map(function(s){ return '<option value="'+s.id+'">'+s.nombre+'</option>'; }).join('');
      })
      .catch(function(e){ cont.textContent = 'Error: ' + e.message; });
  }

  function _cargarLimites(){
    var gid = selGestor.value, sid = selSorteo.value;
    if (!gid || !sid){ cont.textContent = 'Selecciona gestor y sorteo'; return; }
    cont.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Cargando...';
    fetch("{% url 'roles:api_limites_gestor' %}?gestor_id=" + gid + "&sorteo_id=" + sid)
      .then(function(r){ return r.json(); })
      .then(function(d){
        if (!d.success){ cont.textContent = d.error || 'Error'; return; }
        var formas = d.formas || [];
        if (!formas.length){ cont.innerHTML = '<em style="color:#6B7280;">Sin límites configurados.</em>'; return; }
        var html = '<table style="width:100%;border-collapse:collapse;font-size:.82rem;">'
                 + '<thead><tr style="background:#eef2ff;color:#3730a3;">'
                 + '<th style="padding:8px;text-align:left;">Forma</th>'
                 + '<th style="padding:8px;text-align:right;">Límite</th>'
                 + '<th style="padding:8px;text-align:right;">Dosis</th>'
                 + '<th style="padding:8px;text-align:right;">Sobrelímite</th>'
                 + '</tr></thead><tbody>';
        formas.forEach(function(f){
          html += '<tr style="border-bottom:1px solid #e5e7eb;">'
               + '<td style="padding:8px;font-weight:800;color:#3730a3;">'+f.forma+'</td>'
               + '<td style="padding:8px;text-align:right;font-family:monospace;font-weight:800;color:#065F46;">$'+f.limite.toFixed(2)+'</td>'
               + '<td style="padding:8px;text-align:right;font-family:monospace;font-weight:800;color:#4338ca;">x'+f.dosis.toFixed(2)+'</td>'
               + '<td style="padding:8px;text-align:right;font-family:monospace;font-weight:800;color:#b45309;">$'+f.sobrelimite.toFixed(2)+'</td>'
               + '</tr>';
        });
        html += '</tbody></table>';
        cont.innerHTML = html;
      })
      .catch(function(e){ cont.textContent = 'Error: ' + e.message; });
  }

  selGestor.addEventListener('change', _cargarLimites);
  selSorteo.addEventListener('change', _cargarLimites);
})();
</script>
'''

    # Insertar antes del cierre de body
    idx = src2.rfind("</body>")
    if idx > 0:
        src2 = src2[:idx] + modal_html + src2[idx:]
        print("3: OK (modal global insertado)")
    else:
        print("3: ERROR (no encontre </body>)")

p2.write_text(src2, encoding="utf-8")
print("OK: template base.html actualizado")
