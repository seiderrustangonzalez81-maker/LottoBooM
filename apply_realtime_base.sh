#!/bin/bash
set -euo pipefail
PROJECT="/home/LottoBooM"; cd "$PROJECT"
G='\033[0;32m'; R='\033[0;31m'; Y='\033[0;33m'; B='\033[1;34m'; NC='\033[0m'
log(){ echo -e "${G}[✔]${NC} $*"; }
err(){ echo -e "${R}[✘]${NC} $*"; exit 1; }
step(){ echo -e "\n${B}═══ $* ═══${NC}"; }

step "1/6 · Backup"
BK="_backup_rt_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BK/usuarios" "$BK/LottoBooM"
for f in usuarios/views.py usuarios/urls.py usuarios/models.py LottoBooM/settings.py; do
  [ -f "$f" ] && cp "$f" "$BK/$f" && log "bk $f"
done
echo "$BK" > .last_backup_rt

step "2/6 · Campo last_activity en Perfil"
python3 << 'PYEOF'
from pathlib import Path
import re
p = Path("/home/LottoBooM/usuarios/models.py")
src = p.read_text(encoding="utf-8")
if "last_activity = models.DateTimeField" in src:
    print("○ last_activity ya existe")
    raise SystemExit(0)

# Buscar class Perfil y añadir el campo al final de sus campos
m = re.search(
    r"(class Perfil\(models\.Model\):.*?)(\n    class Meta:)",
    src, re.DOTALL,
)
if not m:
    print("✘ No encontré class Perfil")
    raise SystemExit(1)

campo = '''
    last_activity = models.DateTimeField(
        null=True, blank=True, db_index=True,
        verbose_name='Última actividad',
        help_text='Se actualiza con throttle. No escribir en cada request.'
    )
'''
src = src[:m.end(1)] + campo + src[m.end(1):]
p.write_text(src, encoding="utf-8")
print("✔ Campo last_activity añadido a Perfil")
PYEOF

python3 manage.py makemigrations usuarios --name add_last_activity_perfil 2>&1 | tail -5
python3 manage.py migrate usuarios 2>&1 | tail -3

step "3/6 · Middleware + Cache Utils"
cat > /home/LottoBooM/usuarios/middleware.py << 'PY_MW_EOF'
# usuarios/middleware.py
"""
LastActivityMiddleware — Marca actividad del usuario en cache (rápido)
y en BD con throttle (5 min) para auditoría. NO escribe BD en cada request.
"""
from django.utils import timezone
from django.core.cache import cache

ONLINE_KEY = 'online:u:{uid}'       # {timestamp: float}
ONLINE_TTL = 300                     # 5 min de margen
BD_THROTTLE_SG = 300                 # escribir en BD cada 5 min
CACHE_THROTTLE_SG = 30               # cache.set cada 30s
SESSION_KEY = '_la_sync'
SESSION_BD_KEY = '_la_bd_sync'


class LastActivityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            try:
                ahora = timezone.now()
                ts = ahora.timestamp()

                # 1) Cache: throttle 30s (evita cache.set en cada request)
                last_cache = request.session.get(SESSION_KEY, 0)
                if ts - last_cache > CACHE_THROTTLE_SG:
                    cache.set(ONLINE_KEY.format(uid=request.user.id), ts, timeout=ONLINE_TTL)
                    request.session[SESSION_KEY] = ts

                # 2) BD: throttle 5 min (auditoría, no crítico)
                last_bd = request.session.get(SESSION_BD_KEY, 0)
                if ts - last_bd > BD_THROTTLE_SG:
                    try:
                        from .models import Perfil
                        Perfil.objects.filter(user_id=request.user.id).update(last_activity=ahora)
                        request.session[SESSION_BD_KEY] = ts
                    except Exception:
                        pass
            except Exception:
                pass

        return self.get_response(request)
PY_MW_EOF
log "middleware.py creado"

cat > /home/LottoBooM/usuarios/cache_utils.py << 'PY_CU_EOF'
# usuarios/cache_utils.py
"""
Helpers de presencia online basados en cache (O(1), sin tocar BD).
"""
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta

ONLINE_KEY = 'online:u:{uid}'
ONLINE_VENTANA_SG = 300  # 5 min: si no hay actividad en este tiempo → offline
COUNT_CACHE_KEY = 'online:count:cache'
COUNT_CACHE_TTL = 10  # el contador global se cachea 10s


def marcar_online(user, ts=None):
    """Marca al user como activo ahora mismo."""
    if not user or not user.is_authenticated:
        return
    ts = ts or timezone.now().timestamp()
    cache.set(ONLINE_KEY.format(uid=user.id), ts, timeout=ONLINE_VENTANA_SG + 60)


def esta_online(user_id, ventana_sg=ONLINE_VENTANA_SG):
    """True si el user tuvo actividad en los últimos N segundos."""
    if not user_id:
        return False
    ts = cache.get(ONLINE_KEY.format(uid=user_id))
    if not ts:
        return False
    return (timezone.now().timestamp() - ts) <= ventana_sg


def last_activity_cache(user_id):
    """Devuelve datetime de la última actividad (cache), o None."""
    ts = cache.get(ONLINE_KEY.format(uid=user_id))
    if not ts:
        return None
    return timezone.datetime.fromtimestamp(ts, tz=timezone.get_current_timezone())


def mapa_online(user_ids, ventana_sg=ONLINE_VENTANA_SG):
    """
    Devuelve {user_id: bool} para una lista de IDs.
    Usa cache.get_many → 1 sola llamada al backend.
    """
    if not user_ids:
        return {}
    keys = {ONLINE_KEY.format(uid=uid): uid for uid in user_ids}
    ahora = timezone.now().timestamp()
    valores = cache.get_many(list(keys.keys()))
    resultado = {}
    for key, uid in keys.items():
        ts = valores.get(key)
        resultado[uid] = bool(ts and (ahora - ts) <= ventana_sg)
    return resultado


def contar_online(user_ids=None):
    """
    Cuenta cuántos están online.
    Si user_ids=None → cuenta global (todos los usuarios en cache).
    """
    if user_ids is not None:
        return sum(1 for v in mapa_online(user_ids).values() if v)
    # Global: leer todos los keys online:u:*
    try:
        from django.core.cache import caches
        backend = caches['default']
        # LocMemCache: acceso directo al dict interno (solo para global)
        if hasattr(backend, '_cache'):
            ahora = timezone.now().timestamp()
            n = 0
            for k, v in list(backend._cache.items()):
                if isinstance(k, str) and k.startswith('online:u:'):
                    if isinstance(v, (int, float)) and (ahora - v) <= ONLINE_VENTANA_SG:
                        n += 1
            return n
    except Exception:
        pass
    return 0


def marcar_offline(user_id):
    """Fuerza offline (ej: logout)."""
    cache.delete(ONLINE_KEY.format(uid=user_id))


def snapshot_online_por_grupo(grupos):
    """
    grupos: dict {nombre: [user_ids]}
    Devuelve {nombre: {'online': N, 'total': M}}
    """
    resultado = {}
    for nombre, ids in grupos.items():
        if not ids:
            resultado[nombre] = {'online': 0, 'total': 0}
            continue
        online_n = sum(1 for v in mapa_online(ids).values() if v)
        resultado[nombre] = {'online': online_n, 'total': len(ids)}
    return resultado
PY_CU_EOF
log "cache_utils.py creado"

step "4/6 · settings.py — CACHES"
python3 << 'PYEOF'
from pathlib import Path
import re
p = Path("/home/LottoBooM/LottoBooM/settings.py")
src = p.read_text(encoding="utf-8")

if "'default': {" in src and "LocMemCache" in src:
    print("○ CACHES ya configurado con LocMemCache")
    raise SystemExit(0)

# Buscar el final del archivo y añadir CACHES
if "CACHES = {" in src:
    print("○ CACHES ya existe — revisar manualmente")
    raise SystemExit(0)

bloque = '''

# ═══════════════════════════════════════════════════════════════
# CACHES — LocMemCache (PythonAnywhere Free, 1 worker)
# ═══════════════════════════════════════════════════════════════
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'lottoboom-online-cache',
        'TIMEOUT': 300,
        'OPTIONS': {
            'MAX_ENTRIES': 10000,
            'CULL_FREQUENCY': 3,
        },
    }
}
'''
src += bloque
p.write_text(src, encoding="utf-8")
print("✔ CACHES añadido a settings.py")
PYEOF

step "5/6 · Registrar middleware"
python3 << 'PYEOF'
from pathlib import Path
import re
p = Path("/home/LottoBooM/LottoBooM/settings.py")
src = p.read_text(encoding="utf-8")

if "usuarios.middleware.LastActivityMiddleware" in src:
    print("○ Middleware ya registrado")
    raise SystemExit(0)

# Buscar MIDDLEWARE = [...]
m = re.search(r"MIDDLEWARE\s*=\s*\[(.*?)\]", src, re.DOTALL)
if not m:
    print("✘ No encontré MIDDLEWARE = [...]")
    raise SystemExit(1)

cuerpo = m.group(1)
if "AuthenticationMiddleware" not in cuerpo:
    print("✘ No encontré AuthenticationMiddleware en MIDDLEWARE")
    raise SystemExit(1)

# Insertar después de AuthenticationMiddleware
lineas = cuerpo.split("\n")
nuevas = []
for ln in lineas:
    nuevas.append(ln)
    if "AuthenticationMiddleware" in ln:
        # Detectar indentación
        indent = re.match(r"^(\s*)", ln).group(1)
        nuevas.append(f"{indent}'usuarios.middleware.LastActivityMiddleware',")

src = src[:m.start(1)] + "\n".join(nuevas) + src[m.end(1):]
p.write_text(src, encoding="utf-8")
print("✔ Middleware registrado")
PYEOF

step "6/6 · Verificación"
python3 manage.py check 2>&1 | tail -3
python3 manage.py shell << 'PYEOF'
from django.core.cache import cache
from usuarios.cache_utils import marcar_online, esta_online, contar_online

# Test básico
cache.clear()
marcar_online(type('U', (), {'id': 999, 'is_authenticated': True})())
assert esta_online(999), "debería estar online"
assert not esta_online(1000), "no debería estar online"
print("✔ cache_utils funciona")

# Middleware importable
from usuarios.middleware import LastActivityMiddleware
print("✔ Middleware importable")
PYEOF

echo ""
echo -e "${G}🎉 INFRAESTRUCTURA BASE LISTA${NC}"
echo "Backup: $BK"
echo ""
echo "Para activar:"
echo "  1. PythonAnywhere → Web → Reload"
echo "  2. El middleware empieza a marcar 'last_activity' automáticamente"
echo "  3. Los endpoints AJAX los añadimos en el paso 2"
