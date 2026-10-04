from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('publico.urls')),           # tu home

    # ============================================================
    # RECUPERACIÓN DE CONTRASEÑA (Django built-in)
    # ============================================================
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