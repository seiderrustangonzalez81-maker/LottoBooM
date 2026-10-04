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


# ═══════════════════════════════════════════════════════════════
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
