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
