from django.db import models
from django.conf import settings
from django.utils import timezone


class Pago(models.Model):
    ESTADOS = [
        ("pendiente", "Pendiente"),
        ("completado", "Completado"),
        ("rechazado", "Rechazado"),
        ("cancelado", "Cancelado"),
    ]

    METODOS = [
        ("transferencia", "Transferencia bancaria"),
        ("efectivo", "Efectivo"),
        ("tarjeta", "Tarjeta"),
        ("otro", "Otro"),
    ]

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="pagos", verbose_name="Usuario")
    cantidad = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Cantidad (CUP)")
    metodo = models.CharField(max_length=20, choices=METODOS, default="transferencia", verbose_name="Método de pago")
    referencia = models.CharField(max_length=100, blank=True, verbose_name="Referencia")
    estado = models.CharField(max_length=20, choices=ESTADOS, default="pendiente", verbose_name="Estado")
    nota = models.TextField(blank=True, verbose_name="Nota")
    fecha = models.DateTimeField(default=timezone.now, verbose_name="Fecha de pago")
    creado_en = models.DateTimeField(default=timezone.now)
    actualizado_en = models.DateTimeField(auto_now=True, verbose_name="Actualizado")

    class Meta:
        ordering = ["-fecha"]
        verbose_name = "Pago"
        verbose_name_plural = "Pagos"

    def __str__(self):
        return f"Pago #{self.id} - {self.usuario.username} ({self.cantidad} CUP)"


class FormaPago(models.Model):
    nombre = models.CharField(max_length=50, unique=True, verbose_name="Nombre")
    activo = models.BooleanField(default=True, verbose_name="Activo")
    descripcion = models.TextField(blank=True, verbose_name="Descripción")
    creado_en = models.DateTimeField(default=timezone.now, verbose_name="Creado")
    actualizado_en = models.DateTimeField(auto_now=True, verbose_name="Actualizado")

    class Meta:
        ordering = ["nombre"]
        verbose_name = "Forma de pago"
        verbose_name_plural = "Formas de pago"

    def __str__(self):
        return self.nombre