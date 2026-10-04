from django.db import models
from django.conf import settings


class UbicacionUsuario(models.Model):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ubicaciones",
        verbose_name="Usuario"
    )
    telefono = models.CharField(
        max_length=20,
        verbose_name="Teléfono"
    )
    direccion = models.CharField(
        max_length=255,
        verbose_name="Dirección"
    )
    ciudad = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Ciudad"
    )
    provincia = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Provincia"
    )
    latitud = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        blank=True,
        null=True,
        verbose_name="Latitud"
    )
    longitud = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        blank=True,
        null=True,
        verbose_name="Longitud"
    )
    activo = models.BooleanField(
        default=True,
        verbose_name="Activo"
    )
    fecha_registro = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de registro"
    )
    actualizado_en = models.DateTimeField(
        auto_now=True,
        verbose_name="Actualizado"
    )

    class Meta:
        verbose_name = "Ubicación de usuario"
        verbose_name_plural = "Ubicaciones de usuarios"
        ordering = ["-fecha_registro"]
        indexes = [
            models.Index(fields=["telefono"]),
            models.Index(fields=["usuario"]),
        ]

    def __str__(self):
        return f"{self.usuario.username} - {self.telefono}"

    def direccion_completa(self):
        """Retorna la dirección formateada"""
        partes = [self.direccion]
        if self.ciudad:
            partes.append(self.ciudad)
        if self.provincia:
            partes.append(self.provincia)
        return ", ".join(partes)