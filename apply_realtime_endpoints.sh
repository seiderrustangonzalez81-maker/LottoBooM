#!/bin/bash
set -euo pipefail
PROJECT="/home/LottoBooM"; cd "$PROJECT"
G='\033[0;32m'; R='\033[0;31m'; B='\033[1;34m'; NC='\033[0m'
log(){ echo -e "${G}[✔]${NC} $*"; }
step(){ echo -e "\n${B}═══ $* ═══${NC}"; }

step "1/6 · Backup"
BK="_backup_rt2_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BK/usuarios" "$BK/templates/partials" "$BK/static/js" "$BK/templates"
for f in usuarios/urls.py templates/base.html; do
  [ -f "$f" ] && cp "$f" "$BK/$f" && log "bk $f"
done
echo "$BK" > .last_backup_rt2

step "2/6 · Endpoints /api/state/ y /api/heartbeat/"
cat > "$PROJECT/usuarios/api_views.py" << 'PY_EOF'
# usuarios/api_views.py
"""
Endpoints AJAX para polling de estado en tiempo real.
PythonAnywhere Free: 1 worker, LocMemCache.
- heartbeat: 204, solo cache.set (ultra liviano)
- state: agregado, ETag + cache 5s + rate limit 4s
"""
import hashlib
import json
import logging

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.cache import cache
from django.db.models import Q, Sum
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST

from usuarios.cache_utils import (
    marcar_online, esta_online, mapa_online, contar_online,
    last_activity_cache,
)

logger = logging.getLogger(__name__)


def _rate_limited(user_id, scope, min_sg=4):
    key = f'rl:{user_id}:{scope}'
    if cache.get(key):
        return True
    cache.set(key, 1, timeout=min_sg)
    return False


@login_required
@require_POST
def api_heartbeat(request):
    marcar_online(request.user)
    return HttpResponse(status=204)


@login_required
def api_state(request):
    user = request.user
    scope = (request.GET.get('scope') or 'global').strip()
    cliente_id = (request.GET.get('cliente_id') or '').strip()

    if _rate_limited(user.id, scope):
        cached = cache.get(f'state:last:{user.id}:{scope}:{cliente_id}')
        if cached:
            etag, payload = cached
            if request.headers.get('If-None-Match') == etag:
                return HttpResponse(status=304)
            resp = JsonResponse(payload)
            resp['ETag'] = etag
            return resp
        return JsonResponse({'success': False, 'error': 'rate_limited'}, status=429)

    cache_key = f'state:last:{user.id}:{scope}:{cliente_id}'
    cached = cache.get(cache_key)

    if cached:
        etag, payload = cached
    else:
        try:
            payload = _build_state(user, scope, cliente_id)
            payload['ts'] = timezone.now().isoformat()
            raw = json.dumps(payload, sort_keys=True, default=str)
            etag = hashlib.md5(raw.encode()).hexdigest()[:16]
            payload['etag'] = etag
            cache.set(cache_key, (etag, payload), timeout=5)
        except Exception as e:
            logger.exception(f'[api_state] scope={scope} uid={user.id}: {e}')
            return JsonResponse({'success': False, 'error': str(e)}, status=500)

    if request.headers.get('If-None-Match') == etag:
        return HttpResponse(status=304)

    resp = JsonResponse(payload)
    resp['ETag'] = etag
    resp['Cache-Control'] = 'private, max-age=0, must-revalidate'
    return resp


def _build_state(user, scope, cliente_id):
    if scope == 'global': return _state_global(user)
    if scope == 'lista-clientes': return _state_lista_clientes(user)
    if scope == 'recarga-directa': return _state_recarga_directa(user, cliente_id)
    if scope == 'apostar': return _state_apostar(user, cliente_id)
    if scope == 'paneles': return _state_paneles(user)
    return {'success': False, 'error': 'scope desconocido'}


def _state_global(user):
    total_users = User.objects.filter(is_active=True).count()
    online_n = contar_online()
    return {'success': True, 'online': online_n, 'total': total_users}


def _state_lista_clientes(user):
    es_superadmin = user.is_superuser or user.roles.filter(tipo='superadmin', activo=True).exists()
    es_banco = user.roles.filter(tipo='banco', activo=True).exists()
    es_comercial = user.roles.filter(tipo='comercial', activo=True).exists()

    from roles.models import Fondo, Subordinacion

    if es_superadmin:
        qs_users = User.objects.filter(is_active=True)
    elif es_banco:
        comerciales_ids = list(Subordinacion.objects.filter(
            jefe=user, activo=True
        ).values_list('subordinado_id', flat=True))
        clientes_ids = list(Fondo.objects.filter(
            Q(asignado_por__in=comerciales_ids) | Q(asignado_por=user),
            activo=True
        ).values_list('usuario_id', flat=True).distinct())
        qs_users = User.objects.filter(Q(id__in=clientes_ids) | Q(id__in=comerciales_ids), is_active=True)
    elif es_comercial:
        clientes_ids = list(Fondo.objects.filter(
            asignado_por=user, activo=True
        ).values_list('usuario_id', flat=True).distinct())
        qs_users = User.objects.filter(id__in=clientes_ids, is_active=True)
    else:
        return {'success': False, 'error': 'sin permiso'}

    qs_agg = qs_users.annotate(
        total_fondo=Sum('fondos__monto', filter=Q(fondos__activo=True)),
    ).values('id', 'username', 'total_fondo')

    ids = [u['id'] for u in qs_agg]
    mapa = mapa_online(ids)

    clientes = []
    total_fondo_sum = 0.0
    online_n = 0
    for u in qs_agg:
        tf = float(u['total_fondo'] or 0)
        total_fondo_sum += tf
        on = mapa.get(u['id'], False)
        if on:
            online_n += 1
        clientes.append({
            'id': u['id'],
            'username': u['username'],
            'online': on,
            'total_fondo': round(tf, 2),
        })

    return {
        'success': True,
        'online': online_n,
        'total': len(clientes),
        'total_fondo': round(total_fondo_sum, 2),
        'clientes': clientes,
    }


def _state_recarga_directa(user, cliente_id):
    if not cliente_id or not cliente_id.isdigit():
        return {'success': False, 'error': 'falta cliente_id'}

    from roles.models import Fondo
    from pagos.models import FormaPago

    try:
        cliente = User.objects.get(id=int(cliente_id), is_active=True)
    except User.DoesNotExist:
        return {'success': False, 'error': 'cliente no encontrado'}

    from django.db.models import Sum as _Sum
    fondos = {}
    total = 0.0
    for fp in FormaPago.objects.filter(activo=True).order_by('nombre'):
        m = Fondo.objects.filter(
            usuario=cliente, forma_pago=fp, activo=True
        ).aggregate(t=_Sum('monto'))['t'] or 0
        m = float(m)
        if m != 0:
            fondos[fp.nombre] = round(m, 2)
            total += m

    online = esta_online(cliente.id)
    last_act = last_activity_cache(cliente.id)

    return {
        'success': True,
        'cliente_id': cliente.id,
        'username': cliente.username,
        'online': online,
        'last_activity': last_act.isoformat() if last_act else None,
        'fondos': fondos,
        'total_fondo': round(total, 2),
    }


def _state_apostar(user, cliente_id):
    if not cliente_id or not cliente_id.isdigit():
        return {'success': True, 'clientes': []}
    cid = int(cliente_id)
    return {'success': True, 'clientes': [{'id': cid, 'online': esta_online(cid)}]}


def _state_paneles(user):
    from roles.models import Rol
    bancos_ids = list(Rol.objects.filter(tipo='banco', activo=True).values_list('usuario_id', flat=True))
    comerciales_ids = list(Rol.objects.filter(tipo='comercial', activo=True).values_list('usuario_id', flat=True))
    clientes_ids = list(Rol.objects.filter(tipo='cliente', activo=True).values_list('usuario_id', flat=True))
    mb = mapa_online(bancos_ids)
    mc = mapa_online(comerciales_ids)
    mcl = mapa_online(clientes_ids)
    return {
        'success': True,
        'bancos': {'online': sum(1 for v in mb.values() if v), 'total': len(bancos_ids)},
        'comerciales': {'online': sum(1 for v in mc.values() if v), 'total': len(comerciales_ids)},
        'clientes': {'online': sum(1 for v in mcl.values() if v), 'total': len(clientes_ids)},
    }
PY_EOF
log "api_views.py creado"

step "3/6 · URLs"
python3 << 'PYEOF'
from pathlib import Path
import re
p = Path("/home/LottoBooM/usuarios/urls.py")
src = p.read_text(encoding="utf-8")

if "api_heartbeat" in src:
    print("○ URLs ya registradas")
    raise SystemExit(0)

if "from . import api_views" not in src and "from usuarios import api_views" not in src:
    if "from . import views" in src:
        src = src.replace("from . import views", "from . import views\nfrom . import api_views", 1)
    else:
        src = "from . import api_views\n" + src

m = re.search(r"urlpatterns\s*=\s*\[", src)
if not m:
    print("✘ No encontré urlpatterns")
    raise SystemExit(1)

rutas = '''
    path('api/heartbeat/', api_views.api_heartbeat, name='api_heartbeat'),
    path('api/state/',     api_views.api_state,     name='api_state'),
'''
src = src[:m.end()] + rutas + src[m.end():]
p.write_text(src, encoding="utf-8")
print("✔ URLs registradas")

import ast
try:
    ast.parse(src)
    print("✔ Sintaxis OK")
except SyntaxError as e:
    print(f"✘ Error línea {e.lineno}: {e.msg}")
    raise SystemExit(1)
PYEOF

step "4/6 · Partial online badge"
mkdir -p /home/LottoBooM/templates/partials
cat > /home/LottoBooM/templates/partials/_online_badge.html << 'HTML_EOF'
<span class="online-badge {% if online %}is-online{% else %}is-offline{% endif %}"
      data-online-for="{{ user_id }}"
      title="{% if online %}En línea{% else %}Offline{% endif %}">
  {% if online %}🟢{% else %}⚫{% endif %}
</span>
HTML_EOF
log "partial _online_badge.html creado"

step "5/6 · JS rt_polling.js"
mkdir -p /home/LottoBooM/static/js
cat > /home/LottoBooM/static/js/rt_polling.js << 'JS_EOF'
/* rt_polling.js — Polling LottoBooM
 * - Heartbeat cada 90s
 * - Poll estado cada N ms con jitter ±20%
 * - ETag: 304 sin cambios
 * - Pausa al ocultar pestaña
 */
(function(global){
  'use strict';
  var HEARTBEAT_MS = 90000;

  function jitter(ms){ var d = ms * 0.20; return ms + (Math.random() * 2 * d - d); }

  function getCsrf(){
    var c = document.querySelector('[name=csrfmiddlewaretoken]');
    if (c) return c.value;
    var m = document.cookie.match(/(^|;)\s*csrftoken=([^;]+)/);
    return m ? m[2] : '';
  }

  function heartbeat(url){
    fetch(url, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'X-CSRFToken': getCsrf(), 'X-Requested-With': 'XMLHttpRequest' },
    }).catch(function(){});
  }

  function Poller(opts){
    this.stateUrl = opts.stateUrl;
    this.heartUrl = opts.heartUrl;
    this.scope = opts.scope || 'global';
    this.params = opts.params || {};
    this.interval = opts.interval || 20000;
    this.onData = opts.onData || function(){};
    this._etag = null;
    this._timer = null;
    this._heartTimer = null;
    this._stopped = false;
  }

  Poller.prototype._buildUrl = function(){
    var qs = ['scope=' + encodeURIComponent(this.scope)];
    var self = this;
    Object.keys(this.params).forEach(function(k){
      var v = self.params[k];
      if (v !== null && v !== undefined && v !== '') {
        qs.push(encodeURIComponent(k) + '=' + encodeURIComponent(v));
      }
    });
    return this.stateUrl + '?' + qs.join('&');
  };

  Poller.prototype._tick = function(){
    if (this._stopped) return;
    var self = this;
    var headers = {
      'X-Requested-With': 'XMLHttpRequest',
      'Accept': 'application/json',
    };
    if (this._etag) headers['If-None-Match'] = this._etag;

    fetch(this._buildUrl(), { headers: headers, credentials: 'same-origin' })
      .then(function(r){
        if (r.status === 304) return null;
        if (r.status === 429) return null;
        if (!r.ok) throw new Error('HTTP ' + r.status);
        var et = r.headers.get('ETag');
        if (et) self._etag = et;
        return r.json();
      })
      .then(function(data){
        if (data) {
          try { self.onData(data); } catch(e){ console.error('[rt_poll onData]', e); }
        }
      })
      .catch(function(e){ console.warn('[rt_poll]', e); })
      .finally(function(){
        if (self._stopped) return;
        self._timer = setTimeout(function(){ self._tick(); }, jitter(self.interval));
      });
  };

  Poller.prototype.start = function(){
    var self = this;
    if (this.heartUrl) {
      heartbeat(this.heartUrl);
      this._heartTimer = setInterval(function(){ heartbeat(self.heartUrl); }, HEARTBEAT_MS);
    }
    this._tick();
    document.addEventListener('visibilitychange', function(){
      if (document.hidden) {
        if (self._timer) { clearTimeout(self._timer); self._timer = null; }
      } else {
        self._etag = null;
        self._tick();
        if (self.heartUrl) heartbeat(self.heartUrl);
      }
    });
  };

  Poller.prototype.stop = function(){
    this._stopped = true;
    if (this._timer) clearTimeout(this._timer);
    if (this._heartTimer) clearInterval(this._heartTimer);
  };

  Poller.prototype.updateParams = function(newParams){
    this.params = Object.assign({}, this.params, newParams);
    this._etag = null;
  };

  global.LottoRT = {
    create: function(opts){ return new Poller(opts); },
    start: function(opts){
      var p = new Poller(opts);
      p.start();
      return p;
    },
  };
})(window);
JS_EOF
log "rt_polling.js creado"

step "6/6 · Fix sidebar + verificación"
python3 << 'PYEOF'
from pathlib import Path
p = Path("/home/LottoBooM/templates/base.html")
src = p.read_text(encoding="utf-8")
n = src.count("usuarios:historial_movimientos")
if n:
    src = src.replace("usuarios:historial_movimientos", "roles:historial_movimientos")
    p.write_text(src, encoding="utf-8")
    print(f"✔ sidebar: {n} ocurrencia(s) corregida(s)")
else:
    print("○ sidebar ya estaba OK")
PYEOF

python3 manage.py check 2>&1 | tail -3

python3 manage.py shell << 'PYEOF'
from django.urls import reverse
try:
    print("✔", reverse('usuarios:api_heartbeat'))
    print("✔", reverse('usuarios:api_state'))
except Exception as e:
    print("✘ URLs:", e)
    raise SystemExit(1)

from usuarios.api_views import api_heartbeat, api_state
print("✔ Vistas importables")

from pathlib import Path
assert Path('/home/LottoBooM/templates/partials/_online_badge.html').exists()
assert Path('/home/LottoBooM/static/js/rt_polling.js').exists()
print("✔ Partial + JS en disco")
PYEOF

echo ""
echo -e "${G}🎉 PASO 2 COMPLETO${NC}"
echo "Backup: $BK"
