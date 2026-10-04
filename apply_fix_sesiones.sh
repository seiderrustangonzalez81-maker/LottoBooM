#!/bin/bash
set -euo pipefail
PROJECT="/home/LottoBooM"; cd "$PROJECT"
G='\033[0;32m'; R='\033[0;31m'; B='\033[1;34m'; NC='\033[0m'
log(){ echo -e "${G}[✔]${NC} $*"; }
step(){ echo -e "\n${B}═══ $* ═══${NC}"; }

step "1/3 · Backup"
BK="_backup_fixses_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BK/usuarios"
cp usuarios/cache_utils.py "$BK/usuarios/" 2>/dev/null || true
cp usuarios/middleware.py "$BK/usuarios/" 2>/dev/null || true
echo "$BK" > .last_backup_fixses
log "backup: $BK"

step "2/3 · Reescribir snapshot_sesiones con índice explícito"
python3 << 'PYEOF'
from pathlib import Path
import re

p = Path("/home/LottoBooM/usuarios/cache_utils.py")
src = p.read_text(encoding="utf-8")

# Localizar el bloque SESIONES ACTIVAS y reemplazarlo
patron = re.compile(
    r"# ═+\s*\n# SESIONES ACTIVAS.*?\Z",
    re.DOTALL,
)
if not patron.search(src):
    # Fallback: buscar desde "TAB_KEY =" hasta el final
    patron = re.compile(r"TAB_KEY = .*?\Z", re.DOTALL)
    if not patron.search(src):
        print("✘ No encontré el bloque SESIONES ACTIVAS")
        raise SystemExit(1)

nuevo = '''# ═══════════════════════════════════════════════════════════════
# SESIONES ACTIVAS (una por pestaña/dispositivo) — v2 con índice
# ═══════════════════════════════════════════════════════════════
TAB_KEY = 'online:tab:{tid}'
TAB_INDEX_KEY = 'online:tabs:index'  # dict: {tid: ts}  ← índice explícito


def _ahora_ts():
    return timezone.now().timestamp()


def registrar_tab(tab_id, user_id, ts=None):
    """
    Registra una sesión/pestaña activa.
    - Escribe el estado del tab.
    - Actualiza el índice global de tabs activos.
    """
    if not tab_id:
        return
    tab_id = str(tab_id)[:64]
    ts = ts or _ahora_ts()

    # 1) Estado del tab
    cache.set(TAB_KEY.format(tid=tab_id), {'uid': int(user_id), 'ts': ts}, timeout=ONLINE_VENTANA_SG + 60)

    # 2) Índice: {tid: {'uid': N, 'ts': ts}}
    idx = cache.get(TAB_INDEX_KEY) or {}
    if not isinstance(idx, dict):
        idx = {}
    idx[tab_id] = {'uid': int(user_id), 'ts': ts}

    # Limpieza: eliminar tabs viejos del índice (evita que crezca sin control)
    ahora = ts
    idx = {
        t: v for t, v in idx.items()
        if isinstance(v, dict) and isinstance(v.get('ts'), (int, float))
        and (ahora - v['ts']) <= ONLINE_VENTANA_SG
    }
    cache.set(TAB_INDEX_KEY, idx, timeout=ONLINE_VENTANA_SG + 120)


def snapshot_sesiones(ventana_sg=ONLINE_VENTANA_SG):
    """
    Devuelve el estado de sesiones activas.
    Usa el índice explícito (no depende de internals de LocMemCache).
    """
    resultado = {
        'sesiones': 0,
        'usuarios_unicos': 0,
        'por_usuario': {},
        'user_ids_online': [],
    }
    idx = cache.get(TAB_INDEX_KEY) or {}
    if not isinstance(idx, dict):
        return resultado

    ahora = _ahora_ts()
    uids = set()
    por_usuario = {}

    for tid, v in idx.items():
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

src_new = patron.sub(nuevo, src, count=1)
p.write_text(src_new, encoding="utf-8")
print("✔ cache_utils reescrito con índice explícito")

import ast
try:
    ast.parse(src_new)
    print("✔ Sintaxis OK")
except SyntaxError as e:
    print(f"✘ Error línea {e.lineno}: {e.msg}")
    raise SystemExit(1)
PYEOF

step "3/3 · Middleware usa registrar_tab()"
python3 << 'PYEOF'
from pathlib import Path
import re

p = Path("/home/LottoBooM/usuarios/middleware.py")
src = p.read_text(encoding="utf-8")

if "from .cache_utils import registrar_tab" in src or "registrar_tab(" in src:
    print("○ Middleware ya usa registrar_tab")
    raise SystemExit(0)

# Importar
if "from .cache_utils import" not in src:
    src = src.replace(
        "from django.core.cache import cache",
        "from django.core.cache import cache\nfrom .cache_utils import registrar_tab",
        1,
    )

# Reemplazar la escritura directa por la llamada al helper
src = src.replace(
    """                    tid = request.headers.get('X-Tab-Id') or request.headers.get('X-Session-Id')
                    if tid:
                        tid = str(tid)[:64]  # sanear longitud
                        cache.set(
                            ONLINE_TAB_KEY.format(tid=tid),
                            {'uid': uid, 'ts': ts},
                            timeout=ONLINE_TTL,
                        )""",
    """                    tid = request.headers.get('X-Tab-Id') or request.headers.get('X-Session-Id')
                    if tid:
                        registrar_tab(tid, uid, ts=ts)""",
)

p.write_text(src, encoding="utf-8")
print("✔ Middleware actualizado")

import ast
try:
    ast.parse(src)
    print("✔ Sintaxis OK")
except SyntaxError as e:
    print(f"✘ Error línea {e.lineno}: {e.msg}")
    raise SystemExit(1)
PYEOF

step "4/4 · Verificación"
python3 manage.py shell << 'PYEOF'
from usuarios.cache_utils import registrar_tab, snapshot_sesiones
from django.core.cache import cache

cache.clear()

# Simular 3 tabs del mismo user (1) + 1 tab de otro (2)
registrar_tab('tab-A', 1)
registrar_tab('tab-B', 1)
registrar_tab('tab-C', 1)
registrar_tab('tab-D', 2)

snap = snapshot_sesiones()
print(f"Sesiones activas: {snap['sesiones']} (esperado 4)")
print(f"Usuarios únicos: {snap['usuarios_unicos']} (esperado 2)")
print(f"Por usuario: {snap['por_usuario']}")

assert snap['sesiones'] == 4, f"esperaba 4, obtuve {snap['sesiones']}"
assert snap['usuarios_unicos'] == 2, f"esperaba 2, obtuve {snap['usuarios_unicos']}"
assert snap['por_usuario'] == {1: 3, 2: 1}

print("\n✔ TODO OK")
PYEOF

echo ""
echo -e "${G}🎉 FIX APLICADO${NC}"
echo "Backup: $BK"
