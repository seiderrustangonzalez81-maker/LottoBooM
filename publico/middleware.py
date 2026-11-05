# -*- coding: utf-8 -*-
"""Middlewares de la app publico."""
from django.utils import timezone


class RegistrarVisitaMiddleware:
    """Registra cada visita única por sesión/día en VisitaDiaria."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            self._registrar_visita(request)
        except Exception:
            # Nunca romper la request por un fallo de analítica
            pass
        return self.get_response(request)

    def _registrar_visita(self, request):
        from .models import VisitaDiaria

        # Ignorar estáticos, media, admin, favicon, APIs
        path = request.path_info or '/'
        if path.startswith(('/static/', '/media/', '/admin/', '/favicon.ico',
                            '/events/', '/roles/api/')):
            return

        # Necesitamos sesión
        if not hasattr(request, 'session'):
            return
        if not request.session.session_key:
            request.session.save()

        session_key = request.session.session_key
        hoy = timezone.localdate()

        usuario = request.user if getattr(request, 'user', None) and \
            request.user.is_authenticated else None

        VisitaDiaria.objects.get_or_create(
            session_key=session_key,
            fecha=hoy,
            defaults={'usuario': usuario},
        )


class NoCacheHTMLMiddleware:
    """Prohíbe que el navegador cachee HTML dinámico."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        ct = response.get('Content-Type', '')
        if 'text/html' in ct:
            response['Cache-Control'] = (
                'no-store, no-cache, must-revalidate, '
                'max-age=0, private'
            )
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'
        return response


class ActualizarUltimaActividadMiddleware:
    """Actualiza Perfil.last_activity cada N segundos del usuario autenticado."""

    # Actualizar solo si pasó >60s desde la última (para no saturar BD)
    INTERVALO_SEGUNDOS = 60

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            self._actualizar(request)
        except Exception:
            pass
        return self.get_response(request)

    def _actualizar(self, request):
        from django.utils import timezone
        from datetime import timedelta
        from usuarios.models import Perfil

        u = getattr(request, 'user', None)
        if not u or not u.is_authenticated:
            return

        ahora = timezone.now()
        perfil = Perfil.objects.filter(usuario=u).only('id', 'last_activity').first()
        if not perfil:
            return

        if perfil.last_activity is None or \
                (ahora - perfil.last_activity) > timedelta(seconds=self.INTERVALO_SEGUNDOS):
            Perfil.objects.filter(pk=perfil.pk).update(last_activity=ahora)
