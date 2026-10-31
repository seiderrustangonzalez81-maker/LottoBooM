from django.urls import path
from . import views

app_name = 'jugadas'

urlpatterns = [
    path('api/check-duplicados/', views.api_check_duplicados, name='api_check_duplicados'),
    # ============================================================
    # VISTAS PRINCIPALES
    # ============================================================
    path('apostar/', views.apostar, name='apostar'),
    path('superparlet/', views.superparlet, name='superparlet'),
    path('guardar-apuesta/', views.guardar_apuesta, name='guardar_apuesta'),
    path('mis-apuestas/', views.mis_apuestas, name='mis_apuestas'),
    path('mis-fondos/', views.mis_fondos, name='mis_fondos'),

    # ============================================================
    # APIs GENERALES
    # ============================================================
    path('api/sorteos-disponibles/', views.api_sorteos_disponibles, name='api_sorteos_disponibles'),
    path('api/configuracion-sorteo/', views.api_configuracion_sorteo, name='api_configuracion_sorteo'),
    path('api/forma-pago-cliente/', views.api_forma_pago_cliente, name='api_forma_pago_cliente'),
    path('api/sorteos-con-boleta/', views.api_sorteos_con_boleta, name='api_sorteos_con_boleta'),
    path('api/verificar-saldo/', views.api_verificar_saldo, name='api_verificar_saldo'),
    path('api/verificar-password/', views.api_verificar_password, name='api_verificar_password'),
    path('api/info-apuesta/', views.api_info_apuesta, name='api_info_apuesta'),
    path('api/jugada-detalle/', views.api_jugada_detalle, name='api_jugada_detalle'),
    path('api/cancelar-jugada/<int:jugada_id>/', views.api_cancelar_jugada, name='api_cancelar_jugada'),
    path('api/cancelar-boleta/<int:boleta_id>/', views.api_cancelar_boleta, name='api_cancelar_boleta'),
    path('api/duplicar-boleta/<int:boleta_id>/', views.api_duplicar_boleta, name='api_duplicar_boleta'),
    path('api/verificar-sorteo/<int:sorteo_id>/', views.api_verificar_sorteo, name='api_verificar_sorteo'),
    path('api/disponible-por-numero/', views.api_disponible_por_numero, name='api_disponible_por_numero'),
    path('api/crear-cliente/', views.api_crear_cliente, name='api_crear_cliente'),
    path('api/ver-password-cliente/<int:cliente_id>/', views.api_ver_password_cliente, name='api_ver_password_cliente'),

    # ============================================================
    # APIs DE POSTPAGO
    # ============================================================
    path('api/otorgar-postpago/', views.otorgar_postpago_view, name='otorgar_postpago'),
    path('api/liquidar-postpago/', views.liquidar_postpago_view, name='liquidar_postpago'),
    path('api/postpago-cliente/', views.api_postpago_cliente, name='api_postpago_cliente'),
]