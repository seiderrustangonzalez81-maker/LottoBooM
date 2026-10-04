from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal

from .models import (
    Rol, Subordinacion, Fondo, MovimientoFondo, Bono,
    Deuda, Notificacion, CuadreDiario, Prestamo,
    SuscripcionBanco, DosisPago, LimiteApuesta
)


class RolModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='pass123')

    def test_creacion_rol(self):
        rol = Rol.objects.create(usuario=self.user, tipo='cliente', fondo=0, activo=True)
        self.assertEqual(rol.tipo, 'cliente')
        self.assertTrue(rol.activo)

    def test_rol_unico_por_tipo(self):
        Rol.objects.create(usuario=self.user, tipo='cliente', activo=True)
        with self.assertRaises(Exception):
            Rol.objects.create(usuario=self.user, tipo='cliente', activo=True)


class SubordinacionModelTest(TestCase):
    def setUp(self):
        self.jefe = User.objects.create_user(username='jefe', password='pass123')
        self.subordinado = User.objects.create_user(username='sub', password='pass123')

    def test_subordinacion(self):
        sub = Subordinacion.objects.create(jefe=self.jefe, subordinado=self.subordinado, activo=True)
        self.assertEqual(str(sub), "jefe → sub")

    def test_subordinacion_unica(self):
        Subordinacion.objects.create(jefe=self.jefe, subordinado=self.subordinado, activo=True)
        with self.assertRaises(Exception):
            Subordinacion.objects.create(jefe=self.jefe, subordinado=self.subordinado, activo=True)


class FondoModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='fondouser', password='pass123')

    def test_fondo_creacion(self):
        fondo = Fondo.objects.create(usuario=self.user, monto=Decimal('100.00'), activo=True)
        self.assertEqual(fondo.monto, Decimal('100.00'))


class BonoModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='bonouser', password='pass123')

    def test_bono_creacion(self):
        bono = Bono.objects.create(
            usuario=self.user,
            tipo='registro',
            monto=50,
            saldo_restante=50,
            estado='activo'
        )
        self.assertEqual(bono.saldo_restante, 50)

    def test_bono_descontar(self):
        bono = Bono.objects.create(
            usuario=self.user,
            tipo='registro',
            monto=50,
            saldo_restante=50,
            estado='activo'
        )
        result = bono.descontar(20)
        self.assertTrue(result)
        self.assertEqual(bono.saldo_restante, 30)

    def test_bono_descontar_agotado(self):
        bono = Bono.objects.create(
            usuario=self.user,
            tipo='registro',
            monto=50,
            saldo_restante=50,
            estado='activo'
        )
        bono.descontar(50)
        self.assertEqual(bono.estado, 'agotado')


class NotificacionModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='notifuser', password='pass123')

    def test_notificacion_creacion(self):
        notif = Notificacion.objects.create(
            usuario=self.user,
            tipo='info',
            mensaje='Test mensaje',
            leido=False
        )
        self.assertFalse(notif.leido)

    def test_marcar_como_leida(self):
        notif = Notificacion.objects.create(
            usuario=self.user,
            tipo='info',
            mensaje='Test',
            leido=False
        )
        notif.marcar_como_leida()
        self.assertTrue(notif.leido)
        self.assertIsNotNone(notif.leido_en)


class PrestamoModelTest(TestCase):
    def setUp(self):
        self.solicitante = User.objects.create_user(username='solicitante', password='pass123')
        self.prestamista = User.objects.create_user(username='prestamista', password='pass123')

    def test_prestamo_creacion(self):
        prestamo = Prestamo.objects.create(
            solicitante=self.solicitante,
            prestamista=self.prestamista,
            monto=Decimal('100.00'),
            saldo_pendiente=Decimal('100.00'),
            estado='solicitado'
        )
        self.assertEqual(prestamo.estado, 'solicitado')


class SuscripcionBancoModelTest(TestCase):
    def setUp(self):
        self.banco = User.objects.create_user(username='bancouser', password='pass123')

    def test_suscripcion_creacion(self):
        sus = SuscripcionBanco.objects.create(
            banco=self.banco,
            fecha_vencimiento=timezone.now() + timezone.timedelta(days=30),
            activo=True,
            tipo_pago='mensual'
        )
        self.assertTrue(sus.esta_activo())

    def test_suscripcion_vencida(self):
        sus = SuscripcionBanco.objects.create(
            banco=self.banco,
            fecha_vencimiento=timezone.now() - timezone.timedelta(days=1),
            activo=True,
            tipo_pago='mensual'
        )
        self.assertFalse(sus.esta_activo())


class SignalTest(TestCase):
    def test_crear_suscripcion_al_ascender_banco(self):
        user = User.objects.create_user(username='nuevobanco', password='pass123')
        self.assertFalse(SuscripcionBanco.objects.filter(banco=user).exists())
        Rol.objects.create(usuario=user, tipo='banco', activo=True)
        self.assertTrue(SuscripcionBanco.objects.filter(banco=user).exists())