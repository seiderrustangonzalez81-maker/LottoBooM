from django.db import models
from django.conf import settings


class VisitaDiaria(models.Model):
    session_key = models.CharField(max_length=40, blank=True, default='')
    fecha = models.DateField()
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    ip = models.CharField(max_length=45, blank=True, default='')
    user_agent = models.CharField(max_length=255, blank=True, default='')
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['session_key', 'fecha'],
                name='unique_visita_diaria'
            )
        ]

    def __str__(self):
        return f"{self.session_key} - {self.fecha}"