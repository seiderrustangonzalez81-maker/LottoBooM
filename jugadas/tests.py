import json
from decimal import Decimal

from django.test import TestCase, Client, override_settings
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from django.db import transaction

from jugadas.models import Jugada, FormaJuego
from jugadas.views import (
    limpiar_tokens,
    expandir_abreviaturas,
    generar_pares_entre_grupos,
    obtener_configuracion_sorteo,
)
from sorteos.models import Sorteo
from pagos.models import FormaPago
from roles.models import Rol, Fondo, Bono, Subordinacion, LimiteApuesta, Notificacion, MovimientoFondo


@override_settings(STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage')
class JugadasAuxiliaresTest(TestCase):
    """Tests para funciones auxiliares puras (sin base de datos)."""

    def test_limpiar_tokens_vacio(self):
        self.assertEqual(limpiar_tokens(''), '')
        self.assertEqual(limpiar_tokens(None), '')

    def test_limpiar_tokens_validos(self):
        self.assertEqual(limpiar_tokens('12 34 PA D5 T3'), '12 34 PA D5 T3')

    def test_limpiar_tokens_invalidos(self):
        self.assertEqual(limpiar_tokens('12 abc XX D5'), '12 D5')

    def test_expandir_abreviaturas_pa(self):
        resultado = expandir_abreviaturas('PA')
        esperado = '00 11 22 33 44 55 66 77 88 99'
        self.assertEqual(resultado, esperado)

    def test_expandir_abreviaturas_d(self):
        resultado = expandir_abreviaturas('D3')
        self.assertEqual(resultado, '30 31 32 33 34 35 36 37 38 39')

    def test_expandir_abreviaturas_t(self):
        resultado = expandir_abreviaturas('T4')
        self.assertEqual(resultado, '04 14 24 34 44 54 64 74 84 94')

    def test_expandir_abreviaturas_mixto(self):
        resultado = expandir_abreviaturas('12 PA D2')
        self.assertIn('12', resultado)
        self.assertIn('00', resultado)
        self.assertIn('20', resultado)

    def test_generar_pares_entre_grupos(self):
        g1 = ['10', '20']
        g2 = ['30', '40']
        monto = Decimal('100')
        pares = generar_pares_entre_grupos(g1, g2, monto)
        self.assertEqual(len(pares), 4)
        self.assertIn('10x30', pares)
        self.assertIn('20x40', pares)
        total = sum(pares.values())
        self.assertEqual(total, monto)

    def test_generar_pares_grupo_vacio(self):
        self.assertEqual(generar_pares_entre_grupos([], ['10'], Decimal('100')), {})

    def test_obtener_configuracion_sorteo_con_get_configuracion(self):
        class FakeSorteo:
            nombre = 'Test'
            def get_configuracion(self):
                return {'pick2': True}
        s = FakeSorteo()
        self.assertTrue(obtener_configuracion_sorteo(s).get('pick2'))


@override_settings(STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage')
class JugadasModelTest(TestCase):
    """Tests para el modelo Jugada y FormaJuego."""

    def setUp(self):
        self.user = User.objects.create_user(username='jugador', password='testpass123')
        self.destinatario = User.objects.create_user(username='comercial', password='testpass123')
        self.sorteo = Sorteo.objects.create(
            nombre='La Primera',
            activo=True,
            fecha=timezone.now().date()
        )
        self.forma_juego = FormaJuego.objects.create(
            nombre='Tradicional',
            digitos_esperados=2,
            activo=True
        )
        self.jugada = Jugada.objects.create(
            usuario=self.user,
            destinatario=self.destinatario,
            forma_juego=self.forma_juego,
            sorteo=self.sorteo,
            numero='23',
            monto=Decimal('50.00'),
            estado='pendiente',
            fecha_sorteo=self.sorteo.fecha
        )

    def test_str_jugada(self):
        self.assertIn('jugador', str(self.jugada))
        self.assertIn('comercial', str(self.jugada))

    def test_jugada_estado_choices(self):
        self.assertEqual(self.jugada.estado, 'pendiente')
        self.jugada.estado = 'confirmada'
        self.jugada.save()
        self.assertEqual(self.jugada.estado, 'confirmada')

    def test_puede_modificar_sin_cierre(self):
        # Sin configurar cierre, no debería poder modificarse
        result = self.jugada.puede_modificar()
        self.assertFalse(result)

    def test_marcar_como_ganadora(self):
        self.jugada.marcar_como_ganadora(Decimal('500.00'))
        self.assertEqual(self.jugada.estado, 'ganadora')
        self.assertEqual(self.jugada.monto_premio, Decimal('500.00'))

    def test_marcar_como_perdedora(self):
        self.jugada.marcar_como_perdedora()
        self.assertEqual(self.jugada.estado, 'perdedora')

    def test_verificar_fondos_sin_forma_pago(self):
        with self.assertRaises(ValueError):
            self.jugada.verificar_fondos()

    def test_forma_juego_str(self):
        self.assertEqual(str(self.forma_juego), 'Tradicional')


@override_settings(STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage')
class ApostarViewTest(TestCase):
    """Tests para la vista principal de apostar (GET y POST)."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='cliente1', password='testpass123')
        self.comercial = User.objects.create_user(username='comercial1', password='testpass123')
        self.banco = User.objects.create_user(username='banco1', password='testpass123')
        self.superadmin = User.objects.create_user(username='super1', password='testpass123', is_superuser=True)

        # Roles
        Rol.objects.create(usuario=self.comercial, tipo='comercial', activo=True)
        Rol.objects.create(usuario=self.banco, tipo='banco', activo=True)
        Rol.objects.create(usuario=self.superadmin, tipo='superadmin', activo=True)

        # Sorteo con cierre futuro
        self.sorteo = Sorteo.objects.create(
            nombre='La Primera',
            activo=True,
            fecha=timezone.now().date(),
            hora_cierre='23:59'
        )

        # Formas de juego
        self.forma_tradicional = FormaJuego.objects.create(nombre='Tradicional', digitos_esperados=2, activo=True)
        self.forma_vs = FormaJuego.objects.create(nombre='VS', digitos_esperados=2, activo=True)

        # Forma de pago
        self.forma_pago = FormaPago.objects.create(nombre='Efectivo', activo=True)

        # Fondos
        Fondo.objects.create(usuario=self.user, forma_pago=self.forma_pago, monto=Decimal('500.00'), activo=True, asignado_por=self.comercial)

        # Subordinación
        Subordinacion.objects.create(jefe=self.comercial, subordinado=self.user, activo=True)

    def test_apostar_get_cliente(self):
        self.client.login(username='cliente1', password='testpass123')
        response = self.client.get(reverse('jugadas:apostar'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'La Primera')

    def test_apostar_get_comercial(self):
        self.client.login(username='comercial1', password='testpass123')
        response = self.client.get(reverse('jugadas:apostar'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['es_autorizador'])

    def test_apostar_get_banco(self):
        self.client.login(username='banco1', password='testpass123')
        response = self.client.get(reverse('jugadas:apostar'))
        self.assertEqual(response.status_code, 200)

    def test_apostar_get_superadmin(self):
        self.client.login(username='super1', password='testpass123')
        response = self.client.get(reverse('jugadas:apostar'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['es_superadmin'])

    def test_apostar_post_carrito_vacio(self):
        self.client.login(username='cliente1', password='testpass123')
        response = self.client.post(reverse('jugadas:apostar'), {
            'carrito_data': '[]',
            'sorteos': json.dumps([self.sorteo.id])
        })
        self.assertRedirects(response, reverse('jugadas:apostar'))

    def test_apostar_post_sin_forma_pago(self):
        self.client.login(username='cliente1', password='testpass123')
        carrito = [{'tipo': 'pick2', 'numero': '23', 'monto': 50}]
        response = self.client.post(reverse('jugadas:apostar'), {
            'carrito_data': json.dumps(carrito),
            'sorteos': json.dumps([self.sorteo.id])
        })
        self.assertRedirects(response, reverse('jugadas:apostar'))

    def test_apostar_post_pick2_exitoso(self):
        self.client.login(username='cliente1', password='testpass123')
        carrito = [{
            'tipo': 'pick2',
            'numero': '23',
            'monto': '50.00',
            'forma_pago': 'Efectivo',
            'destinatario': 'Yo mismo'
        }]
        response = self.client.post(reverse('jugadas:apostar'), {
            'carrito_data': json.dumps(carrito),
            'sorteos': json.dumps([self.sorteo.id])
        })
        self.assertEqual(Jugada.objects.count(), 1)
        jugada = Jugada.objects.first()
        self.assertEqual(jugada.numero, '23')
        self.assertEqual(jugada.monto, Decimal('50.00'))

    def test_apostar_post_saldo_insuficiente(self):
        self.client.login(username='cliente1', password='testpass123')
        carrito = [{
            'tipo': 'pick2',
            'numero': '23',
            'monto': '9999.00',
            'forma_pago': 'Efectivo',
            'destinatario': 'Yo mismo'
        }]
        response = self.client.post(reverse('jugadas:apostar'), {
            'carrito_data': json.dumps(carrito),
            'sorteos': json.dumps([self.sorteo.id])
        })
        self.assertRedirects(response, reverse('jugadas:apostar'))

    def test_apostar_post_parlet(self):
        self.client.login(username='cliente1', password='testpass123')
        carrito = [{
            'tipo': 'parlet',
            'numero': '10 20 30',
            'monto': '60.00',
            'forma_pago': 'Efectivo'
        }]
        response = self.client.post(reverse('jugadas:apostar'), {
            'carrito_data': json.dumps(carrito),
            'sorteos': json.dumps([self.sorteo.id])
        })
        # 3 numeros = 3 combinaciones de parlet
        self.assertEqual(Jugada.objects.count(), 3)

    def test_apostar_post_candado(self):
        self.client.login(username='cliente1', password='testpass123')
        carrito = [{
            'tipo': 'candado',
            'numero': '10 20 30',
            'monto': '60.00',
            'forma_pago': 'Efectivo'
        }]
        response = self.client.post(reverse('jugadas:apostar'), {
            'carrito_data': json.dumps(carrito),
            'sorteos': json.dumps([self.sorteo.id])
        })
        self.assertEqual(Jugada.objects.count(), 3)

    def test_apostar_post_vs(self):
        self.client.login(username='cliente1', password='testpass123')
        carrito = [{
            'tipo': 'vs',
            'numero': '10 20 | 30 40',
            'monto': '100.00',
            'forma_pago': 'Efectivo'
        }]
        response = self.client.post(reverse('jugadas:apostar'), {
            'carrito_data': json.dumps(carrito),
            'sorteos': json.dumps([self.sorteo.id])
        })
        # 2x2 = 4 combinaciones
        self.assertEqual(Jugada.objects.count(), 4)

    def test_apostar_post_vs100(self):
        self.client.login(username='cliente1', password='testpass123')
        carrito = [{
            'tipo': 'vs100',
            'numero': '10 20',
            'monto': '1.00',
            'forma_pago': 'Efectivo'
        }]
        response = self.client.post(reverse('jugadas:apostar'), {
            'carrito_data': json.dumps(carrito),
            'sorteos': json.dumps([self.sorteo.id])
        })
        self.assertEqual(Jugada.objects.count(), 2)
        jugada = Jugada.objects.first()
        self.assertEqual(jugada.monto, Decimal('100.00'))

    def test_apostar_post_vs_formato_invalido(self):
        self.client.login(username='cliente1', password='testpass123')
        carrito = [{
            'tipo': 'vs',
            'numero': '10 20 30 40',
            'monto': '100.00',
            'forma_pago': 'Efectivo'
        }]
        response = self.client.post(reverse('jugadas:apostar'), {
            'carrito_data': json.dumps(carrito),
            'sorteos': json.dumps([self.sorteo.id])
        })
        # Debe redirigir con error por formato inválido
        self.assertRedirects(response, reverse('jugadas:apostar'))

    def test_apostar_post_autorizador_a_otro_usuario(self):
        self.client.login(username='super1', password='testpass123')
        carrito = [{
            'tipo': 'pick2',
            'numero': '55',
            'monto': '100.00',
            'forma_pago': 'Efectivo',
            'destinatario': str(self.user.id)
        }]
        response = self.client.post(reverse('jugadas:apostar'), {
            'carrito_data': json.dumps(carrito),
            'sorteos': json.dumps([self.sorteo.id])
        })
        self.assertEqual(Jugada.objects.count(), 1)
        jugada = Jugada.objects.first()
        self.assertEqual(jugada.usuario, self.user)


@override_settings(STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage')
class MisFondosViewTest(TestCase):
    """Tests para la vista de mis fondos."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='cliente_fondos', password='testpass123')
        self.comercial = User.objects.create_user(username='comercial_fondos', password='testpass123')
        Rol.objects.create(usuario=self.comercial, tipo='comercial', activo=True)
        self.forma_pago = FormaPago.objects.create(nombre='Efectivo', activo=True)
        Fondo.objects.create(usuario=self.user, forma_pago=self.forma_pago, monto=Decimal('200.00'), activo=True, asignado_por=self.comercial)

    def test_mis_fondos_cliente(self):
        self.client.login(username='cliente_fondos', password='testpass123')
        response = self.client.get(reverse('jugadas:mis_fondos'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '200')

    def test_mis_fondos_filtrar_forma_pago(self):
        self.client.login(username='cliente_fondos', password='testpass123')
        response = self.client.get(reverse('jugadas:mis_fondos'), {'forma_pago': self.forma_pago.id})
        self.assertEqual(response.status_code, 200)


@override_settings(STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage')
class APIViewsTest(TestCase):
    """Tests para las APIs auxiliares."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='apiuser', password='testpass123')
        self.forma_pago = FormaPago.objects.create(nombre='Transferencia', activo=True)
        Fondo.objects.create(usuario=self.user, forma_pago=self.forma_pago, monto=Decimal('300.00'), activo=True)

    def test_api_verificar_password_correcta(self):
        self.client.login(username='apiuser', password='testpass123')
        response = self.client.post(
            reverse('jugadas:api_verificar_password'),
            data=json.dumps({'password': 'testpass123'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])

    def test_api_verificar_password_incorrecta(self):
        self.client.login(username='apiuser', password='testpass123')
        response = self.client.post(
            reverse('jugadas:api_verificar_password'),
            data=json.dumps({'password': 'wrongpass'}),
            content_type='application/json'
        )
        data = json.loads(response.content)
        self.assertFalse(data['success'])

    def test_api_verificar_password_get_no_permitido(self):
        self.client.login(username='apiuser', password='testpass123')
        response = self.client.get(reverse('jugadas:api_verificar_password'))
        self.assertEqual(response.status_code, 405)

    def test_api_verificar_saldo(self):
        self.client.login(username='apiuser', password='testpass123')
        response = self.client.get(reverse('jugadas:api_verificar_saldo'), {'usuario_id': self.user.id})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['total_fondos'], 300.0)
        self.assertEqual(data['saldo_total'], 300.0)

    def test_api_verificar_saldo_sin_usuario(self):
        self.client.login(username='apiuser', password='testpass123')
        response = self.client.get(reverse('jugadas:api_verificar_saldo'))
        self.assertEqual(response.status_code, 400)

    def test_api_forma_pago_cliente(self):
        self.client.login(username='apiuser', password='testpass123')
        response = self.client.get(reverse('jugadas:api_forma_pago_cliente'), {'cliente_id': self.user.id})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn(self.forma_pago.id, data['formas_pago'])

    def test_api_forma_pago_cliente_sin_id(self):
        self.client.login(username='apiuser', password='testpass123')
        response = self.client.get(reverse('jugadas:api_forma_pago_cliente'))
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn(self.forma_pago.id, data['formas_pago'])


@override_settings(STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage')
class JugadaProcesarApuestaTest(TestCase):
    """Tests para los métodos del modelo Jugada relacionados con procesamiento."""

    def setUp(self):
        self.user = User.objects.create_user(username='procesador', password='testpass123')
        self.autorizador = User.objects.create_user(username='autorizador', password='testpass123')
        Rol.objects.create(usuario=self.autorizador, tipo='banco', activo=True)
        self.sorteo = Sorteo.objects.create(nombre='Test', activo=True, fecha=timezone.now().date())
        self.forma_juego = FormaJuego.objects.create(nombre='Tradicional', digitos_esperados=2, activo=True)
        self.forma_pago = FormaPago.objects.create(nombre='Efectivo', activo=True)
        self.jugada = Jugada.objects.create(
            usuario=self.user,
            sorteo=self.sorteo,
            forma_juego=self.forma_juego,
            forma_pago=self.forma_pago,
            numero='12',
            monto=Decimal('100.00'),
            estado='pendiente'
        )

    def test_procesar_apuesta_sin_forma_pago(self):
        self.jugada.forma_pago = None
        self.jugada.save()
        success, msg = self.jugada.procesar_apuesta()
        self.assertFalse(success)
        self.assertIn('forma de pago', msg.lower())

    def test_procesar_apuesta_sin_fondos_sin_autorizar(self):
        success, msg = self.jugada.procesar_apuesta()
        self.assertFalse(success)
        self.assertIn('insuficiente', msg.lower())

    def test_procesar_apuesta_con_fondos(self):
        Fondo.objects.create(usuario=self.user, forma_pago=self.forma_pago, monto=Decimal('500.00'), activo=True)
        success, msg = self.jugada.procesar_apuesta()
        self.assertTrue(success)
        self.jugada.refresh_from_db()
        self.assertEqual(self.jugada.estado, 'confirmada')
        self.assertEqual(self.jugada.saldo_despues, Decimal('400.00'))

    def test_procesar_apuesta_autorizada_crea_deuda(self):
        Fondo.objects.create(usuario=self.user, forma_pago=self.forma_pago, monto=Decimal('50.00'), activo=True)
        success, msg = self.jugada.procesar_apuesta(autorizado_por=self.autorizador)
        self.assertTrue(success)
        self.jugada.refresh_from_db()
        self.assertEqual(self.jugada.autorizada_por, self.autorizador)
        self.assertIn('deuda_id', self.jugada.metadata)

    def test_notificar_modificacion(self):
        destinatario = User.objects.create_user(username='dest', password='testpass123')
        self.jugada.destinatario = destinatario
        self.jugada.save()
        self.jugada.notificar_modificacion(self.autorizador, {'numero': '12 -> 34'})
        self.assertTrue(Notificacion.objects.filter(usuario=destinatario).exists())

    def test_es_autorizador_true(self):
        self.assertTrue(self.jugada._es_autorizador(self.autorizador))

    def test_es_autorizador_false(self):
        cliente = User.objects.create_user(username='cliente_x', password='testpass123')
        self.assertFalse(self.jugada._es_autorizador(cliente))