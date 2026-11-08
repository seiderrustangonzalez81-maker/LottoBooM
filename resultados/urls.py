from django.urls import path
from . import views

app_name = 'resultados'

urlpatterns = [
    path('', views.resultados_view, name='resultados'),
    path('crear/', views.crear_resultado, name='crear_resultado'),
    path('<int:resultado_id>/', views.detalle_resultado, name='detalle_resultado'),
    path('<int:resultado_id>/editar/', views.editar_resultado, name='editar_resultado'),
    path('<int:resultado_id>/eliminar/', views.eliminar_resultado, name='eliminar_resultado'),
    path('mis-premios/', views.mis_premios, name='mis_premios'),
    path('cobrar/<int:premio_id>/', views.solicitar_cobro, name='solicitar_cobro'),
    path('ganadores/', views.todos_los_ganadores, name='todos_los_ganadores'),

    # APIs
    path('api/sorteos-disponibles/', views.api_sorteos_disponibles, name='api_sorteos_disponibles'),
    path('api/recientes/', views.api_resultados_recientes, name='api_resultados_recientes'),
    path('api/config-sorteo/', views.api_configuracion_sorteo, name='api_configuracion_sorteo'),
    path('api/premios/<int:resultado_id>/', views.api_premios_por_resultado, name='api_premios_por_resultado'),
    path('api/resumen/<int:resultado_id>/', views.api_resumen_resultado, name='api_resumen_resultado'),
    path('api/guardar/', views.api_guardar_resultado, name='api_guardar_resultado'),
    path('api/resumen-filtrado/', views.api_resumen_filtrado, name='api_resumen_filtrado'),
    path('api/premios-sorteo/', views.api_premios_sorteo, name='api_premios_sorteo'),
    path('api/premios-todos/', views.api_premios_todos, name='api_premios_todos'),
    path('api/status/<int:resultado_id>/', views.api_resultado_status, name='api_resultado_status'),
]