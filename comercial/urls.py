from django.urls import path
from . import views

app_name = 'comercial'

urlpatterns = [
    # ============================================================
    # DASHBOARD Y PRINCIPAL
    # ============================================================
    path('dashboard/', views.dashboard_comercial, name='dashboard'),
    path('', views.dashboard_comercial, name='index'),  # Redirige a dashboard

    # ============================================================
    # VENTAS Y RENTABILIDAD
    # ============================================================
    # ⚠️ IMPORTANTE: el nombre debe ser 'resumen_ventas_comercial' para que coincida con el template
    path('resumen-ventas/', views.resumen_ventas_comercial, name='resumen_ventas_comercial'),
    path('resumen-ventas/<str:periodo>/', views.resumen_ventas_comercial, name='resumen_ventas_periodo'),

    # ============================================================
    # GESTIÓN DE CLIENTES Y RECARGAS
    # ============================================================
    path('recargar-usuario/', views.recargar_usuario, name='recargar_usuario'),
    path('clientes/', views.lista_clientes, name='lista_clientes'),
    path('historial-recargas/', views.historial_recargas, name='historial_recargas'),

    # ============================================================
    # COMISIONES Y FINANZAS
    # ============================================================
    path('mis-comisiones/', views.mis_comisiones, name='mis_comisiones'),
    path('resumen-financiero/', views.resumen_financiero, name='resumen_financiero'),

    # ============================================================
    # PERFIL Y CONFIGURACIÓN
    # ============================================================
    path('perfil/', views.perfil_comercial, name='perfil'),
    path('configuracion/', views.configuracion_comercial, name='configuracion'),
    path('mis-recursos/', views.mis_recursos_view, name='mis_recursos'),
]