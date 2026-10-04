#!/bin/bash
set -euo pipefail
PROJECT="/home/LottoBooM"; cd "$PROJECT"
G='\033[0;32m'; R='\033[0;31m'; B='\033[1;34m'; NC='\033[0m'
log(){ echo -e "${G}[✔]${NC} $*"; }
step(){ echo -e "\n${B}═══ $* ═══${NC}"; }

step "1/4 · Backup"
BK="_backup_ses_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BK/usuarios" "$BK/static/js"
cp usuarios/middleware.py "$BK/usuarios/" 2>/dev/null || true
cp usuarios/cache_utils.py "$BK/usuarios/" 2>/dev/null || true
cp usuarios/api_views.py "$BK/usuarios/" 2>/dev/null || true
cp static/js/rt_polling.js "$BK/static/js/" 2>/dev/null || true
echo "$BK" > .last_backup_ses
log "backup: $BK"

step "2/4 · Middleware — capturar tab_id y registrar sesión"
python3 << 'PYEOF'
from pathlib import Path

p = Path("/home/LottoBooM/usuarios/middleware.py")
src = p.read_text(encoding="utf-8")

if "online:tab:" in src:
    print("○ Middleware ya registra tab_id")
    raise SystemExit(0)

nuevo_middleware = '''# usuarios/middleware.py
"""
LastActivityMiddleware — Marca actividad del usuario en cache (rápido).
- Registra actividad por USUARIO (para badge online/offline).
- Registra actividad por TAB_ID (para contar sesiones/pestañas activas).
- Actualiza Perfil.last_activity en BD con throttle (5 min).
"""
from django.utils import timezone
from django.core.cache import cache

ONLINE_USER_KEY = 'online:u:{uid}'      # timestamp
ONLINE_TAB_KEY  = 'online:tab:{tid}'    # {'uid': N, 'ts': ts}
ONLINE_TTL      = 300
BD_THROTTLE_SG  = 300
CACHE_THROTTLE_SG = 20
SESSION_KEY     = '_la_sync'
SESSION_BD_KEY  = '_la_bd_sync'


class LastActivityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            try:
                ahora = timezone.now()
                ts = ahora.timestamp()
                uid = request.user.id

                # ── Cache: throttle 20s ──
                last_cache = request.session.get(SESSION_KEY, 0)
                if ts - last_cache > CACHE_THROTTLE_SG:
                    # 1) Key por usuario (para badge)
                    cache.set(ONLINE_USER_KEY.format(uid=uid), ts, timeout=ONLINE_TTL)

                    # 2) Key por tab_id (para contador de sesiones)
                    tid = request.headers.get('X-Tab-Id') or request.headers.get('X-Session-Id')
                    if tid:
                        tid = str(tid)[:64]  # sanear longitud
                        cache.set(
                            ONLINE_TAB_KEY.format(tid=tid),
                            {'uid': uid, 'ts': ts},
                            timeout=ONLINE_TTL,
                        )
                    request.session[SESSION_KEY] = ts

                # ── BD: throttle 5 min ──
                last_bd = request.session.get(SESSION_BD_KEY, 0)
                if ts - last_bd > BD_THROTTLE_SG:
                    try:
                        from .models import Perfil
                        Perfil.objects.filter(user_id=uid).update(last_activity=ahora)
                        request.session[SESSION_BD_KEY] = ts
                    except Exception:
                        pass
            except Exception:
                pass

        return self.get_response(request)
'''

p.write_text(nuevo_middleware, encoding="utf-8")
print("✔ Middleware actualizado con tab_id")

import ast
try:
    ast.parse(nuevo_middleware)
    print("✔ Sintaxis OK")
except SyntaxError as e:
    print(f"✘ Error línea {e.lineno}: {e.msg}")
    raise SystemExit(1)
PYEOF

step "3/4 · cache_utils — contar sesiones y usuarios únicos"
python3 << 'PYEOF'
from pathlib import Path
import re

p = Path("/home/LottoBooM/usuarios/cache_utils.py")
src = p.read_text(encoding="utf-8")

# Añadir al final las nuevas funciones
nuevas = '''

# ═══════════════════════════════════════════════════════════════
# SESIONES ACTIVAS (una por pestaña/dispositivo)
# ═══════════════════════════════════════════════════════════════
TAB_KEY = 'online:tab:{tid}'


def _backend_interno():
    """Devuelve el backend real de LocMemCache (no el ConnectionProxy)."""
    try:
        from django.core.cache import caches
        return caches['default']
    except Exception:
        return None


def snapshot_sesiones(ventana_sg=ONLINE_VENTANA_SG):
    """
    Lee todos los tab_keys activos en el cache y devuelve:
      {
        'sesiones': N,             # total de sesiones activas
        'usuarios_unicos': M,      # usuarios distintos
        'por_usuario': {uid: count},
        'user_ids_online': [...]
      }
    """
    resultado = {
        'sesiones': 0,
        'usuarios_unicos': 0,
        'por_usuario': {},
        'user_ids_online': [],
    }
    backend = _backend_interno()
    if not backend:
        return resultado

    # LocMemCache: acceso directo al dict interno
    cache_interno = getattr(backend, '_cache', None)
    if not isinstance(cache_interno, dict):
        return resultado

    ahora = timezone.now().timestamp()
    uids = set()
    por_usuario = {}

    for k, v in list(cache_interno.items()):
        if not isinstance(k, str) or not k.startswith('online:tab:'):
            continue
        if not isinstance(v, dict):
            continue
        ts = v.get('ts')
        uid = v.get('uid')
        if not isinstance(ts, (int, float)) or not isinstance(uid, int):
            continue
        if (ahora - ts) > ventana_sg:
            continue
        resultado['sesiones'] += 1
        uids.add(uid)
        por_usuario[uid] = por_usuario.get(uid, 0) + 1

    resultado['usuarios_unicos'] = len(uids)
    resultado['por_usuario'] = por_usuario
    resultado['user_ids_online'] = sorted(uids)
    return resultado


def contar_sesiones_activas(ventana_sg=ONLINE_VENTANA_SG):
    return snapshot_sesiones(ventana_sg)['sesiones']


def contar_usuarios_unicos_online(ventana_sg=ONLINE_VENTANA_SG):
    return snapshot_sesiones(ventana_sg)['usuarios_unicos']
'''

if "def snapshot_sesiones" in src:
    print("○ cache_utils ya tiene snapshot_sesiones")
    raise SystemExit(0)

src += nuevas
p.write_text(src, encoding="utf-8")
print("✔ cache_utils: snapshot_sesiones, contar_sesiones_activas, contar_usuarios_unicos_online")

import ast
try:
    ast.parse(src)
    print("✔ Sintaxis OK")
except SyntaxError as e:
    print(f"✘ Error línea {e.lineno}: {e.msg}")
    raise SystemExit(1)
PYEOF

# Actualizar _state_global para incluir sesiones
python3 << 'PYEOF'
from pathlib import Path
import re

p = Path("/home/LottoBooM/usuarios/api_views.py")
src = p.read_text(encoding="utf-8")

# Actualizar import
if "snapshot_sesiones" not in src.split("def _rate_limited")[0]:
    src = src.replace(
        "from usuarios.cache_utils import (\n    marcar_online, esta_online, mapa_online, contar_online,\n    last_activity_cache,\n)",
        "from usuarios.cache_utils import (\n    marcar_online, esta_online, mapa_online, contar_online,\n    last_activity_cache, snapshot_sesiones,\n)",
    )

# Reemplazar _state_global
patron = re.compile(r"def _state_global\(user\):.*?(?=\ndef |\Z)", re.DOTALL)
nuevo = '''def _state_global(user):
    """
    Contadores globales para el sidebar.
    Devuelve tanto usuarios únicos como sesiones activas (pestañas/dispositivos).
    """
    snap = snapshot_sesiones()
    total_users = User.objects.filter(is_active=True).count()
    return {
        'success': True,
        'online': snap['usuarios_unicos'],   # ← compat con código existente
        'sesiones': snap['sesiones'],         # ← NUEVO: pestañas/dispositivos
        'usuarios_unicos': snap['usuarios_unicos'],
        'total': total_users,
    }
'''

src_new, n = patron.subn(nuevo, src, count=1)
if n == 0:
    print("✘ No encontré _state_global")
    raise SystemExit(1)

p.write_text(src_new, encoding="utf-8")
print("✔ _state_global actualizado con sesiones")

import ast
try:
    ast.parse(src_new)
    print("✔ Sintaxis OK")
except SyntaxError as e:
    print(f"✘ Error línea {e.lineno}: {e.msg}")
    raise SystemExit(1)
PYEOF

step "4/4 · rt_polling.js — enviar X-Tab-Id en cada heartbeat"
python3 << 'PYEOF'
from pathlib import Path
import re

p = Path("/home/LottoBooM/static/js/rt_polling.js")
src = p.read_text(encoding="utf-8")

if "X-Tab-Id" in src:
    print("○ JS ya envía X-Tab-Id")
    raise SystemExit(0)

# Añadir función getTabId
nueva_func = '''
  function getTabId(){
    var k = 'lottort_tab_id';
    var v;
    try { v = sessionStorage.getItem(k); } catch(_){}
    if (!v) {
      try {
        v = (window.crypto && crypto.randomUUID)
          ? crypto.randomUUID()
          : 'tab-' + Date.now() + '-' + Math.random().toString(36).slice(2, 10);
        sessionStorage.setItem(k, v);
      } catch(_) {
        v = 'tab-' + Date.now() + '-' + Math.random().toString(36).slice(2, 10);
      }
    }
    return v;
  }

'''

# Insertar getTabId antes de heartbeat()
patron = re.compile(r"(\n\s*function heartbeat\(url\)\{)", re.MULTILINE)
src, n = patron.subn(nueva_func + r"\1", src, count=1)
if n == 0:
    print("✘ No encontré la función heartbeat()")
    raise SystemExit(1)

# Añadir X-Tab-Id a los headers del heartbeat
src = src.replace(
    "headers: { 'X-CSRFToken': getCsrf(), 'X-Requested-With': 'XMLHttpRequest' },",
    "headers: {\n        'X-CSRFToken': getCsrf(),\n        'X-Tab-Id': getTabId(),\n        'X-Requested-With': 'XMLHttpRequest',\n      },",
)

# También añadir X-Tab-Id al polling de state (para que el middleware registre la sesión aunque no haya heartbeat)
# Los GET también pueden actualizar last_activity
src = src.replace(
    "headers['X-Requested-With'] = 'XMLHttpRequest';",
    "headers['X-Requested-With'] = 'XMLHttpRequest';\n    headers['X-Tab-Id'] = getTabId();",
)
# Algunas versiones tienen otra forma:
src = src.replace(
    "'X-Requested-With': 'XMLHttpRequest',\n      'Accept': 'application/json',",
    "'X-Requested-With': 'XMLHttpRequest',\n      'X-Tab-Id': getTabId(),\n      'Accept': 'application/json',",
)

p.write_text(src, encoding="utf-8")
print("✔ rt_polling.js: envía X-Tab-Id")

# Verificación
if "X-Tab-Id" in src and "getTabId" in src:
    print("✔ Confirmado")
else:
    print("⚠ Revisar manualmente")
PYEOF

# Actualizar el template lista-clientes para mostrar ambos contadores
python3 << 'PYEOF'
from pathlib import Path

p = Path("/home/LottoBooM/roles/templates/roles/lista_clientes.html")
if not p.exists():
    print("⚠ No hay lista_clientes.html")
    raise SystemExit(0)

src = p.read_text(encoding="utf-8")
if "lottort-sesiones" in src:
    print("○ KPIs ya incluyen sesiones")
    raise SystemExit(0)

# Actualizar la sección KPIs inyectada previamente
old_online_kpi = '<span class="lottort-kpi-live"><span class="lv-num lv-on" data-rt="online">—</span><span style="font-size:.7rem;color:#64748b;">/&nbsp;<span data-rt="total">—</span></span></span>'
new_online_kpi = '<span class="lottort-kpi-live lottort-sesiones">'
new_online_kpi += '<span class="lv-num lv-on" data-rt="sesiones">—</span>'
new_online_kpi += '<span style="font-size:.7rem;color:#64748b;">&nbsp;sesiones</span>'
new_online_kpi += '<span style="font-size:.65rem;color:#94a3b8;margin-left:6px;">·&nbsp;'
new_online_kpi += '<span data-rt="usuarios_unicos">—</span>&nbsp;usuarios</span>'
new_online_kpi += '</span>'

if old_online_kpi in src:
    src = src.replace(old_online_kpi, new_online_kpi)
    print("✔ KPI online reformulado a 'sesiones · usuarios'")
else:
    print("⚠ No encontré el KPI online original — revisar manualmente")

# Actualizar el JS para pintar el nuevo formato
src = src.replace(
    "var o = kpis.querySelector('[data-rt=\"online\"]'); if (o) o.textContent = data.online;",
    "var s = kpis.querySelector('[data-rt=\"sesiones\"]'); if (s) s.textContent = data.sesiones || 0;\n        var u = kpis.querySelector('[data-rt=\"usuarios_unicos\"]'); if (u) u.textContent = data.usuarios_unicos || 0;",
)

p.write_text(src, encoding="utf-8")
print("✔ Template actualizado")
PYEOF

# Verificación final
python3 manage.py check 2>&1 | tail -3

python3 manage.py shell << 'PYEOF'
from usuarios.cache_utils import snapshot_sesiones, contar_sesiones_activas, contar_usuarios_unicos_online
from django.core.cache import cache, caches

cache.clear()
print("Backend real:", caches['default'].__class__.__name__)

# Simular 3 tabs del mismo user + 1 tab de otro
from django.utils import timezone
ts = timezone.now().timestamp()
cache.set('online:tab:tab-A', {'uid': 1, 'ts': ts}, timeout=300)
cache.set('online:tab:tab-B', {'uid': 1, 'ts': ts}, timeout=300)
cache.set('online:tab:tab-C', {'uid': 1, 'ts': ts}, timeout=300)
cache.set('online:tab:tab-D', {'uid': 2, 'ts': ts}, timeout=300)

snap = snapshot_sesiones()
print(f"Sesiones activas: {snap['sesiones']} (esperado 4)")
print(f"Usuarios únicos: {snap['usuarios_unicos']} (esperado 2)")
print(f"Por usuario: {snap['por_usuario']}")
assert snap['sesiones'] == 4
assert snap['usuarios_unicos'] == 2
print("✔ snapshot_sesiones funciona")
PYEOF

echo ""
echo -e "${G}🎉 CONTADOR DE SESIONES LISTO${NC}"
echo "Backup: $BK"
