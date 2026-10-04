from django.urls import path
from . import views

app_name = 'banco'

urlpatterns = [
    path('dashboard/', views.dashboard_banco, name='dashboard'),
    path('recargar-usuario/', views.recargar_usuario, name='recargar_usuario'),
    path('gestion-comerciales/', views.gestion_comerciales, name='gestion_comerciales'),
    path('gestion-limites/', views.gestion_limites_banco, name='gestion_limites'),
    path('gestion-dosis/', views.gestion_dosis_banco, name='gestion_dosis'),
    path('reporte-ventas/', views.reporte_ventas_banco, name='reporte_ventas'),
    path('resumen-rentabilidad/', views.resumen_rentabilidad, name='resumen_rentabilidad'),
    path('resumen-comercial/<int:comercial_id>/', views.resumen_comercial, name='resumen_comercial'),
    path('compartir-resumen/<str:token>/', views.compartir_resumen, name='compartir_resumen'),
]