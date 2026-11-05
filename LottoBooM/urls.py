import os
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponse
from django.views.decorators.cache import cache_page
from django.views.generic import RedirectView
from django.views.static import serve


def favicon(request):
    """Sirve /favicon.ico desde static/pwa/favicon.ico."""
    path = os.path.join(settings.BASE_DIR, "static", "pwa", "favicon.ico")
    return serve(request, "favicon.ico", os.path.dirname(path))



# ═══════════════════════════════════════════════════════════════
# SEO — robots.txt y sitemap
# ═══════════════════════════════════════════════════════════════
def robots_txt(request):
    """Sirve robots.txt desde static/."""
    from django.http import HttpResponse
    from django.conf import settings
    import os
    path = os.path.join(settings.BASE_DIR, 'static', 'robots.txt')
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return HttpResponse(f.read(), content_type='text/plain')
    except FileNotFoundError:
        return HttpResponse('User-agent: *\nAllow: /\n', content_type='text/plain')


def assetlinks_json(request):
    """Sirve assetlinks.json placeholder (PWA deep links)."""
    from django.http import JsonResponse
    return JsonResponse([], safe=False)


urlpatterns = [
    path('favicon.ico', favicon),
    path('robots.txt', robots_txt, name='robots'),
    path('.well-known/assetlinks.json', assetlinks_json, name='assetlinks'),
    path('admin/', admin.site.urls),
    path('', include('publico.urls')),           # tu home

    # ============================================================
    # RECUPERACIÓN DE CONTRASEÑA (Django built-in)
    # ============================================================
    # FIX_LOGIN_500_V1: redirigir /accounts/login/ al login custom (evita TemplateDoesNotExist)
    path('accounts/login/', RedirectView.as_view(url='/usuarios/login/', permanent=False)),
    path('accounts/logout/', RedirectView.as_view(url='/usuarios/login/', permanent=False)),
    path('accounts/', include('django.contrib.auth.urls')),   # ← NUEVA

    path('usuarios/', include('usuarios.urls')),
    path('jugadas/', include('jugadas.urls')),
    path('resultados/', include('resultados.urls')),
    path('sorteos/', include('sorteos.urls')),
    path('roles/', include('roles.urls')),

    # ✅ REGISTRA ESTOS NAMESPACES
    path('superadmin/', include('superadmin.urls', namespace='superadmin')),
    path('banco/', include('banco.urls', namespace='banco')),
    path('comercial/', include('comercial.urls', namespace='comercial')),

    # ============================================================
    # EVENTOS Y NOTIFICACIONES EN TIEMPO REAL
    # ============================================================
    path("events/", include("django_eventstream.urls")),
]


# ============================================================
# SERVIR ARCHIVOS MEDIA Y STATIC EN DESARROLLO (DEBUG=True)
# ============================================================
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)


# ============================================================
# 👇 FORZAR REGISTRO DE USER CON NUESTRA CLASE PERSONALIZADA
# ============================================================
# ESTE BLOQUE SE EJECUTA AL FINAL DE TODO, DESPUÉS DE QUE TODAS
# LAS APPS (INCLUIDO ALLAUTH) HAYAN REGISTRADO SUS ADMIN.
# ES EL MÉTODO MÁS SEGURO PARA SOBREESCRIBIR EL UserAdmin.

try:
    from django.contrib.auth.models import User
    from usuarios.admin import UserAdmin, PerfilAdmin
    from usuarios.models import Perfil

    # 1. Desregistrar si están registrados
    try:
        admin.site.unregister(User)
        print("✅ User desregistrado")
    except Exception as e:
        print(f"⚠️ User no estaba registrado o ya fue desregistrado: {e}")

    try:
        admin.site.unregister(Perfil)
        print("✅ Perfil desregistrado")
    except Exception as e:
        print(f"⚠️ Perfil no estaba registrado o ya fue desregistrado: {e}")

    # 2. Registrar con nuestras clases
    admin.site.register(User, UserAdmin)
    admin.site.register(Perfil, PerfilAdmin)

    # 3. Verificar el registro final
    print(f"🎉 User registrado con: {type(admin.site._registry[User]).__name__}")
    print(f"🎉 Perfil registrado con: {type(admin.site._registry[Perfil]).__name__}")

except Exception as e:
    print(f"❌ Error al registrar: {e}")