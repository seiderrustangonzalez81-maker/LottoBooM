# sorteos/models.py
from django.db import models
from jugadas.models import FormaJuego


class Sorteo(models.Model):
    ORIGEN_CHOICES = [
        ('dominicano', 'Dominicano'),
        ('americano', 'Americano'),
        ('haitiano', 'Haitiano'),
    ]
    nombre = models.CharField(max_length=100, unique=True, verbose_name="Nombre del sorteo")
    activo = models.BooleanField(default=True, verbose_name="Activo")
    horarios = models.JSONField(default=dict, blank=True, verbose_name="Horarios por temporada y día")
    hora_salida = models.TimeField(null=True, blank=True, verbose_name="Hora de salida (opcional)")
    minutos_cierre = models.IntegerField(default=5, verbose_name="Minutos antes de la salida para cerrar apuestas")
    origen = models.CharField(max_length=20, choices=ORIGEN_CHOICES, default='dominicano', verbose_name="Origen del sorteo")

    # ✅ NUEVO CAMPO: formas de juego admitidas (guardadas por clave corta, ej: "pick3", "fijo")
    formas_juego = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Formas de juego admitidas",
        help_text="Lista de claves de formas de juego: pick2, pick3, pick4, pick5, fijo, corrido1, corrido2, pf, vspf, vspick2, pick2vspf, tripleta, posicion, centena corrida1, centena corrida2, superparlet, parlet"
    )

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Sorteo"
        verbose_name_plural = "Sorteos"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class SorteoFormaJuego(models.Model):
    """Se mantiene por compatibilidad, pero ya no es la fuente de verdad."""
    sorteo = models.ForeignKey('Sorteo', on_delete=models.CASCADE, related_name='formas_disponibles')
    forma_juego = models.ForeignKey('jugadas.FormaJuego', on_delete=models.CASCADE)
    activo = models.BooleanField(default=True)

    class Meta:
        unique_together = ('sorteo', 'forma_juego')

    def __str__(self):
        return f"{self.sorteo.nombre} - {self.forma_juego.nombre}"


class DosisBase(models.Model):
    sorteo = models.ForeignKey('Sorteo', on_delete=models.CASCADE, related_name='dosis_base')
    forma_juego = models.ForeignKey(FormaJuego, on_delete=models.CASCADE)
    dosis_por_peso = models.DecimalField(max_digits=10, decimal_places=2, default=1.0)
    activo = models.BooleanField(default=True)

    class Meta:
        unique_together = ('sorteo', 'forma_juego')

    def __str__(self):
        return f"{self.sorteo.nombre} - {self.forma_juego.nombre}: {self.dosis_por_peso}"