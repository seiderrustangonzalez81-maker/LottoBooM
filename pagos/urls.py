from django.urls import path
from . import views

app_name = 'pagos'

urlpatterns = [
    path('mis-pagos/', views.mis_pagos, name='mis_pagos'),
    path('crear/', views.crear, name='crear'),
    path('detalle/<int:pk>/', views.detalle, name='detalle'),
    path('gestionar/', views.gestionar, name='gestionar'),
    path('cambiar-estado/<int:pk>/', views.cambiar_estado, name='cambiar_estado'),
]