# jugadas/admin.py
# -*- coding: utf-8 -*-
from django.contrib import admin, messages
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Sum
from django.utils import timezone
from decimal import Decimal
import csv
from django.http import HttpResponse

from .models import (
    Jugada, FormaJuego, Boleta,
    ClienteOffline,
)


# ══════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════

def _badge(texto, color='#6b7280'):
    return format_html(
        '<span style="background:{};color:#fff;padding:2px 8px;'
        'border-radius:10px;font-size:11px;text-transform:uppercase;'
        'font-weight:600;">{}</span>',
        color, texto
    )


# ══════════════════════════════════════════════════════════════
# ACCIONES MASIVAS
# ══════════════════════════════════════════════════════════════

@admin.action(description="🚫 Cancelar boletas seleccionadas")
def cancelar_boletas(modeladmin, request, queryset):
    from jugadas.views import _do_cancelar_boleta
    ok, fail = 0, 0
    for b in queryset:
        if b.estado == 'cancelada':
            fail += 1
            continue
        exito, _, _ = _do_cancelar_boleta(b, request.user, motivo='Cancelación masiva desde admin')
        if exito:
            ok += 1
        else:
            fail += 1
    messages.success(request, f"✅ {ok} boleta(s) cancelada(s). {fail} no se pudieron cancelar.")


@admin.action(description="✅ Marcar como ganadoras")
def marcar_ganadoras(modeladmin, request, queryset):
    total = queryset.update(estado='ganadora')
    messages.success(request, f"✅ {total} boleta(s) marcada(s) como ganadora.")


@admin.action(description="❌ Marcar como perdedoras")
def marcar_perdedoras(modeladmin, request, queryset):
    total = queryset.update(estado='perdedora')
    messages.success(request, f"✅ {total} boleta(s) marcada(s) como perdedora.")


@admin.action(description="📥 Exportar a CSV")
def exportar_csv(modeladmin, request, queryset):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="boletas_{timezone.now():%Y%m%d_%H%M}.csv"'
    w = csv.writer(response)
    w.writerow(['Referencia', 'Cliente', 'Destinatario', 'Fecha sorteo', 'Total', 'Premios', 'Estado'])
    for b in queryset:
        total = b.jugadas.aggregate(t=Sum('monto'))['t'] or 0
        premios = b.jugadas.aggregate(t=Sum('monto_premio'))['t'] or 0
        w.writerow([
            b.referencia,
            b.usuario.username,
            b.destinatario.username if b.destinatario else '—',
            b.fecha_sorteo.strftime('%Y-%m-%d') if b.fecha_sorteo else '—',
            f"{total:.2f}",
            f"{premios:.2f}",
            b.estado,
        ])
    return response


# ══════════════════════════════════════════════════════════════
# JUGADA ADMIN
# ══════════════════════════════════════════════════════════════

@admin.register(Jugada)
class JugadaAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'numero', 'forma_juego', 'sorteo', 'monto_display',
        'usuario', 'destinatario', 'estado_badge', 'fecha_sorteo', 'boleta_link'
    )
    list_filter = ('estado', 'forma_juego', 'sorteo', 'fecha_sorteo', 'forma_pago')
    search_fields = ('numero', 'usuario__username', 'destinatario__username', 'boleta__referencia')
    date_hierarchy = 'fecha_sorteo'
    list_per_page = 100
    raw_id_fields = ('usuario', 'destinatario', 'sorteo', 'forma_juego', 'forma_pago', 'boleta', 'comercial')

    def monto_display(self, obj):
        return f"${obj.monto:.2f}"
    monto_display.short_description = 'Monto'

    def estado_badge(self, obj):
        colores = {
            'confirmada': '#0891b2',
            'pendiente': '#d97706',
            'ganadora': '#65a30d',
            'perdedora': '#6b7280',
            'cancelada': '#e11d48',
        }
        return _badge(obj.estado or '—', colores.get(obj.estado, '#6b7280'))
    estado_badge.short_description = 'Estado'

    def boleta_link(self, obj):
        if not obj.boleta:
            return '—'
        url = reverse('admin:jugadas_boleta_change', args=[obj.boleta.pk])
        return format_html('<a href="{}">{}</a>', url, obj.boleta.referencia)
    boleta_link.short_description = 'Boleta'


# ══════════════════════════════════════════════════════════════
# BOLETA ADMIN
# ══════════════════════════════════════════════════════════════

class JugadaInline(admin.TabularInline):
    model = Jugada
    extra = 0
    fields = ('numero', 'monto', 'monto_premio', 'sorteo', 'forma_juego', 'estado')
    readonly_fields = ('numero', 'monto', 'monto_premio', 'sorteo', 'forma_juego', 'estado')
    can_delete = False
    show_change_link = True


@admin.register(Boleta)
class BoletaAdmin(admin.ModelAdmin):
    list_display = (
        'referencia', 'usuario', 'destinatario', 'fecha_sorteo',
        'total_display', 'premios_display', 'estado_badge'
    )
    list_filter = ('estado', 'fecha_sorteo', 'forma_pago')
    search_fields = ('referencia', 'usuario__username', 'destinatario__username')
    date_hierarchy = 'fecha_sorteo'
    list_per_page = 50
    actions = (cancelar_boletas, marcar_ganadoras, marcar_perdedoras, exportar_csv)
    inlines = (JugadaInline,)
    raw_id_fields = ('usuario', 'destinatario', 'forma_pago', 'comercial', 'creado_por')

    def total_display(self, obj):
        t = obj.jugadas.aggregate(t=Sum('monto'))['t'] or Decimal('0.00')
        return f"${t:.2f}"
    total_display.short_description = 'Total'

    def premios_display(self, obj):
        t = obj.jugadas.aggregate(t=Sum('monto_premio'))['t'] or Decimal('0.00')
        color = '#059669' if t > 0 else '#6b7280'
        return format_html('<strong style="color:{}">${:.2f}</strong>', color, t)
    premios_display.short_description = 'Premios'

    def estado_badge(self, obj):
        colores = {
            'activa': '#0891b2',
            'cancelada': '#e11d48',
            'ganadora': '#65a30d',
            'perdedora': '#6b7280',
            'pendiente': '#d97706',
        }
        return _badge(obj.estado or '—', colores.get(obj.estado, '#6b7280'))
    estado_badge.short_description = 'Estado'


# ══════════════════════════════════════════════════════════════
# FORMA DE JUEGO ADMIN
# ══════════════════════════════════════════════════════════════

@admin.register(FormaJuego)
class FormaJuegoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'digitos_esperados', 'activo')
    list_filter = ('activo',)
    search_fields = ('nombre',)


# ══════════════════════════════════════════════════════════════
# POSTPAGOS
# ══════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════
# CLIENTE OFFLINE (CORREGIDO: usa fecha_alta, no creado_en)
# ══════════════════════════════════════════════════════════════

@admin.register(ClienteOffline)
class ClienteOfflineAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'telefono_offline', 'creado_por',
        'password_cambiada_por_cliente', 'fecha_alta'
    )
    list_filter = ('password_cambiada_por_cliente', 'fecha_alta')
    search_fields = ('user__username', 'telefono_offline', 'creado_por__username')
    readonly_fields = ('fecha_alta',)
    raw_id_fields = ('user', 'creado_por')
    list_per_page = 50