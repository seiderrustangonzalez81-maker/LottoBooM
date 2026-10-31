# jugadas/models.py
# -*- coding: utf-8 -*-
import base64
import hashlib
import uuid
from decimal import Decimal

from cryptography.fernet import Fernet
from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import (
    post_delete, post_save, pre_save, pre_delete,
)
from django.dispatch import receiver
from django.utils import timezone

from roles.models import Deuda, Fondo, MovimientoFondo, Rol
from sorteos.helpers import get_hora_cierre

# ============================================================
# POSTPAGO
# ============================================================
class FormaJuego(models.Model):
    nombre = models.CharField(max_length=50, unique=True)
    digitos_esperados = models.PositiveSmallIntegerField(
        default=2,
        help_text="Número de dígitos que se esperan para este juego",
    )
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Forma de Juego"
        verbose_name_plural = "Formas de Juego"

    def __str__(self):
        return self.nombre


# ============================================================
# BOLETA
# ============================================================
class Boleta(models.Model):
    """
    Agrupa una o varias Jugadas cargadas en un mismo acto de apuesta.
    Es la unidad de operación para editar, cancelar, duplicar o eliminar.
    """
    ESTADOS = [
        ('activa',    'Activa'),
        ('cancelada', 'Cancelada'),
        ('parcial',   'Parcialmente cancelada'),
        ('anulada',   'Anulada'),
    ]

    referencia = models.CharField(
        max_length=32, unique=True, db_index=True, editable=False,
        verbose_name='Referencia',
        help_text='Código legible único (ej: BOL-20260917-A3F8)',
    )

    usuario = models.ForeignKey(
        User, on_delete=models.PROTECT,
        related_name='boletas', verbose_name='Cliente',
        help_text='Dueño real de la boleta (el cliente)',
    )
    destinatario = models.ForeignKey(
        User, on_delete=models.PROTECT,
        related_name='boletas_recibidas', verbose_name='Gestor',
        help_text='Gestor al que se le acredita la boleta',
    )
    comercial = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='boletas_como_comercial', verbose_name='Comercial',
        help_text='Quién la cargó si fue un comercial en nombre del gestor',
    )
    creado_por = models.ForeignKey(
        User, on_delete=models.PROTECT,
        related_name='boletas_creadas', verbose_name='Creada por',
        help_text='Usuario autenticado que ejecutó la acción',
    )

    forma_pago = models.ForeignKey(
        'pagos.FormaPago', on_delete=models.PROTECT,
        null=True, blank=True, verbose_name='Forma de pago',
    )
    fecha_sorteo = models.DateField(verbose_name='Fecha del sorteo')

    monto_total = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Monto total',
    )
    premios_total = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Premios totales',
    )

    estado = models.CharField(
        max_length=16, choices=ESTADOS, default='activa', db_index=True,
        verbose_name='Estado',
    )

    cancelada_en = models.DateTimeField(null=True, blank=True)
    cancelada_por = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='boletas_canceladas',
    )
    motivo_cancelacion = models.TextField(blank=True, default='')

    metadata = models.JSONField(default=dict, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True, db_index=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Boleta'
        verbose_name_plural = 'Boletas'
        ordering = ['-creado_en']
        indexes = [
            models.Index(fields=['usuario', '-creado_en']),
            models.Index(fields=['destinatario', '-creado_en']),
            models.Index(fields=['estado', '-creado_en']),
        ]

    def __str__(self):
        return f"{self.referencia} · {self.usuario.username} · ${self.monto_total}"

    def save(self, *args, **kwargs):
        if not self.referencia:
            self.referencia = self._generar_referencia()
        super().save(*args, **kwargs)

    def _generar_referencia(self):
        """Genera algo como BOL-20260917-A3F8, garantizando unicidad."""
        hoy = timezone.localdate().strftime('%Y%m%d')
        sufijo = uuid.uuid4().hex[:4].upper()
        candidato = f"BOL-{hoy}-{sufijo}"
        contador = 0
        while Boleta.objects.filter(referencia=candidato).exists():
            contador += 1
            candidato = f"BOL-{hoy}-{sufijo}-{contador}"
        return candidato

    def esta_activa(self):
        return self.estado == 'activa'

    def puede_editar(self):
        return self.estado == 'activa'

    def puede_cancelar(self):
        return self.estado == 'activa'

    def recalcular_totales(self, save=True):
        """Recomputa monto_total y premios_total desde las jugadas."""
        agg = self.jugadas.aggregate(
            m=models.Sum('monto'),
            p=models.Sum('monto_premio'),
        )
        self.monto_total = agg['m'] or Decimal('0.00')
        self.premios_total = agg['p'] or Decimal('0.00')
        if save:
            self.save(update_fields=['monto_total', 'premios_total', 'actualizado_en'])


# ============================================================
# JUGADA
# ============================================================
class Jugada(models.Model):
    """Modelo principal de apuestas (línea de una Boleta)."""
    ESTADOS = [
        ('pendiente', 'Pendiente'),
        ('confirmada', 'Confirmada'),
        ('ganadora', 'Ganadora'),
        ('perdedora', 'Perdedora'),
        ('cancelada', 'Cancelada'),
        ('modificada', 'Modificada'),
        ('pendiente_sobrelimite', 'Pendiente Sobrelímite'),
    ]

    usuario = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='jugadas_enviadas',
    )
    destinatario = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='jugadas_recibidas',
        null=True, blank=True,
    )
    comercial = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='jugadas_comercial',
    )
    forma_juego = models.ForeignKey(
        FormaJuego, on_delete=models.CASCADE, related_name='jugadas',
    )
    sorteo = models.ForeignKey(
        'sorteos.Sorteo', on_delete=models.CASCADE, related_name='jugadas',
    )
    forma_pago = models.ForeignKey(
        'pagos.FormaPago', on_delete=models.CASCADE,
        null=True, blank=True, related_name='jugadas',
    )

    boleta = models.ForeignKey(
        'Boleta', on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='jugadas', verbose_name='Boleta',
        help_text='Boleta a la que pertenece esta línea. Null = jugada antigua.',
    )

    numero = models.CharField(max_length=20)
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    fecha = models.DateTimeField(default=timezone.now)
    fecha_sorteo = models.DateField(null=True, blank=True)
    estado = models.CharField(max_length=25, choices=ESTADOS, default='pendiente')

    monto_premio = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    autorizada_por = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='jugadas_autorizadas',
        null=True, blank=True,
    )
    sobrelimite = models.BooleanField(default=False)
    saldo_antes = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    saldo_despues = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    modificado_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='jugadas_modificadas',
    )
    modificado_en = models.DateTimeField(null=True, blank=True)

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)
    metadata = models.JSONField(default=dict, blank=True, help_text="Datos adicionales de la jugada")

    class Meta:
        ordering = ['-fecha']
        indexes = [
            models.Index(fields=['usuario', 'estado']),
            models.Index(fields=['sorteo', 'fecha_sorteo']),
            models.Index(fields=['destinatario', 'estado']),
            models.Index(fields=['forma_pago', 'estado']),
            models.Index(fields=['fecha_sorteo']),
            models.Index(fields=['sobrelimite']),
            models.Index(fields=['boleta']),
        ]
        verbose_name = "Jugada"
        verbose_name_plural = "Jugadas"

    def __str__(self):
        dest = self.destinatario.username if self.destinatario else '?'
        return f"{self.usuario.username} → {dest} - {self.sorteo.nombre} - ${self.monto}"

    def puede_modificar(self):
        """Verifica si la jugada puede ser modificada (antes del cierre del sorteo)."""
        try:
            cierre = get_hora_cierre(self.sorteo)
            if not cierre:
                return False
            return cierre > timezone.now() and self.estado in ['pendiente', 'confirmada']
        except Exception:
            return False

    def _es_autorizador(self, usuario):
        """Verifica si el usuario tiene rol de autorizador."""
        try:
            rol = Rol.objects.get(usuario=usuario, activo=True)
            return rol.tipo in ['superadmin', 'banco', 'comercial']
        except Rol.DoesNotExist:
            return False

    def _get_banco(self, usuario):
        """Obtiene el banco asociado a un usuario (si tiene uno)."""
        try:
            from roles.models import Subordinacion
            sub = Subordinacion.objects.filter(subordinado=usuario, activo=True).first()
            if sub and sub.jefe and sub.jefe.roles.filter(tipo='banco', activo=True).exists():
                return sub.jefe
        except Exception:
            pass
        return None

    def notificar_modificacion(self, usuario_modificador, cambios=None):
        """Envía notificaciones de modificación a los implicados."""
        from roles.models import Notificacion

        datos = {
            'jugada_id': self.id,
            'modificado_por': usuario_modificador.id,
            'cambios': cambios or {},
            'fecha': timezone.now().isoformat(),
        }

        if self.destinatario and self.destinatario != usuario_modificador:
            Notificacion.objects.create(
                usuario=self.destinatario,
                tipo='modificacion',
                mensaje=f"🔁 Jugada #{self.id} en {self.sorteo.nombre} modificada por {usuario_modificador.username}.",
                datos=datos, leido=False,
            )

        if self.destinatario:
            banco = self._get_banco(self.destinatario)
            if banco and banco != usuario_modificador:
                Notificacion.objects.create(
                    usuario=banco,
                    tipo='modificacion',
                    mensaje=f"🔁 Jugada #{self.id} de {self.destinatario.username} en {self.sorteo.nombre} modificada por {usuario_modificador.username}.",
                    datos=datos, leido=False,
                )

        for admin in User.objects.filter(roles__tipo='superadmin', roles__activo=True):
            if admin != usuario_modificador:
                Notificacion.objects.create(
                    usuario=admin,
                    tipo='modificacion',
                    mensaje=f"🔁 Jugada #{self.id} de {self.usuario.username} en {self.sorteo.nombre} modificada por {usuario_modificador.username}.",
                    datos=datos, leido=False,
                )

    def verificar_fondos(self):
        """Verifica si el usuario tiene fondos suficientes en la forma de pago seleccionada."""
        if not self.forma_pago:
            raise ValueError("La apuesta debe tener una forma de pago asignada")

        try:
            fondo = Fondo.objects.get(usuario=self.usuario, forma_pago=self.forma_pago, activo=True)
            saldo_disponible = fondo.monto
        except Fondo.DoesNotExist:
            saldo_disponible = 0

        self.saldo_antes = saldo_disponible
        return saldo_disponible >= self.monto

    def procesar_apuesta(self, autorizado_por=None):
        """Procesa la apuesta: descuenta fondos, crea deuda si aplica, registra movimientos."""
        if not self.forma_pago:
            return False, "Debes seleccionar una forma de pago"

        tiene_fondos = self.verificar_fondos()

        if autorizado_por and self._es_autorizador(autorizado_por):
            self.autorizada_por = autorizado_por
            if not tiene_fondos and self.saldo_antes is not None:
                monto_faltante = self.monto - self.saldo_antes
                if monto_faltante > 0:
                    deuda = Deuda.objects.create(
                        usuario=self.usuario,
                        acreedor=autorizado_por,
                        forma_pago=self.forma_pago,
                        monto_original=monto_faltante,
                        saldo_pendiente=monto_faltante,
                        origen=f"Apuesta #{self.id} - {self.sorteo.nombre}",
                        creado_por=autorizado_por,
                    )
                    self.metadata['deuda_id'] = deuda.id
        else:
            if not tiene_fondos:
                saldo_actual = self.saldo_antes if self.saldo_antes is not None else 0
                return False, f"Saldo insuficiente. Disponible: {saldo_actual}, Necesario: {self.monto}"

        try:
            fondo, created = Fondo.objects.get_or_create(
                usuario=self.usuario,
                forma_pago=self.forma_pago,
                defaults={
                    'monto': -self.monto if autorizado_por else 0,
                    'activo': True,
                    'asignado_por': autorizado_por or self.usuario,
                },
            )
            if not created:
                fondo.monto -= self.monto
                fondo.save(update_fields=['monto'])
            self.saldo_despues = fondo.monto
        except Exception as e:
            return False, f"Error al procesar el fondo: {e}"

        MovimientoFondo.objects.create(
            emisor=self.usuario,
            receptor=self.destinatario or autorizado_por,
            forma_pago=self.forma_pago,
            monto=self.monto,
            tipo='apuesta',
            estado='confirmado' if not autorizado_por else 'autorizado',
            datos_transferencia=f"Apuesta #{self.id} - Sorteo: {self.sorteo.nombre}",
            nota=f"Apuesta {'autorizada' if autorizado_por else 'realizada'} por "
                 f"{autorizado_por.username if autorizado_por else 'cliente'}",
        )

        self.estado = 'confirmada'
        self.save(update_fields=['estado', 'saldo_despues', 'autorizada_por', 'metadata'])

        return True, f"Apuesta {'autorizada' if autorizado_por else 'realizada'} exitosamente"

    def marcar_como_ganadora(self, monto_premio):
        self.estado = 'ganadora'
        self.monto_premio = monto_premio
        self.save(update_fields=['estado', 'monto_premio'])

    def marcar_como_perdedora(self):
        self.estado = 'perdedora'
        self.save(update_fields=['estado'])


# ============================================================
# SEÑALES: mantener totales de la Boleta en sync
# ============================================================
@receiver(post_save, sender=Jugada)
def _sync_boleta_on_jugada_save(sender, instance, **kwargs):
    if instance.boleta_id:
        instance.boleta.recalcular_totales()


@receiver(post_delete, sender=Jugada)
def _sync_boleta_on_jugada_delete(sender, instance, **kwargs):
    if not instance.boleta_id:
        return
    boleta = Boleta.objects.filter(id=instance.boleta_id).first()
    if boleta:
        boleta.recalcular_totales()


# ============================================================
# CLIENTES OFFLINE
# ============================================================
def _get_fernet():
    """
    Clave Fernet derivada del SECRET_KEY.
    ⚠️ Si cambias SECRET_KEY, los passwords cifrados existentes serán indescifrables.
    """
    key = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


class ClienteOffline(models.Model):
    """
    Marca a un User como "cliente offline" (creado por un gestor para un cliente
    sin teléfono ni acceso real a la web).

    - Un solo User en auth_user (regla de unicidad global).
    - Solo el gestor creador (y su banco + superadmin) puede ver su contraseña.
    - El teléfono es ficticio del rango reservado +5350...
    """
    user = models.OneToOneField(
        User, on_delete=models.CASCADE,
        related_name='cliente_offline',
    )
    creado_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='clientes_offline_creados',
    )
    telefono_offline = models.CharField(
        max_length=20, unique=True, db_index=True,
        verbose_name='Teléfono ficticio',
    )
    password_cifrada = models.BinaryField(
        null=True, blank=True,
        verbose_name='Password cifrada',
        help_text='Password original, cifrada con Fernet. Se borra cuando el cliente la cambia.',
    )
    password_cambiada_por_cliente = models.BooleanField(
        default=False,
        verbose_name='¿Cliente cambió la contraseña?',
    )
    fecha_alta = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = 'Cliente Offline'
        verbose_name_plural = 'Clientes Offline'
        ordering = ['-fecha_alta']

    def __str__(self):
        return f"{self.user.username} ({self.telefono_offline})"

    def set_password_cifrada(self, raw_password: str):
        f = _get_fernet()
        self.password_cifrada = f.encrypt(raw_password.encode())
        self.password_cambiada_por_cliente = False
        self.save(update_fields=['password_cifrada', 'password_cambiada_por_cliente'])

    def get_password_cifrada(self):
        """Devuelve el password en claro si está disponible, o None."""
        if self.password_cambiada_por_cliente or not self.password_cifrada:
            return None
        try:
            f = _get_fernet()
            return f.decrypt(bytes(self.password_cifrada)).decode()
        except Exception:
            return None

    def invalidar_password_cifrada(self):
        """Se llama cuando el User cambia su contraseña."""
        self.password_cifrada = None
        self.password_cambiada_por_cliente = True
        self.save(update_fields=['password_cifrada', 'password_cambiada_por_cliente'])


# ============================================================
# SEÑALES: ClienteOffline ↔ User
# ============================================================
@receiver(pre_save, sender=User)
def _detectar_cambio_password(sender, instance, **kwargs):
    """
    Si un User que es cliente offline cambia su contraseña, invalidamos
    la copia cifrada para que el gestor ya no pueda verla.
    """
    if not instance.pk:
        return  # creación, no aplica

    try:
        original = User.objects.only('password').get(pk=instance.pk)
    except User.DoesNotExist:
        return

    if original.password != instance.password:
        try:
            ClienteOffline.objects.filter(user_id=instance.pk).update(
                password_cifrada=None,
                password_cambiada_por_cliente=True,
            )
        except Exception:
            # La tabla aún no existe (migración pendiente) — ignorar silenciosamente
            pass


@receiver(pre_delete, sender=User)
def _reasignar_clientes_offline_al_borrar_gestor(sender, instance, **kwargs):
    """
    Red de seguridad: si alguien borra un gestor (aunque recomendamos soft delete),
    reasignamos sus clientes offline al banco superior.

    Import local de Subordinacion para evitar circular imports con roles.models.
    """
    from roles.models import Subordinacion

    sub = Subordinacion.objects.filter(
        subordinado=instance, activo=True
    ).select_related('jefe').first()

    banco_superior = None
    if sub and sub.jefe:
        if sub.jefe.is_superuser or sub.jefe.roles.filter(tipo='banco', activo=True).exists():
            banco_superior = sub.jefe

    if not banco_superior:
        return

    for co in ClienteOffline.objects.filter(creado_por=instance):
        Subordinacion.objects.filter(
            jefe=instance, subordinado=co.user, activo=True
        ).update(jefe=banco_superior)
        co.creado_por = banco_superior
        co.save(update_fields=['creado_por'])