from django.contrib import admin
from .models import Resultado

@admin.register(Resultado)
class ResultadoAdmin(admin.ModelAdmin):
    list_display = ('id', 'sorteo', 'fecha', 'creado_en')
    list_filter = ('sorteo', 'fecha')
    readonly_fields = ('creado_en', 'actualizado_en')