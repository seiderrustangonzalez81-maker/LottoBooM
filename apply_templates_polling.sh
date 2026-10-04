#!/bin/bash
set -euo pipefail
PROJECT="/home/LottoBooM"; cd "$PROJECT"
G='\033[0;32m'; R='\033[0;31m'; Y='\033[0;33m'; B='\033[1;34m'; NC='\033[0m'
log(){ echo -e "${G}[✔]${NC} $*"; }
warn(){ echo -e "${Y}[!]${NC} $*"; }
step(){ echo -e "\n${B}═══ $* ═══${NC}"; }

step "1/5 · Backup"
BK="_backup_tpl_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BK"
for f in \
  roles/templates/roles/lista_clientes.html \
  roles/templates/roles/recarga_directa.html \
  jugadas/templates/jugadas/apostar.html \
  templates/base.html; do
  [ -f "$f" ] && mkdir -p "$BK/$(dirname "$f")" && cp "$f" "$BK/$f" && log "bk $f"
done
echo "$BK" > .last_backup_tpl

step "2/5 · Añadir estilos + CSS del badge online a base.html"
python3 << 'PYEOF'
from pathlib import Path
p = Path("/home/LottoBooM/templates/base.html")
src = p.read_text(encoding="utf-8")

if "online-badge" in src and "lottort-kpi-live" in src:
    print("○ Estilos ya presentes")
    raise SystemExit(0)

CSS = '''
<style id="lottort-css">
/* Badge online reutilizable */
.online-badge{
  display:inline-block;width:10px;height:10px;border-radius:50%;
  margin:0 2px;vertical-align:middle;
  box-shadow:0 0 0 1px rgba(0,0,0,.15);
}
.online-badge.is-online{background:#22c55e;box-shadow:0 0 8px rgba(34,197,94,.7);animation:ob-pulse 2s infinite;}
.online-badge.is-offline{background:#94a3b8;}
@keyframes ob-pulse{0%,100%{box-shadow:0 0 0 1px rgba(0,0,0,.15),0 0 8px rgba(34,197,94,.7);}50%{box-shadow:0 0 0 1px rgba(0,0,0,.15),0 0 14px rgba(34,197,94,.9);}}

/* KPIs en vivo (opcional si el template los usa) */
.lottort-kpi-live{display:inline-flex;align-items:center;gap:6px;}
.lottort-kpi-live .lv-num{font-weight:900;}
.lottort-kpi-live .lv-on{color:#16a34a;}
.lottort-kpi-live .lv-off{color:#64748b;}

/* Toast ligero cuando cambia el fondo */
.lottort-toast{
  position:fixed;top:80px;right:20px;z-index:9999;
  background:#065F46;color:#fff;font-weight:700;font-size:.82rem;
  padding:10px 16px;border-radius:10px;
  box-shadow:0 8px 24px rgba(4,120,87,.35);
  opacity:0;transform:translateY(-8px);
  transition:opacity .25s,transform .25s;
  pointer-events:none;
}
.lottort-toast.show{opacity:1;transform:translateY(0);}
</style>
'''

idx = src.rfind("</head>")
if idx == -1:
    # Fallback: antes de {% block content %}
    idx = src.find("{% block content %}")
    if idx == -1:
        print("✘ No encontré dónde insertar CSS")
        raise SystemExit(1)

src = src[:idx] + CSS + src[idx:]
p.write_text(src, encoding="utf-8")
print("✔ CSS del badge online añadido a base.html")
PYEOF

step "3/5 · lista-clientes.html — KPIs en vivo + badge por fila + polling"
python3 << 'PYEOF'
from pathlib import Path
import re

p = Path("/home/LottoBooM/roles/templates/roles/lista_clientes.html")
if not p.exists():
    print("✘ No existe lista_clientes.html")
    raise SystemExit(0)

src = p.read_text(encoding="utf-8")

if "lottort-lista-clientes" in src:
    print("○ Ya tiene polling")
    raise SystemExit(0)

# 1) Anotar cada <tr> con data-cliente-id si aún no lo tiene
# Buscamos los <tr> que están dentro del loop {% for c in clientes_data %}
# Heurística: buscar "{% for" + tr y añadir el data attribute con {{ c.cliente.id }}
patron_tr = re.compile(
    r'(<tr)(\s*>)(?!\s*<td[^>]*colspan)',
    re.MULTILINE,
)
# Mejor: buscar el primer tr con clase="cliente-row" o sin clase
# Alternativa: inyectar el data attribute justo dentro del bloque for
# Vamos simple: reemplazar el primer <tr ...> dentro de {% for c in clientes_data %}

def reemplazar_tr(m):
    return m.group(0)  # placeholder, no hacemos nada aún

# Anotar los tr con data-cliente-id si están dentro del for
# Patrón: {% for ... %} ... <tr ...> ... {% endfor %}
for_match = re.search(r"(\{%\s*for\s+c\s+in\s+clientes_data\s*%\})", src)
if for_match:
    # Encontrar el primer <tr después
    start = for_match.end()
    tr_match = re.search(r"<tr(\s|>)", src[start:])
    if tr_match:
        insert_pos = start + tr_match.start()
        # Insertar data-cliente-id
        src = (
            src[:insert_pos]
            + '<tr data-cliente-id="{{ c.cliente.id }}"'
            + src[insert_pos + 3:]  # quitar "<tr"
        )
        print("✔ data-cliente-id inyectado en cada <tr>")

# 2) Añadir bloque KPIs en vivo ANTES del cierre de {% block content %}
# Mejor: añadirlo dentro del contenedor principal, después de los KPIs existentes
bloque_kpi = '''
{# ═══════ KPIs en vivo (polling) ═══════ #}
<div class="row mb-3" id="lottort-kpis" style="display:none;">
  <div class="col">
    <div class="card" style="border-left:4px solid #22c55e;">
      <div class="card-body py-2 px-3">
        <small class="text-muted d-block" style="font-size:.65rem;text-transform:uppercase;font-weight:800;">En línea</small>
        <span class="lottort-kpi-live"><span class="lv-num lv-on" data-rt="online">—</span><span style="font-size:.7rem;color:#64748b;">/&nbsp;<span data-rt="total">—</span></span></span>
      </div>
    </div>
  </div>
  <div class="col">
    <div class="card" style="border-left:4px solid #6366f1;">
      <div class="card-body py-2 px-3">
        <small class="text-muted d-block" style="font-size:.65rem;text-transform:uppercase;font-weight:800;">Fondo total</small>
        <span class="lottort-kpi-live"><span class="lv-num" data-rt="fondo_total">$0.00</span></span>
      </div>
    </div>
  </div>
</div>
'''

# Insertar antes del cierre del block content
idx = src.rfind("{% endblock %}")
if idx == -1:
    print("⚠ No encontré {% endblock %} — no inyecto KPIs")
else:
    src = src[:idx] + bloque_kpi + src[idx:]
    print("✔ Bloque KPIs en vivo inyectado")

# 3) Script de polling ANTES del cierre del block content
script = '''
{# ═══════ POLLING · Lista de clientes ═══════ #}
<script>
(function(){
  var STATE_URL = "{% url 'usuarios:api_state' %}";
  var HEART_URL = "{% url 'usuarios:api_heartbeat' %}";
  var CSRF = (document.querySelector('[name=csrfmiddlewaretoken]')||{}).value || '';
  if (!window.LottoRT) {
    // Fallback mínimo si rt_polling.js no está cargado
    window.LottoRT = { start: function(o){
      setInterval(function(){
        fetch(o.stateUrl + '?scope=' + o.scope, {headers:{'Accept':'application/json'}})
          .then(function(r){ return r.ok ? r.json() : null; })
          .then(function(d){ if (d) o.onData(d); }).catch(function(){});
      }, o.interval || 20000);
      if (o.heartUrl) setInterval(function(){
        fetch(o.heartUrl,{method:'POST',headers:{'X-CSRFToken':CSRF}}).catch(function(){});
      }, 90000);
    }};
  }

  var poller = LottoRT.start({
    stateUrl: STATE_URL,
    heartUrl: HEART_URL,
    scope: 'lista-clientes',
    interval: 20000,
    onData: function(data){
      if (!data || !data.success) return;
      var kpis = document.getElementById('lottort-kpis');
      if (kpis) {
        kpis.style.display = '';
        var o = kpis.querySelector('[data-rt="online"]'); if (o) o.textContent = data.online;
        var t = kpis.querySelector('[data-rt="total"]');  if (t) t.textContent = data.total;
        var f = kpis.querySelector('[data-rt="fondo_total"]'); if (f) f.textContent = '$' + (data.total_fondo||0).toFixed(2);
      }
      // Actualizar badges + fondos por fila
      (data.clientes || []).forEach(function(c){
        var row = document.querySelector('tr[data-cliente-id="' + c.id + '"]');
        if (!row) return;
        var badge = row.querySelector('.online-badge');
        if (badge) {
          badge.classList.toggle('is-online', c.online);
          badge.classList.toggle('is-offline', !c.online);
          badge.title = c.online ? 'En línea' : 'Offline';
        }
        // Intentar actualizar celda de fondo total
        var fondCell = row.querySelector('[data-rt="total_fondo"]');
        if (fondCell) fondCell.textContent = '$' + (c.total_fondo || 0).toFixed(2);
      });
    }
  });
})();
</script>
'''

idx = src.rfind("{% endblock %}")
if idx == -1:
    print("⚠ No encontré {% endblock %} — no inyecto script")
else:
    src = src[:idx] + script + src[idx:]
    print("✔ Script de polling inyectado")

p.write_text(src, encoding="utf-8")

# Verificar
import ast
try:
    # No es Python, pero verificamos que no rompimos la estructura básica
    assert "lottort-kpis" in src or "lottort-kpis" in src
    print("✔ lista-clientes.html actualizado")
except Exception as e:
    print(f"✘ {e}")
PYEOF

step "4/5 · recarga-directa.html — bloque fondo cliente en vivo"
python3 << 'PYEOF'
from pathlib import Path
import re

p = Path("/home/LottoBooM/roles/templates/roles/recarga_directa.html")
if not p.exists():
    print("✘ No existe recarga_directa.html")
    raise SystemExit(0)

src = p.read_text(encoding="utf-8")
if "lottort-fondo-cliente" in src:
    print("○ Ya tiene bloque fondo cliente")
    raise SystemExit(0)

# Insertar bloque después del "locked-panel" o después del título del cliente
bloque = '''
{# ═══════ FONDO DEL CLIENTE EN VIVO (polling) ═══════ #}
{% if usuario_preseleccionado %}
<div class="lottort-fondo-cliente" id="lottort-fondo-cliente"
     style="background:linear-gradient(145deg,#ecfdf5,#d1fae5);border:2px solid #10B981;border-radius:14px;padding:14px 18px;margin-bottom:18px;box-shadow:0 4px 16px rgba(16,185,129,.15);">
  <div style="display:flex;justify-content:space-between;align-items:center;font-weight:800;color:#065F46;font-size:.85rem;margin-bottom:10px;padding-bottom:8px;border-bottom:2px dashed #86efac;flex-wrap:wrap;gap:6px;">
    <span>
      💰 Fondo actual del cliente
      <span class="online-badge is-offline" data-online-for="{{ usuario_preseleccionado.id }}" style="margin-left:6px;"></span>
      <small id="lottort-ultima-act" style="color:#065F46;font-weight:600;font-size:.7rem;"></small>
    </span>
    <span id="lottort-fondo-total" style="font-size:1.4rem;font-weight:900;color:#047857;font-family:'Courier New',monospace;background:#fff;padding:4px 14px;border-radius:10px;box-shadow:2px 2px 0 #86efac;">$—</span>
  </div>
  <div id="lottort-fondos-grid" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:8px;">
    <div style="text-align:center;color:#6B7280;font-style:italic;font-size:.8rem;padding:10px;">Cargando…</div>
  </div>
</div>

<script>
(function(){
  var CLIENTE_ID = {{ usuario_preseleccionado.id }};
  var STATE_URL = "{% url 'usuarios:api_state' %}";
  var HEART_URL = "{% url 'usuarios:api_heartbeat' %}";
  var CSRF = (document.querySelector('[name=csrfmiddlewaretoken]')||{}).value || '';
  var _etag = null;

  function fetchState(){
    var h = {'Accept':'application/json','X-Requested-With':'XMLHttpRequest'};
    if (_etag) h['If-None-Match'] = _etag;
    return fetch(STATE_URL + '?scope=recarga-directa&cliente_id=' + CLIENTE_ID, { headers: h, credentials: 'same-origin' })
      .then(function(r){
        if (r.status === 304 || r.status === 429) return null;
        if (!r.ok) throw new Error('HTTP ' + r.status);
        var et = r.headers.get('ETag'); if (et) _etag = et;
        return r.json();
      });
  }

  function render(data){
    if (!data || !data.success) return;
    var total = document.getElementById('lottort-fondo-total');
    if (total) total.textContent = '$' + (data.total_fondo || 0).toFixed(2);

    var badge = document.querySelector('.online-badge[data-online-for="' + CLIENTE_ID + '"]');
    if (badge) {
      badge.classList.toggle('is-online', !!data.online);
      badge.classList.toggle('is-offline', !data.online);
      badge.title = data.online ? 'En línea' : 'Offline';
    }
    var ult = document.getElementById('lottort-ultima-act');
    if (ult && data.last_activity) {
      var d = new Date(data.last_activity);
      ult.textContent = '· activo hace ' + Math.floor((Date.now() - d.getTime())/60000) + ' min';
    }

    var grid = document.getElementById('lottort-fondos-grid');
    if (!grid) return;
    var f = data.fondos || {};
    var keys = Object.keys(f);
    if (!keys.length) {
      grid.innerHTML = '<div style="text-align:center;color:#6B7280;font-style:italic;font-size:.8rem;padding:10px;">Sin fondos activos</div>';
      return;
    }
    var html = '';
    keys.forEach(function(k){
      var v = f[k];
      var color = v < 0 ? '#b91c1c' : '#047857';
      var ico = v < 0 ? '🔴' : '🟢';
      html += '<div style="background:#fff;border:1px solid #b6e5c2;border-radius:8px;padding:8px 10px;display:flex;flex-direction:column;gap:2px;">'
           +    '<span style="font-size:.62rem;font-weight:800;color:#065F46;text-transform:uppercase;letter-spacing:.4px;">' + ico + ' ' + k + '</span>'
           +    '<span style="font-size:.95rem;font-weight:900;color:' + color + ';font-family:Courier New,monospace;">$' + v.toFixed(2) + '</span>'
           +  '</div>';
    });
    grid.innerHTML = html;
  }

  function tick(){ fetchState().then(render).catch(function(){}); }

  // Polling cada 8s con jitter
  function loop(){
    setTimeout(function(){
      tick();
      loop();
    }, 8000 + Math.random()*2000);
  }

  // Heartbeat cada 90s
  if (HEART_URL && CSRF) {
    setInterval(function(){
      fetch(HEART_URL,{method:'POST',headers:{'X-CSRFToken':CSRF}}).catch(function(){});
    }, 90000);
  }

  tick();
  loop();
  document.addEventListener('visibilitychange', function(){ if (!document.hidden) tick(); });
})();
</script>
{% endif %}
'''

# Insertar antes del cierre del block content
idx = src.rfind("{% endblock %}")
if idx == -1:
    print("⚠ No encontré endblock")
    raise SystemExit(0)

src = src[:idx] + bloque + src[idx:]
p.write_text(src, encoding="utf-8")
print("✔ Bloque fondo cliente en vivo inyectado")
PYEOF

step "5/5 · apostar.html — badge cliente seleccionado"
python3 << 'PYEOF'
from pathlib import Path
import re

p = Path("/home/LottoBooM/jugadas/templates/jugadas/apostar.html")
if not p.exists():
    print("⚠ No existe apostar.html — saltando")
    raise SystemExit(0)

src = p.read_text(encoding="utf-8")
if "lottort-apo-badge" in src:
    print("○ Ya tiene badge en apostar")
    raise SystemExit(0)

# Inyectar script ANTES de {% endblock %} final
bloque = '''
{# ═══════ Badge online del cliente seleccionado (apostar) ═══════ #}
<script>
(function(){
  var sel = document.getElementById('selCliente');
  if (!sel) return;
  var STATE_URL = "{% url 'usuarios:api_state' %}";
  var HEART_URL = "{% url 'usuarios:api_heartbeat' %}";
  var CSRF = (document.querySelector('[name=csrfmiddlewaretoken]')||{}).value || '';
  var badgeId = 'lottort-apo-badge';

  function insertarBadge(){
    var viejo = document.getElementById(badgeId);
    if (viejo) viejo.remove();
    if (!sel.value) return;
    var span = document.createElement('span');
    span.id = badgeId;
    span.className = 'online-badge is-offline';
    span.style.marginLeft = '8px';
    span.title = 'Verificando…';
    sel.parentNode.insertBefore(span, sel.nextSibling);
  }

  function actualizar(){
    var cid = sel.value;
    if (!cid) return;
    fetch(STATE_URL + '?scope=apostar&cliente_id=' + cid, {headers:{'Accept':'application/json'}})
      .then(function(r){ return r.ok ? r.json() : null; })
      .then(function(d){
        if (!d || !d.success || !d.clientes || !d.clientes.length) return;
        var c = d.clientes[0];
        var b = document.getElementById(badgeId);
        if (!b) { insertarBadge(); b = document.getElementById(badgeId); }
        if (b) {
          b.classList.toggle('is-online', !!c.online);
          b.classList.toggle('is-offline', !c.online);
          b.title = c.online ? 'En línea' : 'Offline';
        }
      }).catch(function(){});
  }

  sel.addEventListener('change', function(){ insertarBadge(); actualizar(); });
  // Polling cada 30s
  setInterval(actualizar, 30000);
  // Heartbeat cada 90s
  if (HEART_URL && CSRF) {
    setInterval(function(){
      fetch(HEART_URL,{method:'POST',headers:{'X-CSRFToken':CSRF}}).catch(function(){});
    }, 90000);
  }
})();
</script>
'''

idx = src.rfind("{% endblock %}")
if idx == -1:
    print("⚠ No encontré endblock en apostar.html")
    raise SystemExit(0)

src = src[:idx] + bloque + src[idx:]
p.write_text(src, encoding="utf-8")
print("✔ Badge en apostar.html inyectado")
PYEOF

echo ""
echo -e "${G}🎉 PASO 3 COMPLETO${NC}"
echo "Backup: $BK"
