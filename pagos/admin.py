# pagos/admin.py

from django.contrib import admin
from .models import Pago, FormaPago


@admin.register(FormaPago)
class FormaPagoAdmin(admin.ModelAdmin):
    list_display = ['id', 'nombre', 'activo', 'descripcion']
    list_filter = ['activo']
    search_fields = ['nombre']


@admin.register(Pago)
class PagoAdmin(admin.ModelAdmin):
    list_display = ['id', 'usuario', 'cantidad', 'metodo', 'estado', 'fecha']
    list_filter = ['estado', 'metodo', 'fecha']
    search_fields = ['usuario__username', 'referencia']
    raw_id_fields = ['usuario']
    readonly_fields = ['creado_en', 'actualizado_en']

    fieldsets = (
        ('Información del Pago', {
            'fields': ('usuario', 'cantidad', 'metodo', 'referencia')
        }),
        ('Estado', {
            'fields': ('estado', 'nota')
        }),
        ('Fechas', {
            'fields': ('fecha', 'creado_en', 'actualizado_en'),
            'classes': ('collapse',)
        }),
    )