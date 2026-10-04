# roles/models.py
# -*- coding: utf-8 -*-
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

# ============================================================
# HELPER PARA NOTIFICACIONES (EVITA IMPORTACIÓN CIRCULAR)
# ============================================================
def _crear_notificacion(*args, **kwargs):
    from .utils import crear_notificacion
    return crear_notificacion(*args, **kwargs)


# ============================================================
# MODELOS DE RELACIONES Y ROLES
# ============================================================

class RelacionClienteGestor(models.Model):
    TIPO_GESTOR_CHOICES = [
    ('superadmin', 'Super Administrador'),
    ('banco', 'Banco'),
    ('comercial', 'Comercial'),
    ('cliente', 'Cliente'),
    ('auditor', 'Auditor'),
]

    cliente = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='gestores_asignados',
        verbose_name='Cliente'
    )
    gestor = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='clientes_asignados',
        verbose_name='Gestor'
    )
    tipo_gestor = models.CharField(
        max_length=20, choices=TIPO_GESTOR_CHOICES,
        default='comercial', verbose_name='Tipo de gestor'
    )
    activo = models.BooleanField(default=True, verbose_name='Activo')
    fecha_asignacion = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de asignación')
    asignado_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='asignaciones_realizadas', verbose_name='Asignado por'
    )
    observaciones = models.TextField(blank=True, null=True, verbose_name='Observaciones')

    class Meta:
        unique_together = ('cliente', 'gestor', 'tipo_gestor')
        verbose_name = 'Relación Cliente-Gestor'
        verbose_name_plural = 'Relaciones Cliente-Gestor'
        ordering = ['-fecha_asignacion']
        indexes = [
            models.Index(fields=['cliente', 'gestor', 'activo']),
            models.Index(fields=['gestor', 'tipo_gestor', 'activo']),
        ]

    def __str__(self):
        return f"{self.cliente.username} → {self.gestor.username} ({self.get_tipo_gestor_display()})"

    def desactivar(self):
        self.activo = False
        self.save(update_fields=['activo'])


class RelacionComercialBanco(models.Model):
    comercial = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='bancos_asignados', verbose_name='Comercial'
    )
    banco = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='comerciales_asignados', verbose_name='Banco'
    )
    activo = models.BooleanField(default=True, verbose_name='Activo')
    fecha_asignacion = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de asignación')
    asignado_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='asignaciones_comerciales', verbose_name='Asignado por'
    )
    observaciones = models.TextField(blank=True, null=True, verbose_name='Observaciones')

    class Meta:
        unique_together = ('comercial', 'banco')
        verbose_name = 'Relación Comercial-Banco'
        verbose_name_plural = 'Relaciones Comercial-Banco'
        ordering = ['-fecha_asignacion']
        indexes = [
            models.Index(fields=['comercial', 'banco', 'activo']),
            models.Index(fields=['banco', 'activo']),
        ]

    def __str__(self):
        return f"{self.comercial.username} → {self.banco.username}"

    def desactivar(self):
        self.activo = False
        self.save(update_fields=['activo'])


class Rol(models.Model):
    TIPOS_ROL = [
        ('superadmin', 'Super Administrador'),
        ('banco', 'Banco'),
        ('comercial', 'Comercial'),
        ('cliente', 'Cliente'),
        ('auditor', 'Auditor'),
    ]

    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='roles')
    tipo = models.CharField(max_length=20, choices=TIPOS_ROL)
    fondo = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    activo = models.BooleanField(default=True)
    banco_asignado = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='roles_banco_asignado', verbose_name='Banco asignado (si es comercial o cliente)'
    )
    comercial_asignado = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='roles_comercial_asignado', verbose_name='Comercial asignado (si es cliente)'
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('usuario', 'tipo')
        ordering = ['usuario__username']

    def __str__(self):
        return f"{self.usuario.username} - {self.get_tipo_display()}"


class Subordinacion(models.Model):
    jefe = models.ForeignKey(User, on_delete=models.CASCADE, related_name='subordinados')
    subordinado = models.ForeignKey(User, on_delete=models.CASCADE, related_name='jefes')
    activo = models.BooleanField(default=True)
    es_temporal = models.BooleanField(default=False)
    creado_en = models.DateTimeField(auto_now_add=True)

    # Comisión del subordinado
    porcentaje_comision = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0.00'),
        help_text="Porcentaje de comisión que recibe el comercial sobre las ganancias (0-100)"
    )
    # ✅ NUEVO: quién y cuándo definió el % (para auditoría)
    definido_por = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='porcentajes_definidos',
        help_text="Quién asignó el porcentaje actual (superadmin o banco)"
    )
    fecha_porcentaje = models.DateTimeField(
        null=True, blank=True,
        help_text="Última vez que se modificó el porcentaje"
    )

    class Meta:
        unique_together = ('jefe', 'subordinado')

    def __str__(self):
        return f"{self.jefe.username} → {self.subordinado.username} ({self.porcentaje_comision}%)"

# ============================================================
# MODELOS FINANCIEROS Y DE FONDOS
# ============================================================

class Fondo(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='fondos')
    forma_pago = models.ForeignKey('pagos.FormaPago', on_delete=models.CASCADE, null=True, blank=True, default=None)
    sorteo = models.ForeignKey('sorteos.Sorteo', on_delete=models.CASCADE, null=True, blank=True, default=None)
    asignado_por = models.ForeignKey(User, on_delete=models.CASCADE, related_name='fondos_asignados', null=True, blank=True, default=None)
    monto = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('usuario', 'sorteo', 'forma_pago')
        ordering = ['-creado_en']

    def __str__(self):
        return f"{self.usuario.username} - {self.monto}"


class MovimientoFondo(models.Model):
    TIPOS = [
        ('recarga', 'Recarga'),
        ('retiro', 'Retiro'),
        ('apuesta', 'Apuesta'),
        ('premio', 'Premio'),
        ('pago_deuda', 'Pago de Deuda'),
        ('ajuste', 'Ajuste'),
        ('comision', 'Comisión'),
        ('postpago', 'Recuperación de postpago'),
    ]
    ESTADOS = [
        ('pendiente', 'Pendiente'),
        ('confirmado', 'Confirmado'),
        ('rechazado', 'Rechazado'),
        ('autorizado', 'Autorizado'),
    ]

    emisor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='movimientos_emitidos', null=True, blank=True)
    receptor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='movimientos_recibidos')
    tipo = models.CharField(max_length=20, choices=TIPOS)
    estado = models.CharField(max_length=20, choices=ESTADOS, default='pendiente')
    forma_pago = models.ForeignKey('pagos.FormaPago', on_delete=models.SET_NULL, null=True, blank=True)
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    datos_transferencia = models.JSONField(default=dict, blank=True)
    nota = models.TextField(blank=True, default='')
    creado_en = models.DateTimeField(auto_now_add=True)
    confirmado_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-creado_en']

    def __str__(self):
        return f"{self.tipo} - {self.monto} - {self.receptor.username}"


class Comision(models.Model):
    TIPOS = [
        ('venta_diaria', 'Comisión por Venta Diaria'),
        ('forma_juego', 'Comisión por Forma de Juego'),
        ('sorteo', 'Comisión por Sorteo'),
    ]

    banco = models.ForeignKey(User, on_delete=models.CASCADE, related_name='comisiones_banco', null=True, blank=True, default=None)
    comercial = models.ForeignKey(User, on_delete=models.CASCADE, related_name='comisiones_comercial', null=True, blank=True, default=None)
    tipo = models.CharField(max_length=20, choices=TIPOS)
    porcentaje = models.DecimalField(max_digits=5, decimal_places=2)
    forma_juego = models.ForeignKey('jugadas.FormaJuego', on_delete=models.CASCADE, null=True, blank=True, default=None)
    sorteo = models.ForeignKey('sorteos.Sorteo', on_delete=models.CASCADE, null=True, blank=True, default=None)
    activo = models.BooleanField(default=True)
    es_global = models.BooleanField(default=False)
    heredado_de = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, default=None, related_name='herederos_comision')
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Comisión'
        verbose_name_plural = 'Comisiones'
        ordering = ['-creado_en']

    def __str__(self):
        return f"{self.banco.username if self.banco else 'Global'} → {self.comercial.username if self.comercial else 'Todos'} ({self.get_tipo_display()}: {self.porcentaje}%)"


class DosisPago(models.Model):
    banco = models.ForeignKey(User, on_delete=models.CASCADE, related_name='dosis_banco', null=True, blank=True, default=None)
    comercial = models.ForeignKey(User, on_delete=models.CASCADE, related_name='dosis_comercial', null=True, blank=True, default=None)
    sorteo = models.ForeignKey('sorteos.Sorteo', on_delete=models.CASCADE)
    forma_juego = models.ForeignKey('jugadas.FormaJuego', on_delete=models.CASCADE)
    forma_pago = models.ForeignKey('pagos.FormaPago', on_delete=models.CASCADE, null=True, blank=True, default=None)
    monto_por_peso = models.DecimalField(max_digits=10, decimal_places=2)
    activo = models.BooleanField(default=True)
    es_global = models.BooleanField(default=False)
    heredado_de = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, default=None, related_name='herederos_dosis')
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Dosis de Pago'
        verbose_name_plural = 'Dosis de Pago'
        unique_together = ('banco', 'comercial', 'sorteo', 'forma_juego', 'forma_pago')
        ordering = ['-creado_en']

    def __str__(self):
        return f"{self.comercial.username if self.comercial else 'Global'} → {self.forma_juego.nombre}: {self.monto_por_peso}x"


# ============================================================
# BONOS Y DEUDAS
# ============================================================

class Bono(models.Model):
    TIPO_CHOICES = [
        ('registro', 'Bono de registro'),
        ('bienvenida', 'Bienvenida'),
        ('referencia', 'Referencia'),
        ('recomendacion', 'Recomendación por referido'),
        ('asignado', 'Asignado por gestor'),
        ('recarga', 'Bono por recarga'),
    ]

    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bonos_recibidos')
    asignado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='bonos_asignados')
    # FIX_FP_BONO_POSTPAGO_V1: forma de pago asociada al bono (NULL = universal)
    forma_pago = models.ForeignKey(
        'pagos.FormaPago', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='bonos',
        verbose_name='Forma de pago asociada',
    )
    usuario_referente = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='bonos_referidos_otorgados')
    usuario_referido = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='bonos_por_referido')
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='asignado')
    monto = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Monto original del bono")
    saldo_restante = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    estado = models.CharField(
        max_length=20,
        choices=[
            ('activo', 'Activo'),
            ('agotado', 'Agotado'),
            ('anulado', 'Anulado'),
            ('pendiente', 'Pendiente'),
        ],
        default='activo'
    )
    apuestas_requeridas = models.PositiveIntegerField(default=0, help_text="Número mínimo de apuestas para activar")
    monto_apostado_requerido = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Monto mínimo apostado para activar")
    requiere_jugada_previa = models.BooleanField(default=False)
    metadata = models.JSONField(default=dict, blank=True, help_text="Datos adicionales en formato JSON")
    fecha_vencimiento = models.DateTimeField(
        null=True, blank=True, db_index=True,
        help_text='Fecha en que el bono expira. NULL = nunca expira.'
    )

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Bono'
        verbose_name_plural = 'Bonos'
        ordering = ['-creado_en']

    def __str__(self):
        return f"{self.usuario.username} - {self.get_tipo_display()} - ${self.saldo_restante}"

    @property
    def esta_vigente(self):
        """True si el bono no ha expirado."""
        from django.utils import timezone
        if self.estado != 'activo':
            return False
        if self.fecha_vencimiento is None:
            return True
        return self.fecha_vencimiento > timezone.now()

    @property
    def ya_vencio(self):
        """True si tiene fecha_vencimiento y ya pasó."""
        from django.utils import timezone
        if self.fecha_vencimiento is None:
            return False
        return self.fecha_vencimiento <= timezone.now()

    def marcar_expirado(self):
        """Marca el bono como expirado y guarda."""
        self.estado = 'expirado'
        self.save(update_fields=['estado', 'actualizado_en'])
    def activar(self, dias_vigencia=None):
        """Activa el bono. Si se pasa dias_vigencia, setea fecha_vencimiento."""
        from django.utils import timezone
        from datetime import timedelta
        self.estado = 'activo'
        # Reglas: registro y recomendacion_cliente vencen a 15 días
        # recomendacion_gestor NUNCA vence
        if dias_vigencia is None:
            if self.tipo in ('registro', 'recomendacion_cliente', 'recomendacion'):
                dias_vigencia = 15
            else:
                dias_vigencia = None  # nunca vence
        if dias_vigencia is not None:
            self.fecha_vencimiento = timezone.now() + timedelta(days=dias_vigencia)
        self.save(update_fields=['estado', 'fecha_vencimiento', 'actualizado_en'])


    def descontar(self, monto):
        if self.estado != 'activo':
            return False
        if monto <= 0:
            return False
        if monto > self.saldo_restante:
            return False
        self.saldo_restante -= monto
        if self.saldo_restante == 0:
            self.estado = 'agotado'
        self.save(update_fields=['saldo_restante', 'estado'])
        return True


class Deuda(models.Model):
    ESTADOS = [
        ('pendiente', 'Pendiente'),
        ('parcial', 'Pagada Parcialmente'),
        ('pagada', 'Pagada'),
        ('cancelada', 'Cancelada'),
        ('vencida', 'Vencida'),
    ]

    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='deudas')
    acreedor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='deudas_cobrar')
    forma_pago = models.ForeignKey('pagos.FormaPago', on_delete=models.CASCADE)
    monto_original = models.DecimalField(max_digits=10, decimal_places=2)
    monto_pagado = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    saldo_pendiente = models.DecimalField(max_digits=10, decimal_places=2)
    limite_autorizado = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    origen = models.CharField(max_length=200)
    estado = models.CharField(max_length=20, choices=ESTADOS, default='pendiente')
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_vencimiento = models.DateTimeField(null=True, blank=True, default=None)
    fecha_pago = models.DateTimeField(null=True, blank=True, default=None)
    creado_por = models.ForeignKey(User, on_delete=models.CASCADE, related_name='deudas_creadas', null=True, blank=True, default=None)
    metadata = models.JSONField(default=dict, blank=True)
    es_automatica = models.BooleanField(default=False)

    class Meta:
        ordering = ['-fecha_creacion']

    def __str__(self):
        return f"{self.usuario.username} debe {self.saldo_pendiente} a {self.acreedor.username}"


# ============================================================
# NOTIFICACIONES
# ============================================================

class Notificacion(models.Model):
    TIPOS = [
        ('recarga', 'Recarga'),
        ('apuesta', 'Apuesta'),
        ('deuda', 'Deuda'),
        ('premio', 'Premio'),
        ('pago', 'Pago'),
        ('sobrelimite', 'Sobrelimite'),
        ('postpago', 'Postpago'),
        ('info', 'Información'),
        ('suscripcion', 'Suscripción'),
        ('prestamo', 'Préstamo'),
    ]

    PRIORIDADES = [
        ('baja', 'Baja'),
        ('media', 'Media'),
        ('alta', 'Alta'),
        ('urgente', 'Urgente'),
    ]

    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notificaciones')
    tipo = models.CharField(max_length=20, choices=TIPOS)
    mensaje = models.TextField()
    leido = models.BooleanField(default=False)
    leido_en = models.DateTimeField(null=True, blank=True, verbose_name='Fecha de lectura')
    prioridad = models.CharField(max_length=10, choices=PRIORIDADES, default='media')
    categoria = models.CharField(max_length=20, blank=True, default='general')
    con_sonido = models.BooleanField(
        default=False,
        verbose_name='Reproducir sonido',
        help_text='True = el frontend reproduce sonido al recibir esta notificacion'
    )
    datos = models.JSONField(default=dict, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-creado_en']
        indexes = [
            models.Index(fields=['usuario', 'leido']),
            models.Index(fields=['usuario', 'creado_en']),
            models.Index(fields=['tipo']),
            models.Index(fields=['prioridad']),
        ]

    def __str__(self):
        return f"{self.usuario.username} - {self.tipo} - {self.mensaje[:50]}"

    def marcar_como_leida(self):
        if not self.leido:
            self.leido = True
            self.leido_en = timezone.now()
            self.save(update_fields=['leido', 'leido_en'])


# ============================================================
# CUADRE DIARIO
# ============================================================
class CuadreDiario(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='cuadres')
    fecha = models.DateField(db_index=True)

    inicial_tarjeta = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    inicial_saldo   = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    inicial_cash    = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

    ajuste_tarjeta  = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    ajuste_saldo    = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    ajuste_cash     = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

    envie_tarjeta   = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    envie_saldo     = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    envie_cash      = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

    recibi_tarjeta  = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    recibi_saldo    = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    recibi_cash     = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

    deuda_total     = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    pagado          = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

    cerrado = models.BooleanField(default=False)
    notas = models.TextField(blank=True)

    # FIX_CUADRE_JSON_V1: listas de transferencias por forma de pago
    # Formato: {'Tarjeta': [300, 300, 800], 'Saldo': [...], 'Cash': [...]}
    envie_lista = models.JSONField(
        default=dict, blank=True,
        verbose_name='Lista de envíos al banco por FP',
        help_text='Valores individuales de transferencias enviadas al banco'
    )
    recibi_lista = models.JSONField(
        default=dict, blank=True,
        verbose_name='Lista de recibidos del banco por FP',
        help_text='Valores individuales de transferencias recibidas del banco'
    )
    ajuste_lista = models.JSONField(
        default=dict, blank=True,
        verbose_name='Lista de ajustes por FP',
        help_text='Ajustes manuales del banco (positivos o negativos)'
    )

    # FIX_CUADRE_HERENCIA_V3: snapshots para herencia entre días
    fondo_inicial_snapshot = models.JSONField(
        default=dict, blank=True,
        verbose_name='Snapshot del fondo inicial por FP',
        help_text='Congela los iniciales del día para referencia histórica'
    )
    fondo_final_snapshot = models.JSONField(
        default=dict, blank=True,
        verbose_name='Snapshot del fondo final por FP',
        help_text='Se usa para heredar el inicial del día siguiente'
    )

    # ✅ NUEVOS: snapshot de la comisión al momento de creación (no retroactivo)
    porcentaje_comision_snapshot = models.DecimalField(
        max_digits=5, decimal_places=2,
        null=True, blank=True,
        help_text="% de comisión vigente cuando se creó este cuadre"
    )
    modalidad_comision_snapshot = models.CharField(
        max_length=20, null=True, blank=True,
        help_text="'general' o 'por_grupo' al momento de creación"
    )
    comision_calculada_snapshot = models.DecimalField(
        max_digits=12, decimal_places=2,
        null=True, blank=True,
        help_text="Comisión calculada con el % del momento"
    )
    comision_desglose_snapshot = models.JSONField(
        null=True, blank=True,
        help_text="Desglose por forma de pago al momento de creación"
    )

    class Meta:
        unique_together = ['usuario', 'fecha']
        ordering = ['-fecha']

    def __str__(self):
        return f"Cuadre {self.fecha} - {self.usuario.username}"
# ============================================================
# LÍMITES Y SOBRELÍMITES (CORREGIDOS)
# ============================================================


class HistorialTransferencia(models.Model):
    """
    Registra cada transferencia entre banco y comercial.
    Permite ver el historial completo de movimientos por cuadre.
    """
    ACCIONES = [
        ('agregar', 'Agregar'),
        ('modificar', 'Modificar'),
        ('eliminar', 'Eliminar'),
    ]
    TIPOS = [
        ('envio', 'Envío (comercial → banco)'),
        ('recibo', 'Recibo (banco → comercial)'),
    ]

    cuadre = models.ForeignKey(
        'CuadreDiario', on_delete=models.CASCADE,
        related_name='historial_transferencias'
    )
    banco = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='transferencias_como_banco'
    )
    comercial = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='transferencias_como_comercial'
    )
    tipo = models.CharField(max_length=20, choices=TIPOS)
    forma_pago = models.ForeignKey('pagos.FormaPago', on_delete=models.PROTECT)
    monto = models.DecimalField(max_digits=12, decimal_places=2)
    accion = models.CharField(max_length=20, choices=ACCIONES, default='agregar')
    monto_anterior = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text='Solo para modificaciones'
    )
    nota = models.TextField(blank=True, default='')
    creado_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='transferencias_creadas'
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-creado_en']
        verbose_name = 'Historial de transferencia'
        verbose_name_plural = 'Historial de transferencias'

    def __str__(self):
        return f"{self.banco.username} {'→' if self.tipo == 'envio' else '←'} {self.comercial.username}: ${self.monto}"

class LimiteApuesta(models.Model):
    banco = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='limites_banco',
        null=True, blank=True, default=None
    )
    comercial = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='limites_comercial',
        null=True, blank=True, default=None
    )
    sorteo = models.ForeignKey('sorteos.Sorteo', on_delete=models.CASCADE)
    forma_juego = models.ForeignKey('jugadas.FormaJuego', on_delete=models.CASCADE)
    forma_pago = models.ForeignKey(
        'pagos.FormaPago', on_delete=models.CASCADE,
        null=True, blank=True, default=None
    )

    monto_maximo = models.DecimalField(max_digits=10, decimal_places=2)
    monto_sobrelimite = models.DecimalField(
        max_digits=10, decimal_places=2,
        default=0.00,
        verbose_name='Monto sobrelímite',
        help_text='Monto máximo que se puede autorizar en situación de sobrelímite'
    )
    comision_extra_porcentaje = models.DecimalField(
        max_digits=5, decimal_places=2,
        default=1.0,
        help_text='% extra que se aplica a la comisión del comercial sobre el sobrelímite'
    )

    activo = models.BooleanField(default=True)
    es_global = models.BooleanField(default=False)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('banco', 'comercial', 'sorteo', 'forma_juego', 'forma_pago')
        ordering = ['-creado_en']

    def __str__(self):
        nombre = f"{self.comercial.username if self.comercial else 'Global'} - "
        nombre += f"{self.sorteo.nombre} - {self.forma_juego.nombre}"
        nombre += f": Límite ${self.monto_maximo} | Sobrelímite ${self.monto_sobrelimite}"
        return nombre


class Sobrelimite(models.Model):
    """
    Modelo para gestionar solicitudes de sobrelímite.
    """
    ESTADO_COMPENSACION = [
        ('pendiente', 'Pendiente'),
        ('aceptado', 'Aceptado'),
        ('rechazado', 'Rechazado'),
    ]

    jugada = models.ForeignKey(
        'jugadas.Jugada', on_delete=models.CASCADE,
        null=True, blank=True, related_name='sobrelimites'
    )
    comercial = models.ForeignKey(
        User, on_delete=models.CASCADE,
        null=True, blank=True, related_name='sobrelimites_comercial'
    )
    banco = models.ForeignKey(
        User, on_delete=models.CASCADE,
        null=True, blank=True, related_name='sobrelimites_banco'
    )
    limite_aplicado = models.DecimalField(          # ✅ 4 espacios de sangría
        max_digits=10, decimal_places=2,
        default=0.00,
        verbose_name='Límite aplicado'
    )
    monto_excedido = models.DecimalField(           # ✅ 4 espacios de sangría
        max_digits=10, decimal_places=2,
        default=0.00,
        verbose_name='Monto excedido'
    )
    monto_solicitado = models.DecimalField(         # ✅ 4 espacios de sangría
        max_digits=10, decimal_places=2,
        verbose_name='Monto solicitado'
    )
    estado_compensacion = models.CharField(
        max_length=20, choices=ESTADO_COMPENSACION,
        default='pendiente', verbose_name='Estado de compensación'
    )
    fecha = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de solicitud')
    fecha_compensacion = models.DateTimeField(
        null=True, blank=True, verbose_name='Fecha de compensación'
    )
    monto_compensado = models.DecimalField(
        max_digits=10, decimal_places=2,
        null=True, blank=True, verbose_name='Monto compensado'
    )
    banco_solicitado = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='sobrelimites_recibidos',
        verbose_name='Banco al que se solicitó compensación'
    )

    class Meta:
        verbose_name = 'Sobrelímite'
        verbose_name_plural = 'Sobrelímites'
        ordering = ['-fecha']

    def __str__(self):
        return f"Sobrelímite #{self.id} - {self.monto_solicitado} ({self.get_estado_compensacion_display()})"

# ============================================================
# PRÉSTAMOS
# ============================================================

class Prestamo(models.Model):
    ESTADOS = [
        ('solicitado', 'Solicitado'),
        ('aprobado', 'Aprobado'),
        ('pagado', 'Pagado'),
        ('rechazado', 'Rechazado'),
        ('vencido', 'Vencido'),
    ]

    solicitante = models.ForeignKey(User, on_delete=models.CASCADE, related_name='prestamos_solicitados')
    prestamista = models.ForeignKey(User, on_delete=models.CASCADE, related_name='prestamos_otorgados')
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    monto_pagado = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    saldo_pendiente = models.DecimalField(max_digits=10, decimal_places=2)
    interes = models.DecimalField(max_digits=5, decimal_places=2, default=0, blank=True, null=True)
    motivo = models.TextField(blank=True, null=True, default='')
    estado = models.CharField(max_length=20, choices=ESTADOS, default='solicitado')
    fecha_solicitud = models.DateTimeField(auto_now_add=True)
    fecha_aprobacion = models.DateTimeField(null=True, blank=True, default=None)
    fecha_vencimiento = models.DateTimeField(null=True, blank=True, default=None)
    fecha_pago = models.DateTimeField(null=True, blank=True, default=None)
    aprobado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, default=None, related_name='prestamos_aprobados')
    comercial_comun = models.ForeignKey(User, on_delete=models.CASCADE, related_name='prestamos_comunes', null=True, blank=True, default=None)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-fecha_solicitud']

    def __str__(self):
        return f"Préstamo #{self.id} - {self.solicitante.username} → {self.prestamista.username}"

    def aprobar(self, aprobado_por=None):
        from django.db import transaction
        if self.estado != 'solicitado':
            return False, "Este préstamo ya no está en estado de solicitud"
        fondos_prestamista = Fondo.objects.filter(usuario=self.prestamista, activo=True)
        saldo_prestamista = sum(f.monto for f in fondos_prestamista)
        if saldo_prestamista < self.monto:
            return False, f"El prestamista no tiene fondos suficientes. Saldo: ${saldo_prestamista}"
        with transaction.atomic():
            monto_restante = self.monto
            for fondo in fondos_prestamista.order_by('id'):
                if monto_restante <= 0:
                    break
                if fondo.monto >= monto_restante:
                    fondo.monto -= monto_restante
                    monto_restante = 0
                else:
                    monto_restante -= fondo.monto
                    fondo.monto = 0
                fondo.save()
            forma_pago = fondos_prestamista.first().forma_pago if fondos_prestamista.exists() else None
            if forma_pago:
                fondo_solicitante, _ = Fondo.objects.get_or_create(
                    usuario=self.solicitante,
                    forma_pago=forma_pago,
                    defaults={'monto': 0, 'activo': True, 'asignado_por': aprobado_por or self.prestamista}
                )
                fondo_solicitante.monto += self.monto
                fondo_solicitante.save()
            MovimientoFondo.objects.create(
                emisor=self.prestamista,
                receptor=self.solicitante,
                forma_pago=forma_pago,
                monto=self.monto,
                tipo='ajuste',
                estado='confirmado',
                datos_transferencia={'prestamo_id': self.id},
                nota=f"Préstamo aprobado por {aprobado_por.username if aprobado_por else 'sistema'}"
            )
            self.estado = 'aprobado'
            self.fecha_aprobacion = timezone.now()
            self.aprobado_por = aprobado_por
            self.saldo_pendiente = self.monto
            self.save()
            _crear_notificacion(
                usuario=self.solicitante,
                tipo='prestamo',
                mensaje=f"💰 Préstamo de ${self.monto} aprobado por {self.prestamista.username}.",
                datos={'prestamo_id': self.id, 'monto': float(self.monto), 'saldo_pendiente': float(self.saldo_pendiente)},
                prioridad='alta',
                categoria='financiera'
            )
            _crear_notificacion(
                usuario=self.prestamista,
                tipo='prestamo',
                mensaje=f"💰 Has otorgado un préstamo de ${self.monto} a {self.solicitante.username}.",
                datos={'prestamo_id': self.id, 'monto': float(self.monto)},
                prioridad='alta',
                categoria='financiera'
            )
        return True, "Préstamo aprobado y fondos transferidos."

    def pagar_cuota(self, monto):
        from django.db import transaction
        if self.estado not in ['solicitado', 'aprobado']:
            return False, "Este préstamo no está activo"
        if monto <= 0:
            return False, "El monto debe ser mayor a 0"
        if monto > self.saldo_pendiente:
            return False, f"El monto excede el saldo pendiente (${self.saldo_pendiente})"
        fondos_solicitante = Fondo.objects.filter(usuario=self.solicitante, activo=True)
        saldo_solicitante = sum(f.monto for f in fondos_solicitante)
        if saldo_solicitante < monto:
            return False, f"El solicitante no tiene fondos suficientes. Saldo: ${saldo_solicitante}"
        with transaction.atomic():
            monto_restante = monto
            for fondo in fondos_solicitante.order_by('id'):
                if monto_restante <= 0:
                    break
                if fondo.monto >= monto_restante:
                    fondo.monto -= monto_restante
                    monto_restante = 0
                else:
                    monto_restante -= fondo.monto
                    fondo.monto = 0
                fondo.save()
            forma_pago = fondos_solicitante.first().forma_pago if fondos_solicitante.exists() else None
            if forma_pago:
                fondo_prestamista, _ = Fondo.objects.get_or_create(
                    usuario=self.prestamista,
                    forma_pago=forma_pago,
                    defaults={'monto': 0, 'activo': True, 'asignado_por': self.solicitante}
                )
                fondo_prestamista.monto += monto
                fondo_prestamista.save()
            self.monto_pagado += monto
            self.saldo_pendiente -= monto
            if self.saldo_pendiente == 0:
                self.estado = 'pagado'
                self.fecha_pago = timezone.now()
            self.save()
            MovimientoFondo.objects.create(
                emisor=self.solicitante,
                receptor=self.prestamista,
                forma_pago=forma_pago,
                monto=monto,
                tipo='pago_deuda',
                estado='confirmado',
                datos_transferencia={'prestamo_id': self.id, 'cuota': True},
                nota=f"Pago de cuota de préstamo"
            )
            _crear_notificacion(
                usuario=self.prestamista,
                tipo='pago',
                mensaje=f"💰 Has recibido un pago de ${monto} de {self.solicitante.username} por el préstamo #{self.id}.",
                datos={'prestamo_id': self.id, 'monto_pagado': float(monto), 'saldo_pendiente': float(self.saldo_pendiente)},
                prioridad='media',
                categoria='financiera'
            )
            if self.saldo_pendiente == 0:
                _crear_notificacion(
                    usuario=self.solicitante,
                    tipo='prestamo',
                    mensaje=f"🎉 Has completado el pago del préstamo #{self.id}. ¡Deuda saldada!",
                    datos={'prestamo_id': self.id, 'monto_total': float(self.monto)},
                    prioridad='alta',
                    categoria='financiera'
                )
        return True, f"Pago de ${monto} registrado. Saldo pendiente: ${self.saldo_pendiente}"


# ============================================================
# SUSCRIPCIÓN DE BANCOS
# ============================================================

class SuscripcionBanco(models.Model):
    TIPO_PAGO_CHOICES = [
        ('mensual', 'Mensual'),
        ('diario', 'Diario'),
        ('por_uso', 'Por uso (tarifa por ganancia)'),
    ]

    banco = models.OneToOneField(User, on_delete=models.CASCADE, related_name='suscripcion', verbose_name='Banco')
    fecha_ascenso = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de ascenso')
    periodo = models.DurationField(default=timedelta(days=30), verbose_name='Período de suscripción')
    fecha_vencimiento = models.DateTimeField(verbose_name='Fecha de vencimiento')
    activo = models.BooleanField(default=True, verbose_name='Activo')
    tipo_pago = models.CharField(max_length=20, choices=TIPO_PAGO_CHOICES, default='mensual', verbose_name='Tipo de pago')
    cuota_fija = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='Cuota fija (mensual/diaria)')
    porcentaje_ganancia = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='% de ganancia (para "por_uso")')

    comerciales_permitidos = models.PositiveIntegerField(default=0, verbose_name='Comerciales permitidos')
    solicitud_pendiente = models.BooleanField(default=False, verbose_name='Solicitud pendiente')
    solicitud_tipo = models.CharField(
        max_length=20,
        choices=[
            ('recursos', 'Solicitar recursos'),
            ('comerciales', 'Solicitar comerciales'),
            ('ambos', 'Solicitar ambos'),
        ],
        blank=True, null=True, verbose_name='Tipo de solicitud'
    )
    solicitud_detalle = models.JSONField(default=dict, blank=True, verbose_name='Detalle de solicitud')

    usuarios_desactivados = models.JSONField(
        default=list, blank=True,
        verbose_name='Usuarios desactivados por vencimiento',
        help_text='IDs de banco + comerciales desactivados al vencer. Se usan para reactivar al renovar.'
    )

    ultimo_pago = models.DateTimeField(null=True, blank=True, verbose_name='Último pago')
    proximo_pago = models.DateTimeField(null=True, blank=True, verbose_name='Próximo pago')
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Suscripción de banco'
        verbose_name_plural = 'Suscripciones de bancos'
        ordering = ['-fecha_ascenso']

    def __str__(self):
        return f"Suscripción de {self.banco.username} - {'Activa' if self.esta_activo() else 'Inactiva'}"

    def save(self, *args, **kwargs):
        if not self.fecha_vencimiento:
            self.fecha_vencimiento = timezone.now() + self.periodo
        super().save(*args, **kwargs)

    def esta_activo(self):
        return self.activo and self.fecha_vencimiento > timezone.now()

    def renovar(self):
        self.fecha_vencimiento = timezone.now() + self.periodo
        self.activo = True
        self.save()

    def desactivar(self):
        self.activo = False
        self.save()

    def calcular_monto_pendiente(self):
        if self.tipo_pago == 'mensual':
            return self.cuota_fija
        elif self.tipo_pago == 'diario':
            return self.cuota_fija
        elif self.tipo_pago == 'por_uso':
            return Decimal('0.00')
        return Decimal('0.00')

    def cambiar_tipo_pago(self, nuevo_tipo, fecha_solicitud=None):
        if not fecha_solicitud:
            fecha_solicitud = timezone.now()
        dias_restantes = (self.fecha_vencimiento - fecha_solicitud).days
        if dias_restantes <= 1 and dias_restantes >= 0:
            self.tipo_pago = nuevo_tipo
            self.save()
            return True
        return False

    def recursos_activos(self):
        from .models import RecursoAsignado
        return RecursoAsignado.objects.filter(banco=self.banco, activo=True)

    def comerciales_activos(self):
        return Subordinacion.objects.filter(jefe=self.banco, activo=True).count()

    def costo_mensual(self):
        recursos = self.recursos_activos().count()
        comerciales = self.comerciales_activos()
        return Decimal(recursos * comerciales * 5)

    def puede_ascender_comercial(self):
        return self.comerciales_activos() < self.comerciales_permitidos


# ============================================================
# RECURSOS ASIGNADOS
# ============================================================

class RecursoAsignado(models.Model):
    TIPO_RECURSO = [
        ('sorteo', 'Sorteo'),
        ('forma_juego', 'Forma de Juego'),
        ('forma_pago', 'Forma de Pago'),
    ]

    banco = models.ForeignKey(User, on_delete=models.CASCADE, related_name='recursos_asignados_banco', null=True, blank=True)
    comercial = models.ForeignKey(User, on_delete=models.CASCADE, related_name='recursos_asignados_comercial', null=True, blank=True)
    tipo = models.CharField(max_length=20, choices=TIPO_RECURSO)
    sorteo = models.ForeignKey('sorteos.Sorteo', on_delete=models.CASCADE, null=True, blank=True)
    forma_juego = models.ForeignKey('jugadas.FormaJuego', on_delete=models.CASCADE, null=True, blank=True)
    forma_pago = models.ForeignKey('pagos.FormaPago', on_delete=models.CASCADE, null=True, blank=True)
    fecha_asignacion = models.DateTimeField(auto_now_add=True)
    activo = models.BooleanField(default=True)
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='recursos_creados')

    class Meta:
        verbose_name = 'Recurso asignado'
        verbose_name_plural = 'Recursos asignados'
        unique_together = ('banco', 'comercial', 'tipo', 'sorteo', 'forma_juego', 'forma_pago')

    def __str__(self):
        nombre_recurso = ""
        if self.tipo == 'sorteo' and self.sorteo:
            nombre_recurso = self.sorteo.nombre
        elif self.tipo == 'forma_juego' and self.forma_juego:
            nombre_recurso = self.forma_juego.nombre
        elif self.tipo == 'forma_pago' and self.forma_pago:
            nombre_recurso = self.forma_pago.nombre
        destino = f"Banco: {self.banco.username}" if self.banco else f"Comercial: {self.comercial.username}"
        return f"{destino} - {self.get_tipo_display()}: {nombre_recurso}"


# ============================================================
# VÍAS DE PAGO DE GESTORES
# ============================================================

class ViaPago(models.Model):
    TIPO_CHOICES = [
        ('tarjeta', 'Tarjeta de Crédito/Débito'),
        ('monedero', 'Monedero Electrónico'),
        ('cuenta', 'Cuenta Bancaria'),
        ('efectivo', 'Efectivo'),
        ('cripto', 'Criptomoneda'),
        ('otros', 'Otros'),
    ]

    DIRECCION_CHOICES = [
        ('recibir', 'Recibir (cobrar)'),
        ('enviar', 'Enviar (pagar)'),
        ('ambos', 'Ambos'),
    ]

    gestor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='vias_pago', verbose_name='Gestor')
    forma_pago = models.ForeignKey('pagos.FormaPago', on_delete=models.CASCADE, related_name='vias_pago', verbose_name='Forma de pago')
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='otros', verbose_name='Tipo de vía')
    nombre = models.CharField(max_length=100, verbose_name='Nombre/alias de la vía', help_text='Ej: "Tarjeta Visa", "Cuenta Banco X"')
    numero = models.CharField(max_length=50, verbose_name='Número de cuenta/tarjeta', help_text='Número de la tarjeta, cuenta o monedero')
    numero_tarjeta = models.CharField(
        max_length=19, blank=True, null=True,
        verbose_name='Número de tarjeta',
        help_text='16 dígitos en formato 4x4 (ej: 1234 5678 9012 3456)'
    )
    telefono = models.CharField(
        max_length=20, blank=True, null=True,
        verbose_name='Teléfono',
        help_text='Para saldo móvil o como dato adicional de tarjeta'
    )
    datos = models.JSONField(default=dict, blank=True, verbose_name='Datos adicionales (JSON)')
    notificar_a = models.CharField(max_length=100, blank=True, null=True, verbose_name='Notificar a', help_text='Teléfono o email para notificaciones')
    direccion = models.CharField(
        max_length=10, choices=DIRECCION_CHOICES,
        default='ambos', verbose_name='Dirección de la vía',
        help_text='¿Para recibir pagos, enviar pagos o ambos?'
    )
    activo = models.BooleanField(default=True, verbose_name='Activo')
    es_por_defecto = models.BooleanField(default=False, verbose_name='Vía por defecto')
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Vía de Pago'
        verbose_name_plural = 'Vías de Pago'
        ordering = ['-es_por_defecto', '-creado_en']

    def __str__(self):
        return f"{self.gestor.username} - {self.forma_pago.nombre} - {self.nombre}"

    def save(self, *args, **kwargs):
        if self.es_por_defecto:
            ViaPago.objects.filter(
                gestor=self.gestor,
                forma_pago=self.forma_pago,
                direccion=self.direccion,
                es_por_defecto=True
            ).exclude(id=self.id).update(es_por_defecto=False)
        super().save(*args, **kwargs)

    def marcar_por_defecto(self):
        self.es_por_defecto = True
        self.save()


# ============================================================
# SOLICITUDES DE RECARGA
# ============================================================

class SolicitudRecarga(models.Model):
    ESTADOS = [
        ('pendiente', 'Pendiente'),
        ('aceptada', 'Aceptada'),
        ('pagada', 'Pagada'),
        ('rechazada', 'Rechazada'),
        ('cancelada', 'Cancelada'),
    ]

    cliente = models.ForeignKey(User, on_delete=models.CASCADE, related_name='solicitudes_recarga', verbose_name='Cliente')
    gestor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='solicitudes_atendidas', verbose_name='Gestor')
    forma_pago = models.ForeignKey('pagos.FormaPago', on_delete=models.CASCADE, verbose_name='Forma de pago')
    via_pago = models.ForeignKey(ViaPago, on_delete=models.SET_NULL, null=True, blank=True, related_name='solicitudes', verbose_name='Vía de pago seleccionada')
    monto = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Monto solicitado')
    monto_abonado = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='Monto abonado')
    estado = models.CharField(max_length=20, choices=ESTADOS, default='pendiente', verbose_name='Estado')
    mensaje_cliente = models.TextField(blank=True, null=True, verbose_name='Mensaje del cliente')
    mensaje_gestor = models.TextField(blank=True, null=True, verbose_name='Mensaje del gestor')
    datos_adicionales = models.JSONField(default=dict, blank=True, verbose_name='Datos adicionales')
    fecha_solicitud = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de solicitud')
    fecha_respuesta = models.DateTimeField(null=True, blank=True, verbose_name='Fecha de respuesta')
    fecha_pago = models.DateTimeField(null=True, blank=True, verbose_name='Fecha de pago')
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='recargas_creadas', verbose_name='Creado por')

    class Meta:
        verbose_name = 'Solicitud de Recarga'
        verbose_name_plural = 'Solicitudes de Recarga'
        ordering = ['-fecha_solicitud']

    def __str__(self):
        return f"{self.cliente.username} → {self.gestor.username} (${self.monto}) - {self.get_estado_display()}"

    def aceptar(self, via_pago_id=None):
        if self.estado != 'pendiente':
            return False, "La solicitud ya no está pendiente."
        if via_pago_id:
            try:
                via = ViaPago.objects.get(id=via_pago_id, gestor=self.gestor, activo=True)
                self.via_pago = via
            except ViaPago.DoesNotExist:
                return False, "La vía de pago no existe o no pertenece al gestor."
        self.estado = 'aceptada'
        self.fecha_respuesta = timezone.now()
        self.save()
        _crear_notificacion(
            usuario=self.cliente,
            tipo='recarga',
            mensaje=f"✅ Tu solicitud de recarga de ${self.monto} ha sido aceptada por {self.gestor.username}.",
            datos={'solicitud_id': self.id, 'monto': float(self.monto), 'gestor': self.gestor.username, 'via_pago': self.via_pago.nombre if self.via_pago else None},
            prioridad='alta',
            categoria='financiera'
        )
        return True, "Solicitud aceptada."

    def pagar(self, monto_abonado=None):
        if self.estado != 'aceptada':
            return False, "La solicitud no está en estado aceptada."
        monto = monto_abonado or self.monto
        if monto > self.monto:
            return False, f"El monto abonado (${monto}) excede el monto solicitado (${self.monto})."
        fondo, created = Fondo.objects.get_or_create(
            usuario=self.cliente,
            forma_pago=self.forma_pago,
            defaults={'monto': 0, 'activo': True, 'asignado_por': self.gestor}
        )
        fondo.monto += monto
        fondo.save()
        MovimientoFondo.objects.create(
            emisor=self.gestor,
            receptor=self.cliente,
            forma_pago=self.forma_pago,
            monto=monto,
            tipo='recarga',
            estado='confirmado',
            datos_transferencia={'solicitud_id': self.id},
            nota=f"Recarga por solicitud #{self.id}"
        )
        self.monto_abonado = monto
        self.estado = 'pagada'
        self.fecha_pago = timezone.now()
        self.save()
        _crear_notificacion(
            usuario=self.cliente,
            tipo='recarga',
            mensaje=f"💰 Se ha abonado ${monto} a tu cuenta por recarga solicitada a {self.gestor.username}.",
            datos={'solicitud_id': self.id, 'monto': float(monto), 'gestor': self.gestor.username},
            prioridad='alta',
            categoria='financiera'
        )
        return True, f"Pago de ${monto} registrado."

    def rechazar(self, motivo=None):
        if self.estado != 'pendiente':
            return False, "La solicitud ya no está pendiente."
        self.estado = 'rechazada'
        self.fecha_respuesta = timezone.now()
        if motivo:
            self.mensaje_gestor = motivo
        self.save()
        _crear_notificacion(
            usuario=self.cliente,
            tipo='recarga',
            mensaje=f"❌ Tu solicitud de recarga de ${self.monto} ha sido rechazada por {self.gestor.username}.",
            datos={'solicitud_id': self.id, 'motivo': motivo},
            prioridad='media',
            categoria='financiera'
        )
        return True, "Solicitud rechazada."


# ============================================================
# SOLICITUDES DE COBRO DE PREMIOS
# ============================================================

class SolicitudCobroPremio(models.Model):
    ESTADOS = [
        ('pendiente', 'Pendiente'),
        ('aceptada', 'Aceptada'),
        ('pagada', 'Pagada'),
        ('rechazada', 'Rechazada'),
        ('cancelada', 'Cancelada'),
    ]

    cliente = models.ForeignKey(User, on_delete=models.CASCADE, related_name='solicitudes_cobro', verbose_name='Cliente')
    gestor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='cobros_atendidos', verbose_name='Gestor')
    forma_pago = models.ForeignKey('pagos.FormaPago', on_delete=models.CASCADE, verbose_name='Forma de pago')
    via_pago = models.ForeignKey(ViaPago, on_delete=models.SET_NULL, null=True, blank=True, related_name='cobros', verbose_name='Vía de pago seleccionada')
    monto = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Monto a cobrar')
    monto_pagado = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='Monto pagado')
    estado = models.CharField(max_length=20, choices=ESTADOS, default='pendiente', verbose_name='Estado')
    mensaje_cliente = models.TextField(blank=True, null=True, verbose_name='Mensaje del cliente')
    mensaje_gestor = models.TextField(blank=True, null=True, verbose_name='Mensaje del gestor')
    jugadas_ids = models.JSONField(default=list, blank=True, verbose_name='IDs de jugadas ganadoras')
    fecha_solicitud = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de solicitud')
    fecha_respuesta = models.DateTimeField(null=True, blank=True, verbose_name='Fecha de respuesta')
    fecha_pago = models.DateTimeField(null=True, blank=True, verbose_name='Fecha de pago')

    class Meta:
        verbose_name = 'Solicitud de Cobro de Premio'
        verbose_name_plural = 'Solicitudes de Cobro de Premios'
        ordering = ['-fecha_solicitud']

    def __str__(self):
        return f"{self.cliente.username} → {self.gestor.username} (${self.monto}) - {self.get_estado_display()}"

    def aceptar(self, via_pago_id=None):
        if self.estado != 'pendiente':
            return False, "La solicitud ya no está pendiente."
        if via_pago_id:
            try:
                via = ViaPago.objects.get(id=via_pago_id, gestor=self.gestor, activo=True)
                self.via_pago = via
            except ViaPago.DoesNotExist:
                return False, "La vía de pago no existe o no pertenece al gestor."
        self.estado = 'aceptada'
        self.fecha_respuesta = timezone.now()
        self.save()
        _crear_notificacion(
            usuario=self.cliente,
            tipo='premio',
            mensaje=f"✅ Tu solicitud de cobro de premio por ${self.monto} ha sido aceptada por {self.gestor.username}.",
            datos={'solicitud_id': self.id, 'monto': float(self.monto), 'gestor': self.gestor.username, 'via_pago': self.via_pago.nombre if self.via_pago else None},
            prioridad='alta',
            categoria='financiera'
        )
        return True, "Solicitud aceptada."

    def pagar(self):
        if self.estado != 'aceptada':
            return False, "La solicitud no está en estado aceptada."
        fondo = Fondo.objects.filter(usuario=self.cliente, forma_pago=self.forma_pago, activo=True).first()
        if not fondo or fondo.monto < self.monto:
            return False, f"El cliente no tiene fondos suficientes en {self.forma_pago.nombre}."
        fondo.monto -= self.monto
        fondo.save()
        MovimientoFondo.objects.create(
            emisor=self.cliente,
            receptor=self.gestor,
            forma_pago=self.forma_pago,
            monto=self.monto,
            tipo='premio',
            estado='confirmado',
            datos_transferencia={'solicitud_cobro_id': self.id},
            nota=f"Pago de premio por solicitud #{self.id}"
        )
        self.monto_pagado = self.monto
        self.estado = 'pagada'
        self.fecha_pago = timezone.now()
        self.save()
        _crear_notificacion(
            usuario=self.cliente,
            tipo='premio',
            mensaje=f"💰 Se ha pagado ${self.monto} por premios a través de {self.gestor.username}.",
            datos={'solicitud_id': self.id, 'monto': float(self.monto), 'gestor': self.gestor.username},
            prioridad='alta',
            categoria='financiera'
        )
        return True, f"Pago de ${self.monto} registrado."

    def rechazar(self, motivo=None):
        if self.estado != 'pendiente':
            return False, "La solicitud ya no está pendiente."
        self.estado = 'rechazada'
        self.fecha_respuesta = timezone.now()
        if motivo:
            self.mensaje_gestor = motivo
        self.save()
        _crear_notificacion(
            usuario=self.cliente,
            tipo='premio',
            mensaje=f"❌ Tu solicitud de cobro de premio por ${self.monto} ha sido rechazada por {self.gestor.username}.",
            datos={'solicitud_id': self.id, 'motivo': motivo},
            prioridad='media',
            categoria='financiera'
        )
        return True, "Solicitud rechazada."


# ============================================================
# SOLICITUDES DE RETIRO DE SALDO (por cliente)
# ============================================================

class SolicitudRetiro(models.Model):
    """
    Retiro voluntario de saldo del cliente.
    El cliente pide a su gestor que le transfiera X monto de su Fondo
    a una vía propia (número de tarjeta, teléfono, etc.).

    Reglas:
    - monto <= Fondo del cliente en esa forma de pago.
    - Si el Fondo está en negativo (por postpago) → no puede retirar.
    - La vía es la del cliente (no del gestor).
    - El gestor confirma al transferir realmente.
    """
    ESTADOS = [
        ('pendiente', 'Pendiente'),
        ('aceptada', 'Aceptada'),
        ('pagada', 'Pagada'),
        ('rechazada', 'Rechazada'),
        ('cancelada', 'Cancelada'),
    ]

    cliente = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='solicitudes_retiro',
        verbose_name='Cliente'
    )
    gestor = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='retiros_atendidos',
        verbose_name='Gestor'
    )
    forma_pago = models.ForeignKey(
        'pagos.FormaPago', on_delete=models.CASCADE,
        verbose_name='Forma de pago'
    )
    via_pago = models.ForeignKey(
        ViaPago, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='retiros',
        verbose_name='Vía de pago del cliente (a dónde recibir)'
    )
    monto = models.DecimalField(
        max_digits=10, decimal_places=2,
        verbose_name='Monto a retirar'
    )
    monto_pagado = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        verbose_name='Monto pagado'
    )
    estado = models.CharField(
        max_length=20, choices=ESTADOS, default='pendiente',
        verbose_name='Estado'
    )
    mensaje_cliente = models.TextField(
        blank=True, null=True,
        verbose_name='Mensaje del cliente'
    )
    mensaje_gestor = models.TextField(
        blank=True, null=True,
        verbose_name='Mensaje del gestor'
    )
    datos_via_cliente = models.JSONField(
        default=dict, blank=True,
        verbose_name='Datos de la vía de retiro (foto congelada)'
    )
    fecha_solicitud = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de solicitud'
    )
    fecha_respuesta = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Fecha de respuesta'
    )
    fecha_pago = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Fecha de pago'
    )

    class Meta:
        verbose_name = 'Solicitud de Retiro'
        verbose_name_plural = 'Solicitudes de Retiro'
        ordering = ['-fecha_solicitud']

    def __str__(self):
        return f"{self.cliente.username} → {self.gestor.username} (${self.monto}) - {self.get_estado_display()}"

    def aceptar(self, via_pago_id=None):
        if self.estado != 'pendiente':
            return False, "La solicitud ya no está pendiente."
        if via_pago_id:
            try:
                via = ViaPago.objects.get(id=via_pago_id, gestor=self.cliente, activo=True)
                self.via_pago = via
            except ViaPago.DoesNotExist:
                return False, "La vía no existe o no pertenece al cliente."
        self.estado = 'aceptada'
        self.fecha_respuesta = timezone.now()
        self.save()
        _crear_notificacion(
            usuario=self.cliente,
            tipo='pago',
            mensaje=f"✅ Tu solicitud de retiro de ${self.monto} fue aceptada por {self.gestor.username}.",
            datos={'solicitud_id': self.id, 'monto': float(self.monto), 'gestor': self.gestor.username},
            prioridad='alta',
            categoria='financiera'
        )
        return True, "Solicitud aceptada."

    def pagar(self, monto_pagado=None):
        if self.estado != 'aceptada':
            return False, "La solicitud no está en estado aceptada."
        monto = monto_pagado or self.monto

        fondo = Fondo.objects.filter(
            usuario=self.cliente,
            forma_pago=self.forma_pago,
            activo=True
        ).first()
        if not fondo:
            return False, f"El cliente no tiene fondo en {self.forma_pago.nombre}."
        if fondo.monto < monto:
            return False, f"Saldo insuficiente. Disponible: ${fondo.monto}."
        if fondo.monto < 0:
            return False, "El cliente tiene saldo negativo (postpago). No puede retirar."

        fondo.monto -= monto
        fondo.save(update_fields=['monto', 'actualizado_en'])

        MovimientoFondo.objects.create(
            emisor=self.cliente,
            receptor=self.gestor,
            forma_pago=self.forma_pago,
            monto=monto,
            tipo='retiro',
            estado='confirmado',
            datos_transferencia={
                'solicitud_retiro_id': self.id,
                'via_pago_id': self.via_pago.id if self.via_pago else None,
                'datos_via': self.datos_via_cliente or {},
            },
            nota=f"Retiro por solicitud #{self.id}"
        )

        self.monto_pagado = monto
        self.estado = 'pagada'
        self.fecha_pago = timezone.now()
        self.save()
        _crear_notificacion(
            usuario=self.cliente,
            tipo='pago',
            mensaje=f"💰 Retiro de ${monto} pagado por {self.gestor.username}.",
            datos={'solicitud_id': self.id, 'monto': float(monto)},
            prioridad='alta',
            categoria='financiera'
        )
        return True, f"Pago de ${monto} registrado."

    def rechazar(self, motivo=None):
        if self.estado != 'pendiente':
            return False, "La solicitud ya no está pendiente."
        self.estado = 'rechazada'
        self.fecha_respuesta = timezone.now()
        if motivo:
            self.mensaje_gestor = motivo
        self.save()
        _crear_notificacion(
            usuario=self.cliente,
            tipo='pago',
            mensaje=f"❌ Tu solicitud de retiro de ${self.monto} fue rechazada por {self.gestor.username}.",
            datos={'solicitud_id': self.id, 'motivo': motivo},
            prioridad='media',
            categoria='financiera'
        )
        return True, "Solicitud rechazada."


class LimiteCliente(models.Model):
    cliente = models.ForeignKey(User, on_delete=models.CASCADE, related_name='limites')
    sorteo = models.ForeignKey('sorteos.Sorteo', on_delete=models.CASCADE)
    forma_juego = models.ForeignKey('jugadas.FormaJuego', on_delete=models.CASCADE)
    forma_pago = models.ForeignKey('pagos.FormaPago', on_delete=models.CASCADE, null=True, blank=True)

    limite_base = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    sobrelimite_base = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    limite_disponible = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    sobrelimite_disponible = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('cliente', 'sorteo', 'forma_juego', 'forma_pago')

    def consumir(self, monto):
        if monto <= 0:
            return (0, 0, False)

        monto_restante = monto
        limite_consumido = Decimal('0')
        sobrelimite_consumido = Decimal('0')
        es_sobrelimite = False

        if self.limite_disponible > 0:
            tomar = min(self.limite_disponible, monto_restante)
            self.limite_disponible -= tomar
            limite_consumido += tomar
            monto_restante -= tomar

        if monto_restante > 0 and self.sobrelimite_disponible > 0:
            tomar = min(self.sobrelimite_disponible, monto_restante)
            self.sobrelimite_disponible -= tomar
            sobrelimite_consumido += tomar
            monto_restante -= tomar
            es_sobrelimite = True

        self.save()
        return (limite_consumido, sobrelimite_consumido, es_sobrelimite)


class NumeroRestringido(models.Model):
    sorteo = models.ForeignKey(
        'sorteos.Sorteo', on_delete=models.CASCADE,
        verbose_name='Sorteo', related_name='restricciones'
    )
    forma_juego = models.ForeignKey(
        'jugadas.FormaJuego', on_delete=models.CASCADE,
        verbose_name='Forma de juego', related_name='restricciones'
    )
    valor = models.CharField(
        max_length=50, verbose_name='Valor restringido',
        help_text='Ej: "55", "1234", "Pa", "T4", "D8"'
    )
    fecha_vencimiento = models.DateField(
        verbose_name='Fecha de vencimiento',
        help_text='La restricción se eliminará automáticamente al llegar esta fecha.'
    )
    gestor = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='restricciones_creadas', verbose_name='Gestor'
    )
    activo = models.BooleanField(default=True, verbose_name='Activo')
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Número restringido'
        verbose_name_plural = 'Números restringidos'
        ordering = ['sorteo', 'forma_juego', 'valor']
        unique_together = ('sorteo', 'forma_juego', 'valor', 'gestor')
        indexes = [
            models.Index(fields=['gestor', 'sorteo', 'activo']),
            models.Index(fields=['sorteo', 'forma_juego']),
        ]

    def __str__(self):
        return f"{self.sorteo.nombre} - {self.forma_juego.nombre} - {self.valor} ({self.gestor.username})"

    @classmethod
    def es_numero_restringido(cls, valor, sorteo, gestor=None, fecha=None):
        if fecha is None:
            fecha = timezone.now().date()
        qs = cls.objects.filter(
            sorteo=sorteo,
            valor=valor,
            activo=True,
            fecha_vencimiento__gte=fecha
        )
        if gestor:
            qs = qs.filter(gestor=gestor)
        return qs.exists()


class AuditLog(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    accion = models.CharField(max_length=100)
    detalles = models.JSONField()
    fecha = models.DateTimeField(auto_now_add=True)


# ============================================================
# POSTPAGOS (CRÉDITO ACUMULATIVO)
# ============================================================
class PostpagoCliente(models.Model):
    cliente = models.OneToOneField(User, on_delete=models.CASCADE, related_name='postpago')
    saldo = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    ultima_notificacion = models.DateTimeField(null=True, blank=True, verbose_name='Última notificación enviada')

    def __str__(self):
        return f"{self.cliente.username} - Saldo postpago: ${self.saldo}"

    def descontar(self, monto, tipo='ajuste', origen_id=None, concepto=''):
        if monto <= 0:
            return Decimal('0.00')
        descuento = min(monto, self.saldo)
        self.saldo -= descuento
        self.save()
        return descuento


class Postpago(models.Model):
    """
    FASE1_POSTPAGO_V1
    Representa la deuda o saldo a favor del cliente con un gestor en una FP.
    - saldo = 0   → sin deuda
    - saldo < 0   → el cliente debe al gestor (postpago negativo)
    - saldo > 0   → saldo a favor del cliente (raro, no debería pasar)
    """
    cliente = models.ForeignKey(User, on_delete=models.CASCADE, related_name='postpagos_recibidos')
    gestor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='postpagos_otorgados')
    forma_pago = models.ForeignKey(
        'pagos.FormaPago', on_delete=models.PROTECT,
        related_name='postpagos',
        verbose_name='Forma de pago asociada',
    )
    saldo = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        help_text='0 = sin deuda, negativo = deuda del cliente, positivo = saldo a favor',
    )
    # Campos legacy conservados para compatibilidad
    monto = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    monto_pendiente = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de adición')
    actualizado_en = models.DateTimeField(auto_now=True)
    concepto = models.CharField(max_length=200, blank=True, default='', verbose_name='Concepto')
    activo = models.BooleanField(default=True, verbose_name='Activo (para anular)')

    class Meta:
        unique_together = [['cliente', 'gestor', 'forma_pago']]
        ordering = ['-fecha_creacion']
        verbose_name = 'Postpago'
        verbose_name_plural = 'Postpagos'

    def __str__(self):
        return f"{self.cliente.username} ↔ {self.gestor.username} [{self.forma_pago.nombre}]: ${self.saldo}"


class PostpagoDescuento(models.Model):
    # FK_POSTPAGO_DESCUENTO_V1
    TIPO_CHOICES = [
        ('premio', 'Premio'),
        ('recarga', 'Recarga'),
        ('apuesta', 'Apuesta'),
        ('ajuste', 'Ajuste manual'),
    ]

    cliente = models.ForeignKey(User, on_delete=models.CASCADE, related_name='postpagos_descuentos')
    postpago = models.ForeignKey('Postpago', on_delete=models.SET_NULL, null=True, blank=True, related_name='descuentos')
    monto = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Monto descontado')
    fecha = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de descuento')
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='ajuste')
    origen_id = models.PositiveIntegerField(null=True, blank=True, verbose_name='ID del origen (jugada/recarga)')
    concepto = models.CharField(max_length=200, blank=True, default='', verbose_name='Concepto')

    class Meta:
        ordering = ['-fecha']
        verbose_name = 'Descuento de postpago'
        verbose_name_plural = 'Descuentos de postpago'

    def __str__(self):
        return f"{self.cliente.username} → -${self.monto} ({self.get_tipo_display()})"


# ============================================================
# CONFIGURACIÓN DE COMISIONES
# ============================================================

class ConfiguracionComision(models.Model):
    """
    Define cómo se descuenta la comisión a un gestor (comercial o banco o superadmin).

    Modalidades:
    - 'general': un solo % sobre el total del día.
    - 'por_grupo': un % distinto por cada forma de pago.
    """
    MODALIDAD_CHOICES = [
        ('general', 'Porcentaje general'),
        ('por_grupo', 'Porcentaje por forma de pago'),
    ]

    usuario = models.OneToOneField(
        User, on_delete=models.CASCADE,
        related_name='configuracion_comision'
    )
    definido_por = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='comisiones_definidas',
        help_text='Quién definió esta config (auto si es el propio usuario)'
    )
    modalidad = models.CharField(
        max_length=20, choices=MODALIDAD_CHOICES, default='general'
    )
    porcentaje_general = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0.00'),
        help_text='Solo se usa si modalidad="general"'
    )
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Configuración de Comisión'
        verbose_name_plural = 'Configuraciones de Comisión'

    def __str__(self):
        return f"{self.usuario.username} — {self.get_modalidad_display()}"


class ComisionFormaPago(models.Model):
    """
    Desglose de % por forma de pago cuando modalidad='por_grupo'.
    """
    configuracion = models.ForeignKey(
        ConfiguracionComision, on_delete=models.CASCADE,
        related_name='comisiones_fp'
    )
    forma_pago = models.ForeignKey(
        'pagos.FormaPago', on_delete=models.CASCADE
    )
    porcentaje = models.DecimalField(max_digits=5, decimal_places=2)

    class Meta:
        unique_together = ['configuracion', 'forma_pago']
        verbose_name = 'Comisión por forma de pago'
        verbose_name_plural = 'Comisiones por forma de pago'

    def __str__(self):
        return f"{self.configuracion.usuario.username} — {self.forma_pago.nombre}: {self.porcentaje}%"


# ============================================================
# HISTORIAL DE COMISIONES (AUDITORÍA)
# ============================================================

class HistorialComision(models.Model):
    """
    Registra cada cambio de % de comisión para auditoría.
    Permite ver "quién cambió el % de X el día Y".
    """
    TIPO_CAMBIO = [
        ('creacion', 'Creación'),
        ('modificacion', 'Modificación'),
        ('eliminacion', 'Eliminación'),
    ]

    usuario_afectado = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='historial_comisiones',
        help_text='Usuario a quien se le cambió el %'
    )
    definido_por = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='cambios_comisiones_realizados',
        help_text='Quién hizo el cambio'
    )
    tipo_cambio = models.CharField(max_length=20, choices=TIPO_CAMBIO)

    porcentaje_anterior = models.DecimalField(
        max_digits=5, decimal_places=2,
        null=True, blank=True
    )
    porcentaje_nuevo = models.DecimalField(
        max_digits=5, decimal_places=2,
        null=True, blank=True
    )
    modalidad_anterior = models.CharField(
        max_length=20, null=True, blank=True
    )
    modalidad_nueva = models.CharField(
        max_length=20, null=True, blank=True
    )

    motivo = models.TextField(blank=True, default='')
    creado_en = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'Historial de Comisión'
        verbose_name_plural = 'Historial de Comisiones'
        ordering = ['-creado_en']
        indexes = [
            models.Index(fields=['usuario_afectado', '-creado_en']),
            models.Index(fields=['definido_por', '-creado_en']),
        ]

    def __str__(self):
        return f"{self.usuario_afectado.username}: {self.porcentaje_anterior}% → {self.porcentaje_nuevo}% por {self.definido_por.username if self.definido_por else 'sistema'}"

# ============================================================
# CONFIGURACIÓN DE RECURSOS POR GESTOR
# ============================================================
class ConfiguracionRecursos(models.Model):
    """
    Reglas de pago configurables por gestor (banco, comercial o superadmin).
    """
    usuario = models.OneToOneField(
        User, on_delete=models.CASCADE,
        related_name='config_recursos',
    )
    pagar_fijo_como_corrido = models.BooleanField(
        default=False,
        verbose_name='Pagar fijo como corrido',
        help_text='Si esta activo, cuando sale un numero como fijo, los clientes que apostaron a corrido por ese numero tambien ganan.'
    )
    actualizado_por = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='config_recursos_actualizadas',
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Configuracion de Recursos'
        verbose_name_plural = 'Configuraciones de Recursos'

    def __str__(self):
        return f"{self.usuario.username} - fijo-como-corrido: {self.pagar_fijo_como_corrido}"
