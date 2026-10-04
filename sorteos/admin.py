# sorteos/admin.py
# -*- coding: utf-8 -*-
from django.contrib import admin, messages
from django import forms
from .models import Sorteo


# ============================================================
# ACCIONES MASIVAS
# ============================================================
@admin.action(description="✅ Activar sorteos seleccionados")
def activar_sorteos(modeladmin, request, queryset):
    total = queryset.update(activo=True)
    messages.success(request, f"✅ {total} sorteo(s) activado(s).")


@admin.action(description="🚫 Desactivar sorteos seleccionados")
def desactivar_sorteos(modeladmin, request, queryset):
    total = queryset.update(activo=False)
    messages.success(request, f"✅ {total} sorteo(s) desactivado(s).")


# ============================================================
# FORMULARIO PERSONALIZADO PARA EL ADMIN
# ============================================================
FORMAS_JUEGO_CHOICES = [
    ('pick2', 'Pick 2'),
    ('pick3', 'Pick 3'),
    ('pick4', 'Pick 4'),
    ('pick5', 'Pick 5'),
    ('fijo', 'Fijo'),
    ('corrido1', 'Corrido 1'),
    ('corrido2', 'Corrido 2'),
    ('pf', 'PF'),
    ('vspf', 'VS PF'),
    ('vspick2', 'VS Pick2'),
    ('pick2vspf', 'Pick2 vs PF'),
    ('tripleta', 'Tripleta'),
    ('posicion', 'Posición'),
    ('centena corrida1', 'Centena Corrida 1'),
    ('centena corrida2', 'Centena Corrida 2'),
    ('superparlet', 'Superparlet'),
    ('parlet', 'Parlet'),
    ('par frontal', 'Par frontal'),
    ('vs', 'VS'),
]


class SorteoAdminForm(forms.ModelForm):
    formas_juego = forms.MultipleChoiceField(
        choices=FORMAS_JUEGO_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label='Formas de juego admitidas',
        help_text='Marca todas las formas de juego que este sorteo acepta.'
    )

    class Meta:
        model = Sorteo
        fields = '__all__'

    def clean_formas_juego(self):
        return list(self.cleaned_data.get('formas_juego', []))


# ============================================================
# ADMIN DE SORTEO
# ============================================================
@admin.register(Sorteo)
class SorteoAdmin(admin.ModelAdmin):
    form = SorteoAdminForm

    list_display = (
        'nombre',
        'id',
        'origen',
        'activo',
        'hora_salida_display',
        'minutos_cierre',
        'horarios_resumidos',
        'cantidad_formas',
        'creado_en',
    )
    list_filter = ('activo', 'origen')
    search_fields = ('nombre',)
    readonly_fields = ('creado_en', 'actualizado_en')
    actions = (activar_sorteos, desactivar_sorteos)
    list_per_page = 50

    fieldsets = (
        (None, {
            'fields': ('nombre', 'activo', 'origen', 'horarios', 'hora_salida', 'minutos_cierre')
        }),
        ('Formas de juego admitidas', {
            'fields': ('formas_juego',),
            'description': 'Marca las formas de juego que este sorteo acepta. '
                           'Esta información reemplaza la antigua tabla SorteoFormaJuego.'
        }),
        ('Metadatos', {
            'fields': ('creado_en', 'actualizado_en'),
            'classes': ('collapse',)
        }),
    )

    # ---------- Métodos de list_display ----------

    def cantidad_formas(self, obj):
        return len(obj.formas_juego or [])
    cantidad_formas.short_description = "Formas"

    def hora_salida_display(self, obj):
        if obj.hora_salida:
            return obj.hora_salida.strftime('%I:%M %p')
        return "—"
    hora_salida_display.short_description = "Hora salida"

    def horarios_resumidos(self, obj):
        if not obj.horarios:
            return "Sin horarios"
        try:
            horarios = obj.horarios
            if isinstance(horarios, dict):
                resumen = []
                for temp in ['verano', 'invierno']:
                    if temp in horarios and horarios[temp]:
                        dias = horarios[temp]
                        items = [f"{dia[:3]}:{hora}" for dia, hora in dias.items() if hora]
                        if items:
                            resumen.append(f"{temp.capitalize()}: {' '.join(items)}")
                return " | ".join(resumen) if resumen else "Sin datos"
            return str(horarios)[:50]
        except Exception:
            return "Error en horarios"
    horarios_resumidos.short_description = "Horarios"