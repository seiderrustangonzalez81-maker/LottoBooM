#!/bin/bash
set -euo pipefail
PROJECT="/home/LottoBooM"; cd "$PROJECT"
G='\033[0;32m'; R='\033[0;31m'; B='\033[1;34m'; NC='\033[0m'
log(){ echo -e "${G}[✔]${NC} $*"; }
err(){ echo -e "${R}[✘]${NC} $*"; exit 1; }
step(){ echo -e "\n${B}═══ $* ═══${NC}"; }

step "1/4 · Backup"
BK="_backup_fxon_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BK/usuarios" "$BK/LottoBooM"
cp usuarios/cache_utils.py "$BK/usuarios/" 2>/dev/null || true
cp LottoBooM/settings.py  "$BK/LottoBooM/" 2>/dev/null || true
echo "$BK" > .last_backup_fxon
log "backup: $BK"

step "2/4 · Fix contar_online()"
python3 << 'PYEOF'
from pathlib import Path
import re

p = Path("/home/LottoBooM/usuarios/cache_utils.py")
src = p.read_text(encoding="utf-8")

# Localizar la función contar_online completa
patron = re.compile(
    r"def contar_online\(user_ids=None\):.*?(?=\ndef |\Z)",
    re.DOTALL,
)

nueva = '''def contar_online(user_ids=None):
    """
    Cuenta cuántos están online.
    - user_ids=None → cuenta global (todos los users activos)
    - user_ids=[...] → cuenta solo esos
    Usa cache.get_many (1 sola llamada al backend).
    """
    if user_ids is None:
        from django.contrib.auth.models import User
        user_ids = list(User.objects.filter(is_active=True).values_list('id', flat=True))
    if not user_ids:
        return 0
    mapa = mapa_online(user_ids)
    return sum(1 for v in mapa.values() if v)
'''

src_new, n = patron.subn(nueva, src, count=1)
if n == 0:
    print("✘ No encontré contar_online")
    raise SystemExit(1)

# Verificar que mapa_online esté definida antes (debe estarlo)
if "def mapa_online" not in src_new:
    print("✘ Falta mapa_online")
    raise SystemExit(1)

p.write_text(src_new, encoding="utf-8")
print("✔ contar_online() reemplazada")

import ast
try:
    ast.parse(src_new)
    print("✔ Sintaxis OK")
except SyntaxError as e:
    print(f"✘ Error línea {e.lineno}: {e.msg}")
    raise SystemExit(1)
PYEOF

step "3/4 · Sesión optimizada"
python3 << 'PYEOF'
from pathlib import Path
import re

p = Path("/home/LottoBooM/LottoBooM/settings.py")
src = p.read_text(encoding="utf-8")

# ─── 1) SESSION_SAVE_EVERY_REQUEST = False ───
if "SESSION_SAVE_EVERY_REQUEST = False" in src:
    print("○ SESSION_SAVE_EVERY_REQUEST ya está en False")
else:
    src2 = re.sub(
        r"SESSION_SAVE_EVERY_REQUEST\s*=\s*True",
        "SESSION_SAVE_EVERY_REQUEST = False",
        src, count=1,
    )
    if src2 == src:
        print("⚠ No encontré SESSION_SAVE_EVERY_REQUEST = True — revisar manual")
    else:
        src = src2
        print("✔ SESSION_SAVE_EVERY_REQUEST = False")

# ─── 2) Añadir SESSION_ENGINE = cached_db si no está ───
# cached_db lee de cache (rápido), escribe en DB (persistente) — lo mejor de ambos
if "SESSION_ENGINE" not in src:
    print("⚠ No hay SESSION_ENGINE — se usará el default (db). OK.")
elif "sessions.backends.db" in src and "cached_db" not in src:
    # Mantener db (más simple, seguro con 1 worker)
    print("○ SESSION_ENGINE = db (correcto, sin cambios)")

p.write_text(src, encoding="utf-8")

# Confirmar
import re as _re
for line in src.splitlines():
    if "SESSION_" in line and not line.strip().startswith("#"):
        print(f"  {line.strip()}")
PYEOF

step "4/4 · Verificación"
python3 manage.py check 2>&1 | tail -3

python3 manage.py shell << 'PYEOF'
from django.contrib.auth.models import User
from usuarios.cache_utils import marcar_online, esta_online, contar_online, mapa_online
from django.core.cache import cache

# Limpiar y probar
cache.clear()

# Marcar 3 users
users = list(User.objects.filter(is_active=True)[:3])
for u in users:
    marcar_online(u)

# Verificar cada uno
for u in users:
    assert esta_online(u.id), f"user {u.id} debería estar online"
    print(f"  ✔ {u.username}: online={esta_online(u.id)}")

# contar_online global debe devolver al menos 3
n = contar_online()
print(f"  ✔ contar_online() = {n} (esperado ≥ 3)")
assert n >= 3, f"contar_online devolvió {n}, esperaba ≥ 3"

# mapa_online
mapa = mapa_online([u.id for u in users])
print(f"  ✔ mapa_online = {mapa}")

# Probar api_state(global) de nuevo
from django.test import RequestFactory
from usuarios.api_views import api_state
rf = RequestFactory()
req = rf.get('/usuarios/api/state/?scope=global')
req.user = users[0]
resp = api_state(req)
import json
body = json.loads(resp.content)
print(f"  ✔ api_state(global) online = {body['online']}")
assert body['online'] >= 3, f"api_state devolvió online={body['online']}"

print("\n✔ TODO OK")
PYEOF

echo ""
echo -e "${G}🎉 FIX APLICADO${NC}"
echo "Backup: $BK"
