from django.utils import timezone
from django.contrib.auth.models import User
from .models import VisitaDiaria


class RegistrarVisitaMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # 🔹 Filtro nuevo: no contar AJAX (polling de stats, guardar apuestas, etc)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return response

        rutas_excluidas = ('/static', '/media', '/admin')
        if any(request.path.startswith(ruta) for ruta in rutas_excluidas):
            return response

        hoy = timezone.now().date()

        if request.user.is_authenticated:
            # ✅ Cambio: usar filter().first() para evitar MultipleObjectsReturned
            existe = VisitaDiaria.objects.filter(
                usuario=request.user, fecha=hoy
            ).exists()
            if not existe:
                VisitaDiaria.objects.create(
                    usuario=request.user,
                    fecha=hoy,
                    session_key=request.session.session_key or '',
                    ip=self._get_ip(request),
                    user_agent=request.META.get('HTTP_USER_AGENT', '')[:255],
                )
        else:
            session_key = request.session.session_key
            if not session_key:
                request.session.save()
                session_key = request.session.session_key

            VisitaDiaria.objects.get_or_create(
                session_key=session_key,
                fecha=hoy,
                defaults={
                    'ip': self._get_ip(request),
                    'user_agent': request.META.get('HTTP_USER_AGENT', '')[:255],
                }
            )

        return response

    def _get_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '')


# ═══════════════════════════════════════════════════════════════
# MIDDLEWARE: Actualizar última actividad real
# ═══════════════════════════════════════════════════════════════

from django.utils import timezone


class ActualizarUltimaActividadMiddleware:
    """
    Actualiza User.last_login en cada request autenticado.
    Esto permite mostrar online/offline con base en actividad real,
    no solo en el momento del login.

    Optimización: solo escribe a DB si pasaron >= 30 segundos desde
    la última actualización, para no saturar con writes.
    """
    INTERVALO_SEGUNDOS = 30

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Actualizar ANTES de procesar la vista
        if hasattr(request, 'user') and request.user.is_authenticated:
            ahora = timezone.now()
            ultima = request.user.last_login
            if (not ultima) or ((ahora - ultima).total_seconds() >= self.INTERVALO_SEGUNDOS):
                # Update directo sin signals
                User.objects.filter(pk=request.user.pk).update(last_login=ahora)
                # Actualizar también en memoria para que la vista lo vea
                request.user.last_login = ahora

        response = self.get_response(request)
        return response

