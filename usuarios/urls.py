# usuarios/urls.py
# -*- coding: utf-8 -*-
from django.urls import path, include  # ✅ AÑADIDO: include
from . import views
from . import api_views

app_name = 'usuarios'

urlpatterns = [
    path('api/offline/', api_views.api_offline, name='api_offline'),
    path('api/heartbeat/', api_views.api_heartbeat, name='api_heartbeat'),
    path('api/state/',     api_views.api_state,     name='api_state'),

    path('mis-movimientos/', views.mis_movimientos, name='mis_movimientos'),
    # ============================================================
    # AUTENTICACIÓN
    # ============================================================
    path('registro/', views.registro_view, name='registro'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # ============================================================
    # AUTENTICACIÓN SOCIAL (Google, etc.)
    # 🔹 DESACTIVADO TEMPORALMENTE: requiere django-allauth
    # ============================================================
    # path('accounts/', include('allauth.urls')),  # Comentado hasta configurar allauth

    # ============================================================
    # PERFIL
    # ============================================================
    path('perfil/', views.perfil_cliente, name='perfil_cliente'),
    path('editar-perfil/', views.editar_perfil, name='editar_perfil'),
    path('mis-fondos/', views.mis_fondos, name='mis_fondos'),

    # ============================================================
    # VÍAS DE PAGO (redirección a roles)
    # ============================================================
    path('mis-vias-pago/', views.mis_vias_pago, name='mis_vias_pago'),

    # ============================================================
    # RECARGAS Y RETIROS (solicitudes del usuario)
    # ============================================================
    path('solicitar-recarga/', views.solicitar_recarga, name='solicitar_recarga'),
    path('solicitar-retiro/', views.solicitar_retiro, name='solicitar_retiro'),

    # ============================================================
    # CONFIRMAR/RECHAZAR RECARGAS (para gestores)
    # ============================================================
    path('confirmar-recarga/<int:movimiento_id>/', views.confirmar_recarga, name='confirmar_recarga'),
    path('rechazar-recarga/<int:movimiento_id>/', views.rechazar_recarga, name='rechazar_recarga'),

    # ============================================================
    # SOLICITUDES Y MOVIMIENTOS
    # ============================================================
    path('solicitudes-pendientes/', views.solicitudes_pendientes, name='solicitudes_pendientes'),
    path('historial-movimientos/', views.historial_movimientos, name='historial_movimientos'),

    # ============================================================
    # ESTADÍSTICAS Y REFERIDOS
    # ============================================================
    path('estadisticas/', views.estadisticas_cliente, name='estadisticas_cliente'),
    path('referidos/', views.referidos_cliente, name='referidos_cliente'),
    path('promociones/', views.promociones_cliente, name='promociones_cliente'),

    # ============================================================
    # APIS
    # ============================================================
    path('api/buscar-bancos-comerciales/', views.api_buscar_bancos_comerciales, name='api_buscar_bancos_comerciales'),
    path('api/buscar-destinatarios/', views.api_buscar_destinatarios, name='api_buscar_destinatarios'),

    # ============================================================
    # DASHBOARD REDIRECT
    # ============================================================
    path('dashboard/', views.redirect_dashboard, name='dashboard'),
    path('mis-limites/',      views.mis_limites,          name='mis_limites'),
    path('api/mis-limites/',  views.api_mis_limites_data, name='api_mis_limites_data'),
]