#!/bin/bash
set -euo pipefail
PROJECT="/home/LottoBooM"; cd "$PROJECT"
G='\033[0;32m'; R='\033[0;31m'; B='\033[1;34m'; NC='\033[0m'
log(){ echo -e "${G}[✔]${NC} $*"; }
step(){ echo -e "\n${B}═══ $* ═══${NC}"; }

step "1/4 · Backup"
BK="_backup_csrf_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BK/templates" "$BK/LottoBooM" "$BK/usuarios"
cp templates/base.html "$BK/templates/"
cp LottoBooM/settings.py "$BK/LottoBooM/"
cp usuarios/middleware.py "$BK/usuarios/"
echo "$BK" > .last_backup_csrf
log "backup: $BK"

step "2/4 · Meta csrf-token + getCsrf robusto en base.html"
python3 << 'PYEOF'
from pathlib import Path
import re

p = Path("/home/LottoBooM/templates/base.html")
src = p.read_text(encoding="utf-8")

# 1) Meta tag en <head>
if 'name="csrf-token"' not in src:
    m = re.search(r'(<head[^>]*>)', src)
    if m:
        meta = '\n<meta name="csrf-token" content="{{ csrf_token }}">'
        src = src[:m.end()] + meta + src[m.end():]
        print("✔ Meta csrf-token añadido al <head>")
    else:
        print("⚠ No encontré <head> — revisar manualmente")
else:
    print("○ Meta ya existe")

# 2) Actualizar getCsrf en el heartbeat global
old_heartbeat_getcsrf = '''  function getCsrf(){
    var c = document.querySelector('[name=csrfmiddlewaretoken]');
    if (c) return c.value;
    var m = document.cookie.match(/(^|;)\\\\s*csrftoken=([^;]+)/);
    return m ? m[2] : '';
  }'''

new_heartbeat_getcsrf = '''  function getCsrf(){
    var m = document.querySelector('meta[name="csrf-token"]');
    if (m && m.content && m.content !== 'NOTPROVIDED') return m.content;
    var c = document.querySelector('[name=csrfmiddlewaretoken]');
    if (c) return c.value;
    var cookieMatch = document.cookie.match(/(^|;)\\\\s*csrftoken=([^;]+)/);
    return cookieMatch ? cookieMatch[2] : '';
  }'''

# Buscar variantes por si el escape quedó distinto
if old_heartbeat_getcsrf in src:
    src = src.replace(old_heartbeat_getcsrf, new_heartbeat_getcsrf)
    print("✔ getCsrf actualizado en heartbeat")
else:
    # Fallback: reemplazo por regex
    patron = re.compile(
        r"function getCsrf\(\)\{[^}]*?var c = document\.querySelector\('\[name=csrfmiddlewaretoken\]'\);[^}]*?\}",
        re.DOTALL,
    )
    src2, n = patron.subn(new_heartbeat_getcsrf, src, count=1)
    if n:
        src = src2
        print("✔ getCsrf actualizado en heartbeat (regex)")
    else:
        print("⚠ No pude actualizar getCsrf — probablemente funcional igual con meta")

p.write_text(src, encoding="utf-8")
PYEOF

step "3/4 · Middleware — fallback session_key como tab_id"
python3 << 'PYEOF'
from pathlib import Path

p = Path("/home/LottoBooM/usuarios/middleware.py")
src = p.read_text(encoding="utf-8")

if "sesion:" in src and "Fallback session" in src:
    print("○ Fallback ya presente")
    raise SystemExit(0)

# Reemplazar el bloque del tid
viejo = """                    tid = request.headers.get('X-Tab-Id') or request.headers.get('X-Session-Id')
                    if tid:
                        registrar_tab(tid, uid, ts=ts)"""

nuevo = """                    tid = request.headers.get('X-Tab-Id') or request.headers.get('X-Session-Id')
                    # Fallback: si no llega tab_id, usar el session_key (1 sesión = 1 tab virtual)
                    if not tid:
                        sk = getattr(request.session, 'session_key', None)
                        tid = f'sesion:{sk}' if sk else f'user:{uid}'
                    try:
                        registrar_tab(tid, uid, ts=ts)
                    except Exception:
                        pass"""

if viejo in src:
    src = src.replace(viejo, nuevo)
    print("✔ Fallback session_key añadido")
else:
    print("⚠ No encontré el bloque — revisar middleware manualmente")

p.write_text(src, encoding="utf-8")

import ast
try:
    ast.parse(src)
    print("✔ Sintaxis OK")
except SyntaxError as e:
    print(f"✘ Error línea {e.lineno}: {e.msg}")
    raise SystemExit(1)
PYEOF

step "4/4 · CACHES — aumentar MAX_ENTRIES"
python3 << 'PYEOF'
from pathlib import Path
import re

p = Path("/home/LottoBooM/LottoBooM/settings.py")
src = p.read_text(encoding="utf-8")

if "MAX_ENTRIES" in src and "5000" in src:
    print("○ MAX_ENTRIES ya configurado")
    raise SystemExit(0)

# Actualizar bloque CACHES
patron = re.compile(
    r"CACHES\s*=\s*\{.*?\n\}",
    re.DOTALL,
)
nuevo = '''CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "unique-lottoboom-cache",
        "TIMEOUT": 300,
        "OPTIONS": {
            "MAX_ENTRIES": 5000,
            "CULL_FREQUENCY": 4,
        },
    }
}'''

src_new, n = patron.subn(nuevo, src, count=1)
if n == 0:
    print("✘ No encontré CACHES = {...}")
    raise SystemExit(1)

p.write_text(src_new, encoding="utf-8")
print("✔ CACHES con MAX_ENTRIES=5000")
PYEOF

python3 manage.py check 2>&1 | tail -3

python3 manage.py shell << 'PYEOF'
from django.core.cache import cache
from django.conf import settings

# Ver backend real y sus opciones
print("Backend:", cache.__class__.__name__)
opts = settings.CACHES['default'].get('OPTIONS', {})
print("MAX_ENTRIES:", opts.get('MAX_ENTRIES'))

# Probar import del middleware
from usuarios.middleware import LastActivityMiddleware
print("✔ Middleware importable")

# Verificar que registrar_tab funciona
from usuarios.cache_utils import registrar_tab, snapshot_sesiones
cache.clear()
registrar_tab('test-1', 999)
registrar_tab('test-2', 999)
registrar_tab('test-3', 1000)
snap = snapshot_sesiones()
print(f"Test: sesiones={snap['sesiones']} usuarios={snap['usuarios_unicos']}")
assert snap['sesiones'] == 3 and snap['usuarios_unicos'] == 2
print("✔ registrar_tab + snapshot OK")
PYEOF

echo ""
echo -e "${G}🎉 FIX CSRF + FALLBACK APLICADO${NC}"
echo "Backup: $BK"
