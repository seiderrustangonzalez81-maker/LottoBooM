# sorteos/urls.py
from django.urls import path
from . import views

app_name = 'sorteos'

urlpatterns = [
    # ============================================================
    # VISTAS PÚBLICAS (HTML)
    # ============================================================
    path('', views.lista_sorteos, name='lista_sorteos'),  # ✅ Esta es la lista
    path('<int:sorteo_id>/', views.detalle_sorteo, name='detalle_sorteo'),

    # ============================================================
    # APIS EN TIEMPO REAL (para frontend)
    # ============================================================
    path('api/data/', views.api_sorteos_data, name='api_sorteos_data'),

    # ============================================================
    # APIS REST PARA CONSUMO EXTERNO
    # ============================================================
    path('api/sorteos/', views.api_sorteos_list, name='api_sorteos_list'),
    path('api/sorteo/<int:sorteo_id>/', views.api_sorteo_detail, name='api_sorteo_detail'),
    path('api/sorteos/origen/<str:origen>/', views.api_sorteos_by_origin, name='api_sorteos_by_origin'),
    path('api/sorteos/estado/<str:estado>/', views.api_sorteos_by_status, name='api_sorteos_by_status'),
    path('api/sorteos/abiertos/', views.api_sorteos_abiertos, name='api_sorteos_abiertos'),
    path('api/sorteos/proximos/<int:horas>/', views.api_proximos_sorteos, name='api_proximos_sorteos'),  # ✅ Solo una vez

    # ============================================================
    # VISTAS CRUD (SOLO STAFF/SUPERADMIN)
    # ============================================================
    path('crear/', views.sorteo_crear, name='sorteo_crear'),
    path('<int:sorteo_id>/editar/', views.sorteo_editar, name='sorteo_editar'),
    path('<int:sorteo_id>/eliminar/', views.sorteo_eliminar, name='sorteo_eliminar'),

    # ============================================================
    # RESULTADOS (pendiente)
    # ============================================================
    path('resultado/crear/', views.resultado_crear, name='resultado_crear'),
    path('api/compartir-sorteos/', views.api_sorteos_compartir, name='api_sorteos_compartir'),  # FIX_COMPARTIR_SORTEOS_V1
]