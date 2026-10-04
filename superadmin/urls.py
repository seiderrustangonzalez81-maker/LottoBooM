from django.urls import path
from . import views

app_name = 'superadmin'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('usuarios/', views.usuarios_list, name='usuarios_list'),
    path('usuario/<int:usuario_id>/editar/', views.usuario_editar, name='usuario_editar'),
    path('sorteos/', views.sorteos_list, name='sorteos_list'),
    path('sorteo/crear/', views.sorteo_crear, name='sorteo_crear'),
    path('sorteo/<int:sorteo_id>/editar/', views.sorteo_editar, name='sorteo_editar'),
    path('jugadas/', views.jugadas_list, name='jugadas_list'),
    path('reporte-ventas/', views.reporte_ventas, name='reporte_ventas'),
    path('reporte-comisiones/', views.reporte_comisiones, name='reporte_comisiones'),
    path('gestion-dosis/', views.gestion_dosis, name='gestion_dosis'),
    path('gestion-limites/', views.gestion_limites, name='gestion_limites'),
    path('recargar-usuario/', views.recargar_usuario, name='recargar_usuario'),
    path('consumir-bono/<int:usuario_id>/', views.consumir_bono_referido, name='consumir_bono_referido'),
    path('api/notificaciones/count/', views.api_notificaciones_count, name='api_notificaciones_count'),
    path('api/notificaciones/recientes/', views.api_notificaciones_recientes, name='api_notificaciones_recientes'),
    path('usuarios/ascender/<int:usuario_id>/', views.usuario_ascender, name='usuario_ascender'),
]