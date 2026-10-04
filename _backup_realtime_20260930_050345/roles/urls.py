# roles/urls.py
# -*- coding: utf-8 -*-
from django.urls import path
from . import views

app_name = 'roles'

urlpatterns = [
    path('historial-movimientos/', views.historial_movimientos, name='historial_movimientos'),
    # ============================================================
    # CUADRES Y VENTAS
    # ============================================================
    path('historial-cuadres/', views.historial_cuadres, name='historial_cuadres'),
    path('detalle-cuadre/<int:cuadre_id>/', views.detalle_cuadre, name='detalle_cuadre'),
    path('resumen-diario/<int:cuadre_id>/', views.resumen_diario, name='resumen_diario'),
    path('editar-cuadre/<int:cuadre_id>/', views.editar_cuadre, name='editar_cuadre'),
    path('historial-ventas/', views.historial_ventas, name='historial_ventas'),
    path('analisis-rendimiento/', views.analisis_rendimiento, name='analisis_rendimiento'),

    # ============================================================
    # NOTIFICACIONES
    # ============================================================
    path('notificaciones/', views.mis_notificaciones, name='notificaciones'),
    path('marcar-notificacion/<int:notificacion_id>/', views.marcar_notificacion_leida, name='marcar_notificacion'),
    path('marcar-todas-leidas/', views.marcar_todas_leidas, name='marcar_todas_leidas'),
    path('marcar-seleccionadas/', views.marcar_seleccionadas, name='marcar_seleccionadas'),

    # APIs de notificaciones (sin duplicados; APPEND_SLASH maneja / vs no-/)
    path('api/notificaciones/count/', views.contar_notificaciones_no_leidas, name='api_notificaciones_count'),
    path('api/notificaciones/recientes/', views.api_notificaciones_recientes, name='api_notificaciones_recientes'),
    path('api/notificaciones/nuevas/', views.api_notificaciones_nuevas, name='api_notificaciones_nuevas'),
    path('api/notificaciones/ultimo-id/', views.api_notificaciones_ultimo_id, name='api_notificaciones_ultimo_id'),
    path('api/notificaciones/', views.api_notificaciones, name='api_notificaciones'),
    path('api/asignar-rol-usuario/', views.asignar_rol_usuario, name='asignar_rol_usuario'),

    # ============================================================
    # GESTIÓN DE BANCOS Y SUSCRIPCIONES
    # ============================================================
    path('panel-bancos/', views.panel_bancos, name='panel_bancos'),
    path('editar-suscripcion/<int:suscripcion_id>/', views.editar_suscripcion, name='editar_suscripcion'),
    path('registrar-pago-banco/<int:suscripcion_id>/', views.registrar_pago_banco, name='registrar_pago_banco'),
    path('panel-suscripcion-banco/', views.panel_suscripcion_banco, name='panel_suscripcion_banco'),
    path('cambiar-tipo-pago/', views.cambiar_tipo_pago_banco, name='cambiar_tipo_pago'),

    # ============================================================
    # GESTIÓN DE USUARIOS (ASCENSOS/DESCENSOS)
    # ============================================================
    path('ascender-usuario/', views.ascender_usuario, name='ascender_usuario'),
    path('ascender-comercial/<int:user_id>/', views.ascender_a_comercial, name='ascender_a_comercial'),
    path('descender-cliente/<int:user_id>/', views.descender_a_cliente, name='descender_a_cliente'),

    # ============================================================
    # RECURSOS Y LÍMITES
    # ============================================================
    path('asignar-recursos/', views.asignar_recursos_banco, name='asignar_recursos_banco'),
    path('gestion-limites-dosis/', views.gestion_limites_dosis, name='gestion_limites_dosis'),
    path('gestiones/', views.gestiones_banco, name='gestiones_banco'),

    # ============================================================
    # ESTRUCTURA GLOBAL
    # ============================================================
    path('estructura-global/', views.estructura_global, name='estructura_global'),

    # ============================================================
    # SOBRE LÍMITES
    # ============================================================
    path('panel-sobrelimites/', views.panel_sobrelimites, name='panel_sobrelimites'),
    path('gestionar-sobrelimite/<int:sobrelimite_id>/<str:accion>/', views.gestionar_sobrelimite, name='gestionar_sobrelimite'),
    path('solicitar-compensacion/<int:sobrelimite_id>/', views.solicitar_compensacion_sobrelimite, name='solicitar_compensacion'),
    path('responder-compensacion/<int:sobrelimite_id>/<str:accion>/', views.responder_compensacion_sobrelimite, name='responder_compensacion'),

    # ============================================================
    # LISTA DE CLIENTES
    # ============================================================
    path('lista-clientes/', views.lista_clientes, name='lista_clientes'),

    # ============================================================
    # VÍAS DE PAGO
    # ============================================================
    path('mis-vias-pago/', views.mis_vias_pago, name='mis_vias_pago'),
    path('agregar-via-pago/', views.agregar_via_pago, name='agregar_via_pago'),
    path('editar-via-pago/<int:via_id>/', views.editar_via_pago, name='editar_via_pago'),
    path('eliminar-via-pago/<int:via_id>/', views.eliminar_via_pago, name='eliminar_via_pago'),

    # ============================================================
    # SOLICITUDES UNIFICADAS
    # ============================================================
    path('solicitar/<str:tipo>/', views.solicitar, name='solicitar'),
    path('gestionar-solicitudes/', views.gestionar_solicitudes, name='gestionar_solicitudes_todas'),
    path('gestionar-solicitudes/<str:tipo>/', views.gestionar_solicitudes, name='gestionar_solicitudes'),
    path('responder-solicitud/<str:tipo>/<int:solicitud_id>/<str:accion>/', views.responder_solicitud, name='responder_solicitud'),
    path('mis-solicitudes/', views.mis_solicitudes, name='mis_solicitudes_todas'),
    path('mis-solicitudes/<str:tipo>/', views.mis_solicitudes, name='mis_solicitudes'),
    path('recarga-directa/', views.recarga_directa, name='recarga_directa'),

    # ============================================================
    # POSTPAGOS
    # ============================================================
    path('gestionar-postpagos/', views.gestionar_postpagos, name='gestionar_postpagos'),
    path('mis-postpagos/', views.mis_postpagos, name='mis_postpagos'),
    path('api/postpagos/historial/<int:cliente_id>/', views.api_historial_postpagos, name='api_historial_postpagos'),

    # ============================================================
    # SUSCRIPCIONES (solicitudes de bancos)
    # ============================================================
    path('solicitar-cambios-suscripcion/', views.solicitar_cambios_suscripcion, name='solicitar_cambios_suscripcion'),
    path('gestionar-solicitudes-suscripcion/', views.gestionar_solicitudes_suscripcion, name='gestionar_solicitudes_suscripcion'),

    # ============================================================
    # CUADRE DIARIO
    # ============================================================
    path('cuadre/', views.cuadre_diario_view, name='cuadre_diario'),
    path('api/cuadre/actualizar/', views.api_actualizar_cuadre, name='api_actualizar_cuadre'),
    path('api/cuadre/cerrar/<int:cuadre_id>/', views.api_cerrar_cuadre, name='api_cerrar_cuadre'),
    path('api/cuadre/<int:cuadre_id>/transferencia/agregar/', views.agregar_transferencia, name='agregar_transferencia'),
    path('api/cuadre/<int:cuadre_id>/transferencia/<int:idx>/editar/', views.editar_transferencia, name='editar_transferencia'),
    path('api/cuadre/<int:cuadre_id>/transferencia/<int:idx>/eliminar/', views.eliminar_transferencia, name='eliminar_transferencia'),

    # ============================================================
    # COMISIONES
    # ============================================================
    path('comisiones/', views.gestionar_comisiones, name='gestionar_comisiones'),
    path('comisiones/guardar/<int:usuario_id>/', views.guardar_comision, name='guardar_comision'),

    # ============================================================
    # NÚMEROS RESTRINGIDOS
    # ============================================================
    path('gestion-numeros-restringidos/', views.gestion_numeros_restringidos, name='gestion_numeros_restringidos'),
    path('crear-numero-restringido/', views.crear_numero_restringido, name='crear_numero_restringido'),
    # ✅ FIX: usar <int:pk> para coincidir con la firma de la vista
    path('eliminar-numero-restringido/<int:pk>/', views.eliminar_numero_restringido, name='eliminar_numero_restringido'),

    # ============================================================
    # RUTA DE PRUEBA
    # ============================================================
    path('asignar-recursos-limites/', views.asignar_recursos_limites, name='asignar_recursos_limites'),
    path('test/', views.test, name='test'),
]