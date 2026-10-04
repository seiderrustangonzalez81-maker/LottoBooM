# ubicaciones/urls.py

from django.urls import path
from . import views

app_name = 'ubicaciones'

urlpatterns = [
    path('buscar/', views.buscar_ubicaciones, name='buscar_ubicaciones'),
    path('buscar/<str:telefono>/', views.buscar_ubicaciones, name='buscar_ubicaciones'),
    path('mis-ubicaciones/', views.mis_ubicaciones, name='mis_ubicaciones'),
    path('registrar/', views.registrar_ubicacion, name='registrar_ubicacion'),
    path('<int:ubicacion_id>/editar/', views.editar_ubicacion, name='editar_ubicacion'),
    path('<int:ubicacion_id>/eliminar/', views.eliminar_ubicacion, name='eliminar_ubicacion'),
]