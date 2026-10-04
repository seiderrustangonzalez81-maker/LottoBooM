# -*- coding: utf-8 -*-
"""
REALTIME_ONLINE_V1 · Middleware que actualiza la actividad del usuario
en cada request autenticado. Permite calcular "en línea" con precisión.
"""
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin


class UserActivityMiddleware(MiddlewareMixin):
    """Actualiza UserActivity.last_activity en cada request autenticado."""

    def process_request(self, request):
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return None
        try:
            from roles.models import UserActivity
            UserActivity.objects.update_or_create(
                user=user,
                defaults={"last_activity": timezone.now()},
            )
        except Exception:
            # Nunca romper el request por culpa de la actividad
            pass
        return None
