# usuarios/models.py
# -*- coding: utf-8 -*-
from django.db import models
from django.conf import settings
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
import secrets
import string


class Perfil(models.Model):
    """
    Perfil extendido del usuario con datos adicionales y sistema de referidos.
    """
    usuario = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='perfil',
        verbose_name='Usuario'
    )
    telefono = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name='Tel\u00e9fono'
    )
    codigo_referido = models.CharField(
        max_length=20,
        unique=True,
        blank=True,
        null=True,
        verbose_name='C\u00f3digo de referido'
    )
    referido_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='referidos_realizados',
        verbose_name='Referido por'
    )
    direccion = models.TextField(
        blank=True,
        null=True,
        verbose_name='Direcci\u00f3n'
    )
    fecha_nacimiento = models.DateField(
        null=True,
        blank=True,
        verbose_name='Fecha de nacimiento'
    )
    foto_perfil = models.ImageField(
        upload_to='perfiles/',
        null=True,
        blank=True,
        verbose_name='Foto de perfil'
    )
    activo = models.BooleanField(
        default=True,
        verbose_name='Activo'
    )
    creado_en = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Creado en'
    )
    actualizado_en = models.DateTimeField(
        auto_now=True,
        verbose_name='Actualizado en'
    )

    last_activity = models.DateTimeField(
        null=True, blank=True, db_index=True,
        verbose_name='Última actividad',
        help_text='Se actualiza con throttle. No escribir en cada request.'
    )


    # FIX_PRESTAMO_V1: badge 'Nuevo' en sidebar
    prestamo_badge_visto = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Perfil'
        verbose_name_plural = 'Perfiles'
        ordering = ['usuario__username']

    def __str__(self):
        return f"Perfil de {self.usuario.username}"

    def generar_codigo_referido(self, longitud=8):
        """
        Genera un c\u00f3digo de referido \u00fanico alfanum\u00e9rico.
        """
        caracteres = string.ascii_uppercase + string.digits
        while True:
            codigo = ''.join(secrets.choice(caracteres) for _ in range(longitud))
            if not Perfil.objects.filter(codigo_referido=codigo).exists():
                return codigo

    def save(self, *args, **kwargs):
        if not self.codigo_referido:
            self.codigo_referido = self.generar_codigo_referido()
        super().save(*args, **kwargs)

    def get_referidos(self):
        """
        Retorna los usuarios que fueron referidos por este usuario.
        """
        return User.objects.filter(perfil__referido_por=self.usuario)

    def get_total_referidos(self):
        """
        Retorna la cantidad de usuarios referidos.
        """
        return self.get_referidos().count()


# ============================================================
# SE\u00d1AL PARA CREAR PERFIL AUTOM\u00c1TICAMENTE AL REGISTRAR USUARIO
# ============================================================

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def crear_actualizar_perfil_usuario(sender, instance, created, **kwargs):
    perfil, creado = Perfil.objects.get_or_create(usuario=instance)
    if creado and not perfil.codigo_referido:
        perfil.codigo_referido = perfil.generar_codigo_referido()
        perfil.save()
    elif not perfil.codigo_referido:
        perfil.codigo_referido = perfil.generar_codigo_referido()
        perfil.save(update_fields=['codigo_referido'])
