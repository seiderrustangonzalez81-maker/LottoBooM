# roles/admin.py
# -*- coding: utf-8 -*-
from django.contrib import admin, messages
from django.contrib.auth.models import User
from django.db.models import Sum
from django.utils.html import format_html
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from .models import (
    Rol, Subordinacion, Fondo, MovimientoFondo, Comision, DosisPago,
    Bono, Deuda, Notificacion, CuadreDiario, Sobrelimite,
    LimiteApuesta, Prestamo, SuscripcionBanco, RecursoAsignado,
    ViaPago, SolicitudRecarga, SolicitudCobroPremio,
    RelacionClienteGestor, RelacionComercialBanco
)


# ============================================================
# HELPERS
# ============================================================
def _badge(texto, color='#6b7280'):
    """Genera un badge HTML pequeño con color de fondo."""
    return format_html(
        '<span style="background:{};color:#fff;padding:2px 8px;'
        'border-radius:10px;font-size:11px;text-transform:uppercase;'
        'font-weight:600;letter-spacing:0.3px;">{}</span>',
        color, texto
    )


# ============================================================
# ACCIONES MASIVAS — FONDOS
# ============================================================
@admin.action(description="💰 Sumar $10 al saldo")
def fondo_sumar_10(modeladmin, request, queryset):
    for f in queryset:
        f.monto = (f.monto or Decimal('0.00')) + Decimal('10.00')
        f.save(update_fields=['monto', 'actualizado_en'])
    messages.success(request, f"✅ +$10 aplicado a {queryset.count()} fondo(s).")


@admin.action(description="💸 Restar $10 al saldo")
def fondo_restar_10(modeladmin, request, queryset):
    for f in queryset:
        f.monto = (f.monto or Decimal('0.00')) - Decimal('10.00')
        f.save(update_fields=['monto', 'actualizado_en'])
    messages.warning(request, f"⚠️ -$10 aplicado a {queryset.count()} fondo(s).")


@admin.action(description="🔒 Desactivar fondos seleccionados")
def fondo_desactivar(modeladmin, request, queryset):
    total = queryset.update(activo=False)
    messages.success(request, f"✅ {total} fondo(s) desactivado(s).")


@admin.action(description="🔓 Reactivar fondos seleccionados")
def fondo_reactivar(modeladmin, request, queryset):
    total = queryset.update(activo=True)
    messages.success(request, f"✅ {total} fondo(s) reactivado(s).")


# ============================================================
# ACCIONES MASIVAS — BONOS
# ============================================================
@admin.action(description="✅ Activar bonos")
def bono_activar(modeladmin, request, queryset):
    total = queryset.update(estado='activo')
    messages.success(request, f"✅ {total} bono(s) activado(s).")


@admin.action(description="🚫 Marcar como agotados")
def bono_agotar(modeladmin, request, queryset):
    total = queryset.update(estado='agotado')
    messages.success(request, f"✅ {total} bono(s) marcado(s) como agotado(s).")


@admin.action(description="🗑️ Vaciar saldo (dejar en $0)")
def bono_vaciar(modeladmin, request, queryset):
    total = queryset.update(saldo_restante=Decimal('0.00'))
    messages.warning(request, f"⚠️ {total} bono(s) con saldo $0.")


# ============================================================
# ACCIONES MASIVAS — MOVIMIENTOS
# ============================================================
@admin.action(description="✅ Marcar movimientos como confirmados")
def mov_confirmar(modeladmin, request, queryset):
    total = queryset.update(estado='confirmado')
    messages.success(request, f"✅ {total} movimiento(s) confirmado(s).")


@admin.action(description="❌ Marcar movimientos como cancelados")
def mov_cancelar(modeladmin, request, queryset):
    total = queryset.update(estado='cancelado')
    messages.warning(request, f"⚠️ {total} movimiento(s) cancelado(s).")


# ============================================================
# ACCIONES MASIVAS — NOTIFICACIONES
# ============================================================
@admin.action(description="📬 Marcar como leídas")
def notif_leidas(modeladmin, request, queryset):
    total = queryset.update(leido=True, leido_en=timezone.now())
    messages.success(request, f"✅ {total} notificación(es) marcada(s) como leída(s).")


@admin.action(description="🔵 Marcar como no leídas")
def notif_no_leidas(modeladmin, request, queryset):
    total = queryset.update(leido=False, leido_en=None)
    messages.success(request, f"✅ {total} notificación(es) marcada(s) como no leída(s).")


@admin.action(description="🗑️ Eliminar notificaciones antiguas (>30 días)")
def notif_eliminar_antiguas(modeladmin, request, queryset):
    corte = timezone.now() - timedelta(days=30)
    q = queryset.filter(creado_en__lt=corte)
    total = q.count()
    q.delete()
    messages.success(request, f"✅ {total} notificación(es) eliminada(s).")


# ============================================================
# ADMINISTRACIÓN DE ROLES Y RELACIONES
# ============================================================

@admin.register(Rol)
class RolAdmin(admin.ModelAdmin):
    list_display = ['usuario', 'tipo', 'activo', 'banco_asignado', 'creado_en']
    list_filter = ['tipo', 'activo']
    search_fields = ['usuario__username', 'usuario__email']
    raw_id_fields = ['usuario', 'banco_asignado', 'comercial_asignado']
    readonly_fields = ['creado_en']
    list_per_page = 50


@admin.register(Subordinacion)
class SubordinacionAdmin(admin.ModelAdmin):
    list_display = ['jefe', 'subordinado', 'activo', 'es_temporal', 'creado_en', 'porcentaje_comision']
    list_filter = ['activo', 'es_temporal']
    search_fields = ['jefe__username', 'subordinado__username']
    raw_id_fields = ['jefe', 'subordinado']
    readonly_fields = ['creado_en']
    list_per_page = 50


@admin.register(RelacionClienteGestor)
class RelacionClienteGestorAdmin(admin.ModelAdmin):
    list_display = ['cliente', 'gestor', 'tipo_gestor', 'activo', 'fecha_asignacion']
    list_filter = ['tipo_gestor', 'activo']
    search_fields = ['cliente__username', 'gestor__username']
    raw_id_fields = ['cliente', 'gestor', 'asignado_por']
    readonly_fields = ['fecha_asignacion']
    list_per_page = 50


@admin.register(RelacionComercialBanco)
class RelacionComercialBancoAdmin(admin.ModelAdmin):
    list_display = ['comercial', 'banco', 'activo', 'fecha_asignacion']
    list_filter = ['activo']
    search_fields = ['comercial__username', 'banco__username']
    raw_id_fields = ['comercial', 'banco', 'asignado_por']
    readonly_fields = ['fecha_asignacion']
    list_per_page = 50


# ============================================================
# ADMINISTRACIÓN FINANCIERA
# ============================================================

@admin.register(Fondo)
class FondoAdmin(admin.ModelAdmin):
    list_display = [
        'usuario', 'forma_pago', 'monto_display', 'activo_badge',
        'asignado_por', 'creado_en'
    ]
    list_filter = ['activo', 'forma_pago', 'creado_en']
    search_fields = ['usuario__username', 'asignado_por__username']
    raw_id_fields = ['usuario', 'forma_pago', 'sorteo', 'asignado_por']
    readonly_fields = ['creado_en', 'actualizado_en']
    list_per_page = 50
    actions = [fondo_sumar_10, fondo_restar_10, fondo_desactivar, fondo_reactivar]

    def monto_display(self, obj):
        monto = obj.monto or Decimal('0.00')
        color = '#059669' if monto > 0 else ('#e11d48' if monto < 0 else '#6b7280')
        return format_html('<strong style="color:{}">${:.2f}</strong>', color, monto)
    monto_display.short_description = 'Monto'

    def activo_badge(self, obj):
        return _badge('activo' if obj.activo else 'inactivo',
                      '#059669' if obj.activo else '#6b7280')
    activo_badge.short_description = 'Estado'


@admin.register(MovimientoFondo)
class MovimientoFondoAdmin(admin.ModelAdmin):
    list_display = ['id', 'emisor', 'receptor', 'tipo', 'monto_display', 'estado_badge', 'creado_en']
    list_filter = ['tipo', 'estado', 'creado_en']
    search_fields = ['emisor__username', 'receptor__username', 'nota', 'datos_transferencia']
    raw_id_fields = ['emisor', 'receptor', 'forma_pago']
    readonly_fields = ['creado_en', 'confirmado_en']
    date_hierarchy = 'creado_en'
    list_per_page = 100
    actions = [mov_confirmar, mov_cancelar]

    def monto_display(self, obj):
        return format_html('<strong>${:.2f}</strong>', obj.monto or 0)
    monto_display.short_description = 'Monto'

    def estado_badge(self, obj):
        colores = {
            'confirmado': '#059669',
            'pendiente': '#d97706',
            'cancelado': '#e11d48',
            'rechazado': '#e11d48',
        }
        color = colores.get(obj.estado, '#6b7280')
        return _badge(obj.estado or '—', color)
    estado_badge.short_description = 'Estado'


@admin.register(Comision)
class ComisionAdmin(admin.ModelAdmin):
    list_display = ['banco', 'comercial', 'tipo', 'porcentaje', 'activo', 'es_global']
    list_filter = ['tipo', 'activo', 'es_global']
    search_fields = ['banco__username', 'comercial__username']
    raw_id_fields = ['banco', 'comercial', 'forma_juego', 'sorteo', 'heredado_de']
    readonly_fields = ['creado_en', 'actualizado_en']
    list_per_page = 50


@admin.register(DosisPago)
class DosisPagoAdmin(admin.ModelAdmin):
    list_display = ['comercial', 'sorteo', 'forma_juego', 'monto_por_peso', 'activo']
    list_filter = ['activo', 'es_global']
    search_fields = ['comercial__username']
    raw_id_fields = ['banco', 'comercial', 'sorteo', 'forma_juego', 'forma_pago', 'heredado_de']
    readonly_fields = ['creado_en', 'actualizado_en']
    list_per_page = 50


@admin.register(Bono)
class BonoAdmin(admin.ModelAdmin):
    list_display = ['usuario', 'tipo', 'monto_display', 'saldo_display', 'estado_badge', 'creado_en']
    list_filter = ['tipo', 'estado', 'creado_en']
    search_fields = ['usuario__username', 'usuario_referente__username']
    raw_id_fields = ['usuario', 'asignado_por', 'usuario_referente', 'usuario_referido']
    readonly_fields = ['creado_en', 'actualizado_en']
    list_per_page = 50
    actions = [bono_activar, bono_agotar, bono_vaciar]

    def monto_display(self, obj):
        return format_html('<strong>${:.2f}</strong>', obj.monto or 0)
    monto_display.short_description = 'Monto'

    def saldo_display(self, obj):
        saldo = obj.saldo_restante or Decimal('0.00')
        color = '#059669' if saldo > 0 else '#6b7280'
        return format_html('<strong style="color:{}">${:.2f}</strong>', color, saldo)
    saldo_display.short_description = 'Saldo restante'

    def estado_badge(self, obj):
        colores = {
            'activo': '#059669',
            'agotado': '#6b7280',
            'expirado': '#e11d48',
            'cancelado': '#e11d48',
        }
        color = colores.get(obj.estado, '#6b7280')
        return _badge(obj.estado or '—', color)
    estado_badge.short_description = 'Estado'


@admin.register(Deuda)
class DeudaAdmin(admin.ModelAdmin):
    list_display = ['usuario', 'acreedor', 'monto_original', 'saldo_pendiente', 'estado', 'fecha_creacion']
    list_filter = ['estado', 'es_automatica']
    search_fields = ['usuario__username', 'acreedor__username', 'origen']
    raw_id_fields = ['usuario', 'acreedor', 'forma_pago', 'creado_por']
    readonly_fields = ['fecha_creacion']
    list_per_page = 50


@admin.register(Notificacion)
class NotificacionAdmin(admin.ModelAdmin):
    list_display = ['id', 'usuario', 'tipo', 'mensaje_corto', 'leido_badge', 'prioridad', 'creado_en']
    list_filter = ['tipo', 'leido', 'prioridad', 'categoria', 'creado_en']
    search_fields = ['usuario__username', 'mensaje']
    raw_id_fields = ['usuario']
    readonly_fields = ['creado_en', 'leido_en']
    date_hierarchy = 'creado_en'
    list_per_page = 100
    actions = [notif_leidas, notif_no_leidas, notif_eliminar_antiguas]

    def mensaje_corto(self, obj):
        txt = (obj.mensaje or '')[:60]
        return txt + ('…' if len(obj.mensaje or '') > 60 else '')
    mensaje_corto.short_description = 'Mensaje'

    def leido_badge(self, obj):
        if obj.leido:
            return format_html('<span style="color:#059669;font-weight:600;">✓ Leído</span>')
        return format_html('<span style="color:#d97706;font-weight:600;">● No leído</span>')
    leido_badge.short_description = 'Leído'


# ============================================================
# CUADRE DIARIO
# ============================================================

@admin.register(CuadreDiario)
class CuadreDiarioAdmin(admin.ModelAdmin):
    list_display = [
        'usuario', 'fecha', 'inicial_tarjeta', 'recogido_total',
        'limpio_tarjeta', 'fondo_tarjeta', 'cerrado_badge'
    ]
    list_filter = ['cerrado', 'fecha']
    search_fields = ['usuario__username']
    raw_id_fields = ['usuario']
    readonly_fields = ['fecha']
    date_hierarchy = 'fecha'
    list_per_page = 50

    fieldsets = (
        ('Usuario y fecha', {'fields': ('usuario', 'fecha')}),
        ('Inicial', {'fields': ('inicial_tarjeta', 'inicial_saldo', 'inicial_cash')}),
        ('Ajustes', {'fields': ('ajuste_tarjeta', 'ajuste_saldo', 'ajuste_cash')}),
        ('Enviado al banco', {'fields': ('envie_tarjeta', 'envie_saldo', 'envie_cash')}),
        ('Recibido del banco', {'fields': ('recibi_tarjeta', 'recibi_saldo', 'recibi_cash')}),
        ('Deuda y pagos', {'fields': ('deuda_total', 'pagado')}),
        ('Estado', {'fields': ('cerrado', 'notas')}),
    )

    def recogido_total(self, obj):
        return '0.00'
    recogido_total.short_description = 'Recogido (estimado)'

    def limpio_tarjeta(self, obj):
        return '0.00'
    limpio_tarjeta.short_description = 'Limpio (estimado)'

    def fondo_tarjeta(self, obj):
        return '0.00'
    fondo_tarjeta.short_description = 'Fondo (estimado)'

    def cerrado_badge(self, obj):
        if obj.cerrado:
            return _badge('cerrado', '#059669')
        return _badge('abierto', '#d97706')
    cerrado_badge.short_description = 'Estado'


# ============================================================
# SOBRELÍMITE
# ============================================================

@admin.register(Sobrelimite)
class SobrelimiteAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'jugada', 'comercial', 'banco',
        'monto_solicitado', 'monto_excedido',
        'estado_compensacion', 'fecha'
    )
    list_filter = ('estado_compensacion', 'fecha')
    search_fields = ('jugada__id', 'comercial__username', 'banco__username')
    raw_id_fields = ('jugada', 'comercial', 'banco', 'banco_solicitado')
    readonly_fields = ('fecha', 'fecha_compensacion', 'monto_compensado')
    date_hierarchy = 'fecha'
    list_per_page = 50
    fieldsets = (
        (None, {
            'fields': ('jugada', 'comercial', 'banco', 'banco_solicitado')
        }),
        ('Montos', {
            'fields': ('monto_solicitado', 'monto_excedido', 'limite_aplicado', 'monto_compensado')
        }),
        ('Estado', {
            'fields': ('estado_compensacion', 'fecha', 'fecha_compensacion')
        }),
    )


# ============================================================
# LÍMITE DE APUESTAS
# ============================================================

@admin.register(LimiteApuesta)
class LimiteApuestaAdmin(admin.ModelAdmin):
    list_display = ['comercial', 'banco', 'sorteo', 'forma_juego', 'forma_pago', 'monto_maximo', 'monto_sobrelimite', 'activo']
    list_filter = ['activo', 'es_global']
    search_fields = ['comercial__username', 'banco__username']
    raw_id_fields = ['banco', 'comercial', 'sorteo', 'forma_juego', 'forma_pago']
    readonly_fields = ['creado_en', 'actualizado_en']
    list_per_page = 50


# ============================================================
# PRÉSTAMOS
# ============================================================

@admin.register(Prestamo)
class PrestamoAdmin(admin.ModelAdmin):
    list_display = ['solicitante', 'prestamista', 'monto', 'saldo_pendiente', 'estado', 'fecha_solicitud']
    list_filter = ['estado']
    search_fields = ['solicitante__username', 'prestamista__username']
    raw_id_fields = ['solicitante', 'prestamista', 'aprobado_por', 'comercial_comun']
    readonly_fields = ['fecha_solicitud', 'fecha_aprobacion', 'fecha_pago']
    date_hierarchy = 'fecha_solicitud'
    list_per_page = 50


# ============================================================
# SUSCRIPCIÓN DE BANCOS
# ============================================================

@admin.register(SuscripcionBanco)
class SuscripcionBancoAdmin(admin.ModelAdmin):
    list_display = ['banco', 'fecha_ascenso', 'fecha_vencimiento', 'activo', 'comerciales_permitidos']
    list_filter = ['activo', 'tipo_pago']
    search_fields = ['banco__username']
    raw_id_fields = ['banco']
    readonly_fields = ['fecha_ascenso', 'creado_en', 'actualizado_en']
    list_per_page = 50


# ============================================================
# RECURSOS ASIGNADOS
# ============================================================

@admin.register(RecursoAsignado)
class RecursoAsignadoAdmin(admin.ModelAdmin):
    list_display = ['banco', 'comercial', 'tipo', 'sorteo', 'forma_juego', 'forma_pago', 'activo']
    list_filter = ['tipo', 'activo']
    search_fields = ['banco__username', 'comercial__username']
    raw_id_fields = ['banco', 'comercial', 'sorteo', 'forma_juego', 'forma_pago', 'creado_por']
    readonly_fields = ['fecha_asignacion']
    list_per_page = 50


# ============================================================
# VÍAS DE PAGO
# ============================================================

@admin.register(ViaPago)
class ViaPagoAdmin(admin.ModelAdmin):
    list_display = ['gestor', 'forma_pago', 'tipo', 'nombre', 'activo', 'es_por_defecto']
    list_filter = ['tipo', 'activo', 'es_por_defecto']
    search_fields = ['gestor__username', 'nombre', 'numero']
    raw_id_fields = ['gestor', 'forma_pago']
    readonly_fields = ['creado_en', 'actualizado_en']
    list_per_page = 50


# ============================================================
# SOLICITUDES DE RECARGA
# ============================================================

@admin.register(SolicitudRecarga)
class SolicitudRecargaAdmin(admin.ModelAdmin):
    list_display = ['cliente', 'gestor', 'monto', 'estado', 'fecha_solicitud']
    list_filter = ['estado', 'fecha_solicitud']
    search_fields = ['cliente__username', 'gestor__username']
    raw_id_fields = ['cliente', 'gestor', 'forma_pago', 'via_pago', 'creado_por']
    readonly_fields = ['fecha_solicitud', 'fecha_respuesta', 'fecha_pago']
    date_hierarchy = 'fecha_solicitud'
    list_per_page = 50


# ============================================================
# SOLICITUDES DE COBRO DE PREMIO
# ============================================================

@admin.register(SolicitudCobroPremio)
class SolicitudCobroPremioAdmin(admin.ModelAdmin):
    list_display = ('id', 'cliente', 'gestor', 'monto', 'estado', 'fecha_solicitud')
    list_filter = ('estado', 'fecha_solicitud')
    search_fields = ('cliente__username', 'gestor__username')
    raw_id_fields = ('cliente', 'gestor', 'forma_pago', 'via_pago')
    readonly_fields = ('fecha_solicitud', 'fecha_respuesta', 'fecha_pago')
    list_select_related = ('cliente', 'gestor', 'forma_pago', 'via_pago')
    date_hierarchy = 'fecha_solicitud'
    list_per_page = 50
    fieldsets = (
        (None, {
            'fields': ('cliente', 'gestor', 'forma_pago', 'via_pago', 'monto')
        }),
        ('Estado y mensajes', {
            'fields': ('estado', 'mensaje_cliente', 'mensaje_gestor')
        }),
        ('Información de premios', {
            'fields': ('jugadas_ids', 'monto_pagado')
        }),
        ('Fechas', {
            'fields': ('fecha_solicitud', 'fecha_respuesta', 'fecha_pago'),
            'classes': ('collapse',)
        }),
    )