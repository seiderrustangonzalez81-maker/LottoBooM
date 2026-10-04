# usuarios/middleware.py
"""
LastActivityMiddleware — Marca actividad del usuario en cache (rápido).
- Registra actividad por USUARIO (para badge online/offline).
- Registra actividad por TAB_ID (para contar sesiones/pestañas activas).
- Actualiza Perfil.last_activity en BD con throttle (5 min).
"""
from django.utils import timezone
from django.core.cache import cache
from .cache_utils import registrar_tab

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
                    # Fallback: si no llega tab_id, usar el session_key (1 sesión = 1 tab virtual)
                    if not tid:
                        sk = getattr(request.session, 'session_key', None)
                        tid = f'sesion:{sk}' if sk else f'user:{uid}'
                    try:
                        registrar_tab(tid, uid, ts=ts)
                    except Exception:
                        pass
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
