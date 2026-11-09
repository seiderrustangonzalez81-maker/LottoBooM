from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

from jugadas.models import Jugada
from sorteos.models import Sorteo
from django.db.models.signals import post_save
from django.dispatch import receiver


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

    procesamiento_estado = models.CharField(
        max_length=20, default='pendiente',
        choices=[('pendiente','Pendiente'),('procesando','Procesando'),
                 ('completado','Completado'),('error','Error')],
        db_index=True, verbose_name='Estado procesamiento premios',
    )
    procesamiento_msg = models.CharField(max_length=255, blank=True, default='')
    premios_generados = models.IntegerField(default=0)
    procesamiento_inicio = models.DateTimeField(null=True, blank=True)
    procesamiento_fin = models.DateTimeField(null=True, blank=True)

    # ═══════════════════════════════════════════════════════════════
    # NUEVO MÉTODO: Devuelve TODOS los campos del resultado
    # ═══════════════════════════════════════════════════════════════
    def get_todos_los_campos(self):
        """
        Devuelve una lista de tuplas (nombre, valor) con TODOS los campos
        poblados del resultado, listos para mostrar en el template.
        Solo incluye campos que tienen valor (no vacíos).
        """
        d = self.derivados or {}
        campos = []

        # ─── Campos base (individuales) ───
        if self.pick2: campos.append(('Pick2', self.pick2))
        if self.pick3: campos.append(('Pick3', self.pick3))
        if self.pick4: campos.append(('Pick4', self.pick4))
        if self.pick5: campos.append(('Pick5', self.pick5))
        if self.fijo: campos.append(('Fijo', self.fijo))
        if self.corrido_1: campos.append(('Corrido 1', self.corrido_1))
        if self.corrido_2: campos.append(('Corrido 2', self.corrido_2))
        if self.pf: campos.append(('PF', self.pf))
        if self.centena_corrida_1: campos.append(('Centena C1', self.centena_corrida_1))
        if self.centena_corrida_2: campos.append(('Centena C2', self.centena_corrida_2))

        # ─── Derivados avanzados (desde JSON) ───
        for parlet in d.get('parlet_general', []):
            campos.append(('Parlet', parlet))
        for pos in d.get('posicion', []):
            campos.append(('Posición', pos))
        for trip in d.get('tripleta', []):
            campos.append(('Tripleta', trip))
        for vs in d.get('vspf', []):
            campos.append(('VS PF', vs))
        for vs in d.get('vspick2', []):
            campos.append(('VS Pick2', vs))
        for vs in d.get('pick2vspf', []):
            campos.append(('Pick2 vs PF', vs))

        return campos


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


# ═══════════════════════════════════════════════════════════════
# SIGNAL: Recalcular derivados y premios al guardar un Resultado
# (esto permite autocorrección desde el admin)
# ═══════════════════════════════════════════════════════════════
@receiver(post_save, sender=Resultado)
def recalcular_derivados_al_guardar(sender, instance, created, **kwargs):
    """Cuando se guarda un Resultado (admin, shell, load_results),
    recalcula derivados y premios automáticamente."""
    # Evitar recursión infinita: usar un flag
    if getattr(instance, '_derivados_recalculados', False):
        return
    if created:
        return  # Si es nuevo, procesar_resultado ya lo maneja

    # Solo recalcular si cambió algo relevante
    from resultados.views import generar_derivaciones_desde_campos, procesar_resultado
    from django.contrib.auth.models import User

    derivados = generar_derivaciones_desde_campos(
        instance.pick2, instance.pick3, instance.pick4, instance.pick5,
        instance.fijo, instance.corrido_1, instance.corrido_2
    )
    instance.derivados = derivados
    instance._derivados_recalculados = True
    instance.save(update_fields=['derivados', 'actualizado_en'])

    # Recalcular premios
    admin = User.objects.filter(is_superuser=True).first()
    if admin:
        class FakeRequest:
            def __init__(self, user): self.user = user
        datos = {
            'sorteo': instance.sorteo, 'fecha': instance.fecha, 'hora': instance.hora,
            'pick2': instance.pick2 or '', 'pick3': instance.pick3 or '',
            'pick4': instance.pick4 or '', 'pick5': instance.pick5 or '',
            'fijo': instance.fijo or '', 'corrido_1': instance.corrido_1 or '',
            'corrido_2': instance.corrido_2 or '', 'pf': instance.pf or '',
            'centena_corrida_1': instance.centena_corrida_1 or '',
            'centena_corrida_2': instance.centena_corrida_2 or '',
        }
        procesar_resultado(FakeRequest(admin), datos, resultado_existente=instance)