#!/bin/bash
set -euo pipefail
PROJECT="/home/LottoBooM"; cd "$PROJECT"
G='\033[0;32m'; B='\033[1;34m'; NC='\033[0m'
step(){ echo -e "\n${B}═══ $* ═══${NC}"; }

step "1/3 · Backup"
BK="_backup_hb_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BK/templates"
cp templates/base.html "$BK/templates/"
echo "$BK" > .last_backup_hb
echo -e "${G}[✔]${NC} backup: $BK"

step "2/3 · Inyectar heartbeat global en base.html"
python3 << 'PYEOF'
from pathlib import Path

p = Path("/home/LottoBooM/templates/base.html")
src = p.read_text(encoding="utf-8")

if "lottort-global-heartbeat" in src:
    print("○ Heartbeat global ya inyectado")
    raise SystemExit(0)

bloque = '''
{# ═══════ Heartbeat global — se ejecuta en TODAS las páginas ═══════ #}
<script id="lottort-global-heartbeat">
(function(){
  // Solo si el usuario está autenticado (el template lo garantiza)
  if (!document.body || document.body.dataset.auth === '0') return;

  var HEART_URL = "{% url 'usuarios:api_heartbeat' %}";
  var INTERVAL_MS = 90000;

  function getCsrf(){
    var c = document.querySelector('[name=csrfmiddlewaretoken]');
    if (c) return c.value;
    var m = document.cookie.match(/(^|;)\\s*csrftoken=([^;]+)/);
    return m ? m[2] : '';
  }
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

  function beat(){
    fetch(HEART_URL, {
      method: 'POST',
      credentials: 'same-origin',
      keepalive: true,
      headers: {
        'X-CSRFToken': getCsrf(),
        'X-Tab-Id': getTabId(),
        'X-Requested-With': 'XMLHttpRequest',
      },
    }).catch(function(){});
  }

  // Primer heartbeat inmediato + loop
  beat();
  setInterval(beat, INTERVAL_MS);

  // Al volver a la pestaña, latido inmediato
  document.addEventListener('visibilitychange', function(){
    if (!document.hidden) beat();
  });

  // Al cerrar la pestaña, avisar al server (best-effort)
  window.addEventListener('beforeunload', function(){
    try {
      if (navigator.sendBeacon) {
        var fd = new FormData();
        fd.append('tab_id', getTabId());
        fd.append('csrfmiddlewaretoken', getCsrf());
        navigator.sendBeacon("{% url 'usuarios:api_offline' %}", fd);
      }
    } catch(_){}
  });
})();
</script>
'''

# Insertar antes del cierre de </body>
idx = src.rfind("</body>")
if idx == -1:
    print("✘ No encontré </body>")
    raise SystemExit(1)
src = src[:idx] + bloque + src[idx:]
p.write_text(src, encoding="utf-8")
print("✔ Heartbeat global añadido")
PYEOF

step "3/3 · Endpoint /api/offline/ + marcar data-auth"
python3 << 'PYEOF'
from pathlib import Path

# 1) Endpoint offline
p = Path("/home/LottoBooM/usuarios/api_views.py")
src = p.read_text(encoding="utf-8")

if "def api_offline" not in src:
    extra = '''

@login_required
@require_POST
def api_offline(request):
    """
    Borra la sesión/tab del índice activo. Best-effort al cerrar pestaña.
    """
    from usuarios.cache_utils import TAB_INDEX_KEY, TAB_KEY
    tid = request.POST.get('tab_id') or request.headers.get('X-Tab-Id')
    if tid:
        tid = str(tid)[:64]
        cache.delete(TAB_KEY.format(tid=tid))
        idx = cache.get(TAB_INDEX_KEY) or {}
        if isinstance(idx, dict):
            idx.pop(tid, None)
            cache.set(TAB_INDEX_KEY, idx, timeout=600)
    return HttpResponse(status=204)
'''
    src += extra
    p.write_text(src, encoding="utf-8")
    print("✔ api_offline añadido")

import ast
try:
    ast.parse(src)
    print("✔ Sintaxis OK")
except SyntaxError as e:
    print(f"✘ Error línea {e.lineno}: {e.msg}")
    raise SystemExit(1)
PYEOF

# 2) URL
python3 << 'PYEOF'
from pathlib import Path
import re
p = Path("/home/LottoBooM/usuarios/urls.py")
src = p.read_text(encoding="utf-8")
if "api_offline" in src:
    print("○ URL offline ya registrada")
    raise SystemExit(0)

m = re.search(r"urlpatterns\s*=\s*\[", src)
src = src[:m.end()] + "\n    path('api/offline/', api_views.api_offline, name='api_offline')," + src[m.end():]
p.write_text(src, encoding="utf-8")
print("✔ URL offline registrada")
PYEOF

# 3) Añadir data-auth a <body> si no existe
python3 << 'PYEOF'
from pathlib import Path
import re
p = Path("/home/LottoBooM/templates/base.html")
src = p.read_text(encoding="utf-8")

if 'data-auth=' in src and '<body' in src:
    # Actualizar el atributo existente
    def repl(m):
        body = m.group(0)
        if 'data-auth=' in body:
            return body
        return body.replace('<body', '<body data-auth="{% if user.is_authenticated %}1{% else %}0{% endif %}"', 1)
    src2 = re.sub(r'<body[^>]*>', repl, src, count=1)
    if src2 != src:
        src = src2
        print("✔ data-auth añadido al <body>")
    else:
        print("○ data-auth ya estaba")
else:
    # Buscar <body ...>
    m = re.search(r'<body([^>]*)>', src)
    if m:
        attrs = m.group(1)
        new_tag = '<body data-auth="{% if user.is_authenticated %}1{% else %}0{% endif %}"' + attrs + '>'
        src = src.replace(m.group(0), new_tag, 1)
        print("✔ data-auth añadido al <body>")
    else:
        print("⚠ No encontré <body> en base.html")
        raise SystemExit(0)

p.write_text(src, encoding="utf-8")
PYEOF

python3 manage.py check 2>&1 | tail -3

python3 manage.py shell << 'PYEOF'
from django.urls import reverse
print("✔", reverse('usuarios:api_heartbeat'))
print("✔", reverse('usuarios:api_offline'))
from pathlib import Path
src = Path('/home/LottoBooM/templates/base.html').read_text()
assert 'lottort-global-heartbeat' in src, "falta heartbeat global"
assert 'data-auth' in src, "falta data-auth"
print("✔ base.html OK")
PYEOF

echo ""
echo -e "${G}🎉 HEARTBEAT GLOBAL LISTO${NC}"
echo "Backup: $BK"
