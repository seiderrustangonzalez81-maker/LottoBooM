from django.contrib import admin
from .models import VisitaDiaria


@admin.register(VisitaDiaria)
class VisitaDiariaAdmin(admin.ModelAdmin):
    list_display = ('session_key', 'usuario', 'fecha', 'ip', 'creado_en')
    list_filter = ('fecha',)
    search_fields = ('session_key', 'usuario__username', 'ip')
    date_hierarchy = 'fecha'
    readonly_fields = ('creado_en',)