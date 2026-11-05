from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

from jugadas.models import Jugada
from sorteos.models import Sorteo
# ✅ from resultados.models import Premio  --> ELIMINADO



class Resultado(models.Model):
    """
    Modelo para almacenar los resultados de los sorteos.
    Incluye campos individuales para cada valor del resumen,
    además del JSONField 'derivados' para compatibilidad.
    """
    sorteo = models.ForeignKey(Sorteo, on_delete=models.CASCADE, related_name='resultados')
    fecha = models.DateField()
    hora = models.TimeField()
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='resultados_creados')
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    # ============================================================
    # CAMPOS INDIVIDUALES DEL RESUMEN
    # ============================================================
    pick2 = models.CharField(max_length=2, blank=True, null=True)
    pick3 = models.CharField(max_length=3, blank=True, null=True)
    pick4 = models.CharField(max_length=4, blank=True, null=True)
    pick5 = models.CharField(max_length=5, blank=True, null=True)
    pf = models.CharField(max_length=2, blank=True, null=True)
    fijo = models.CharField(max_length=2, blank=True, null=True)
    corrido_1 = models.CharField(max_length=2, blank=True, null=True)
    corrido_2 = models.CharField(max_length=2, blank=True, null=True)
    centena_corrida_1 = models.CharField(max_length=3, blank=True, null=True)
    centena_corrida_2 = models.CharField(max_length=3, blank=True, null=True)
    parlet = models.CharField(max_length=200, blank=True, null=True)
    posicion = models.CharField(max_length=200, blank=True, null=True)
    tripleta = models.CharField(max_length=200, blank=True, null=True)
    vspf = models.CharField(max_length=200, blank=True, null=True)
    vspick2 = models.CharField(max_length=200, blank=True, null=True)
    pick2vspf = models.CharField(max_length=200, blank=True, null=True)

    # Campo obligatorio (se llena automáticamente)
    numero_ganador = models.CharField(max_length=10, blank=False, null=False)

    # Campos JSON para datos adicionales y derivaciones completas
    derivados = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-fecha', '-hora']
        # 🔥 CLAVE: UN SOLO RESULTADO POR SORTEO Y FECHA (sin importar la hora)
        unique_together = ['sorteo', 'fecha']

    def __str__(self):
        return f"{self.sorteo.nombre} - {self.fecha} {self.hora}"


class Premio(models.Model):
    """
    Modelo para registrar premios generados a partir de jugadas ganadoras.
    """
    ESTADO_CHOICES = (
        ('pendiente', 'Pendiente'),
        ('pagado', 'Pagado'),
        ('anulado', 'Anulado'),
    )

    jugada = models.ForeignKey(Jugada, on_delete=models.CASCADE, related_name='premios')
    monto_premio = models.DecimalField(max_digits=12, decimal_places=2)
    multiplicador_aplicado = models.IntegerField(default=500)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='pendiente')
    cobrado = models.BooleanField(default=False)
    fecha_pago = models.DateTimeField(null=True, blank=True)
    pagado_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='premios_pagados'
    )
    comentario = models.TextField(blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, blank=True)

    def marcar_como_pagado(self, usuario):
        self.cobrado = True
        self.estado = 'pagado'
        self.fecha_pago = timezone.now()
        self.pagado_por = usuario
        self.save()

    class Meta:
        ordering = ['-creado_en']

    def __str__(self):
        return f"Premio #{self.id} - {self.jugada.usuario.username} - ${self.monto_premio}"