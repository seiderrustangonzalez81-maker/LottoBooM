from django.contrib import admin
from .models import UbicacionUsuario


@admin.register(UbicacionUsuario)
class UbicacionUsuarioAdmin(admin.ModelAdmin):
    list_display = (
        "usuario",
        "telefono",
        "direccion",
        "ciudad",
        "provincia",
        "activo",
        "fecha_registro",
    )
    list_filter = ("activo", "provincia", "ciudad", "fecha_registro")
    search_fields = (
        "usuario__username",
        "usuario__email",
        "telefono",
        "direccion",
        "ciudad",
    )
    ordering = ("-fecha_registro",)
    date_hierarchy = "fecha_registro"

    fieldsets = (
        ("Usuario", {
            "fields": ("usuario", "telefono")
        }),
        ("Dirección", {
            "fields": ("direccion", "ciudad", "provincia")
        }),
        ("Coordenadas", {
            "fields": ("latitud", "longitud"),
            "classes": ("collapse",)
        }),
        ("Estado", {
            "fields": ("activo",)
        }),
    )