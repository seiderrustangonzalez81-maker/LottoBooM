import json
from decimal import Decimal

from django.test import TestCase, Client, override_settings
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from django.db import transaction
from unittest.mock import patch

from jugadas.models import Jugada, FormaJuego, Boleta
from jugadas.views import obtener_configuracion_sorteo
from sorteos.models import Sorteo
from pagos.models import FormaPago
from roles.models import Rol, Fondo, Bono, Subordinacion, LimiteApuesta, Notificacion, MovimientoFondo


@override_settings(STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage')
class JugadasAuxiliaresTest(TestCase):
    """Tests para funciones auxiliares puras (sin base de datos)."""

    def test_obtener_configuracion_sorteo_uses_form_catalog(self):
        class FakeSorteo:
            nombre = 'Test'
            formas_juego = ['pick2']
        config = obtener_configuracion_sorteo(FakeSorteo())
        self.assertTrue(config['config'].get('pick2'))
        self.assertFalse(config['config'].get('pick3'))


@override_settings(STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage')
class JugadasModelTest(TestCase):
    """Tests para el modelo Jugada y FormaJuego."""

    def setUp(self):
        self.user = User.objects.create_user(username='jugador', password='testpass123')
        self.destinatario = User.objects.create_user(username='comercial', password='testpass123')
        self.sorteo = Sorteo.objects.create(
            nombre='La Primera',
            activo=True
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
            fecha_sorteo=timezone.localdate()
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
        _dias = ['lunes', 'martes', 'miercoles', 'jueves', 'viernes', 'sabado', 'domingo']
        _horarios = {
            'verano': {dia: '23:59' for dia in _dias},
            'invierno': {dia: '23:59' for dia in _dias},
        }
        self.sorteo = Sorteo.objects.create(
            nombre='La Primera',
            activo=True,
            hora_salida='23:59',
            minutos_cierre=0,
            horarios=_horarios,
            formas_juego=['pick2', 'pick3', 'pick4', 'parlet', 'candado', 'vs', 'vs100']
        )
        self._patch_actualizacion = patch('jugadas.views._intentar_actualizar_loteria')
        self._patch_actualizacion.start()
        self.addCleanup(self._patch_actualizacion.stop)

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
        self.assertContains(response, 'listaSorteos')

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

    def test_apostar_post_method_not_allowed(self):
        self.client.login(username='cliente1', password='testpass123')
        response = self.client.post(reverse('jugadas:apostar'), {})
        self.assertEqual(response.status_code, 405)

    def test_guardar_apuesta_rejects_empty_payload(self):
        self.client.login(username='cliente1', password='testpass123')
        response = self.client.post(reverse('jugadas:guardar_apuesta'), {
            'fecha': timezone.localdate().isoformat(),
            'cliente_id': str(self.user.id),
            'forma_pago': str(self.forma_pago.id),
            'carrito_data': '[]',
            'superparlet_data': '[]',
            'sorteos': '[]',
            'superparlet_sorteos': '[]',
            'tabla_rows': '[]',
        })
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Jugada.objects.exists())

    def test_guardar_apuesta_requires_raw_rows(self):
        self.client.login(username='cliente1', password='testpass123')
        response = self.client.post(reverse('jugadas:guardar_apuesta'), {
            'fecha': timezone.localdate().isoformat(),
            'cliente_id': str(self.user.id),
            'forma_pago': str(self.forma_pago.id),
            'carrito_data': json.dumps([{'tipo':'pick2','numero':'23','monto':'50.00','sorteo_id':self.sorteo.id}]),
            'superparlet_data': '[]',
            'sorteos': json.dumps([self.sorteo.id]),
            'superparlet_sorteos': '[]',
            'tabla_rows': '[]',
        })
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Jugada.objects.exists())

    def test_guardar_apuesta_rejects_invalid_raw_table(self):
        self.client.login(username='cliente1', password='testpass123')
        response = self.client.post(reverse('jugadas:guardar_apuesta'), {
            'fecha': timezone.localdate().isoformat(),
            'cliente_id': str(self.user.id),
            'forma_pago': str(self.forma_pago.id),
            'carrito_data': json.dumps([{'tipo':'pick2','numero':'23','monto':'50.00','sorteo_id':self.sorteo.id}]),
            'superparlet_data': '[]',
            'sorteos': json.dumps([self.sorteo.id]),
            'superparlet_sorteos': '[]',
            'tabla_rows': json.dumps([{'sorteo_id':self.sorteo.id,'tablas':[]}]),
        })
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Jugada.objects.exists())

    @patch('jugadas.views._puede_apostar_segun_estado_sorteo', return_value=True)
    @patch('jugadas.views.get_pool_gestor', return_value=Decimal('1000.00'))
    def test_guardar_apuesta_valid_pick2_creates_ticket_and_charges_fund(self, _pool, _draw_open):
        self.client.login(username='cliente1', password='testpass123')
        items = [{'tipo':'pick2','numero':'23','monto':'50.00','sorteo_id':self.sorteo.id}]
        raw_rows = [{
            'sorteo_id':self.sorteo.id,
            'tablas':{
                'tabla-tradicional':{
                    'kind':'multi','forms':['pick2'],
                    'rows':[{'num':'23','montos':{'pick2':'50.00'}}]
                }
            }
        }]
        response = self.client.post(reverse('jugadas:guardar_apuesta'), {
            'fecha': timezone.localdate().isoformat(),
            'cliente_id': str(self.user.id),
            'destinatario_id': str(self.comercial.id),
            'forma_pago': str(self.forma_pago.id),
            'carrito_data': json.dumps(items),
            'superparlet_data': '[]',
            'sorteos': json.dumps([self.sorteo.id]),
            'superparlet_sorteos': '[]',
            'tabla_rows': json.dumps(raw_rows),
        })
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json().get('success'), response.json())
        self.assertEqual(Jugada.objects.count(), 1)
        ticket = Boleta.objects.get(usuario=self.user)
        self.assertEqual(ticket.monto_total, Decimal('50.00'))
        self.assertEqual(ticket.metadata['pago']['total'], '50.00')
        fondo = Fondo.objects.get(usuario=self.user, forma_pago=self.forma_pago, asignado_por=self.comercial)
        self.assertEqual(fondo.monto, Decimal('450.00'))

        # Editar aumento: misma boleta, diferencia descontada del Fondo.
        ticket_id = ticket.id
        ref_original = ticket.referencia
        items_aumento = [{'tipo':'pick2','numero':'23','monto':'75.00','sorteo_id':self.sorteo.id}]
        raw_aumento = [{
            'sorteo_id':self.sorteo.id,
            'tablas':{'tabla-tradicional':{'kind':'multi','forms':['pick2'],
                'rows':[{'num':'23','montos':{'pick2':'75.00'}}]}}
        }]
        response_edit = self.client.post(reverse('jugadas:guardar_apuesta'), {
            'fecha': timezone.localdate().isoformat(),
            'cliente_id': str(self.user.id),
            'destinatario_id': str(self.comercial.id),
            'forma_pago': str(self.forma_pago.id),
            'carrito_data': json.dumps(items_aumento),
            'superparlet_data': '[]',
            'sorteos': json.dumps([self.sorteo.id]),
            'superparlet_sorteos': '[]',
            'tabla_rows': json.dumps(raw_aumento),
            'modo_edicion': 'editar_boleta',
            'boleta_origen_id': str(ticket_id),
            'modo_operacion': 'editar',
        })
        self.assertEqual(response_edit.status_code, 200, response_edit.content)
        self.assertTrue(response_edit.json().get('success'), response_edit.json())
        ticket.refresh_from_db()
        fondo.refresh_from_db()
        self.assertEqual(ticket.id, ticket_id)
        self.assertEqual(ticket.referencia, ref_original)
        self.assertEqual(ticket.monto_total, Decimal('75.00'))
        self.assertEqual(fondo.monto, Decimal('425.00'))
        self.assertEqual(ticket.metadata['pago']['total'], '75.00')

        # Editar reducción: devuelve diferencia al Fondo y conserva historial.
        items_reduccion = [{'tipo':'pick2','numero':'23','monto':'40.00','sorteo_id':self.sorteo.id}]
        raw_reduccion = [{
            'sorteo_id':self.sorteo.id,
            'tablas':{'tabla-tradicional':{'kind':'multi','forms':['pick2'],
                'rows':[{'num':'23','montos':{'pick2':'40.00'}}]}}
        }]
        response_edit2 = self.client.post(reverse('jugadas:guardar_apuesta'), {
            'fecha': timezone.localdate().isoformat(),
            'cliente_id': str(self.user.id),
            'destinatario_id': str(self.comercial.id),
            'forma_pago': str(self.forma_pago.id),
            'carrito_data': json.dumps(items_reduccion),
            'superparlet_data': '[]',
            'sorteos': json.dumps([self.sorteo.id]),
            'superparlet_sorteos': '[]',
            'tabla_rows': json.dumps(raw_reduccion),
            'modo_edicion': 'editar_boleta',
            'boleta_origen_id': str(ticket_id),
            'modo_operacion': 'editar',
        })
        self.assertEqual(response_edit2.status_code, 200, response_edit2.content)
        self.assertTrue(response_edit2.json().get('success'), response_edit2.json())
        ticket.refresh_from_db()
        fondo.refresh_from_db()
        self.assertEqual(ticket.monto_total, Decimal('40.00'))
        self.assertEqual(fondo.monto, Decimal('460.00'))
        self.assertEqual(ticket.metadata['pago']['total'], '40.00')
        self.assertEqual(len(ticket.metadata['historial_ediciones']), 2)
        self.assertEqual(ticket.metadata['historial_ediciones'][0]['total_nuevo'], '75.00')
        self.assertEqual(ticket.metadata['historial_ediciones'][1]['total_nuevo'], '40.00')

        # Reenviar: crea boleta/cobro nuevos y no altera la original.
        items_reenvio = [{'tipo':'pick2','numero':'23','monto':'40.00','sorteo_id':self.sorteo.id}]
        raw_reenvio = [{
            'sorteo_id':self.sorteo.id,
            'tablas':{'tabla-tradicional':{'kind':'multi','forms':['pick2'],
                'rows':[{'num':'23','montos':{'pick2':'40.00'}}]}}
        }]
        response_reenvio = self.client.post(reverse('jugadas:guardar_apuesta'), {
            'fecha': timezone.localdate().isoformat(),
            'cliente_id': str(self.user.id),
            'destinatario_id': str(self.comercial.id),
            'forma_pago': str(self.forma_pago.id),
            'carrito_data': json.dumps(items_reenvio),
            'superparlet_data': '[]',
            'sorteos': json.dumps([self.sorteo.id]),
            'superparlet_sorteos': '[]',
            'tabla_rows': json.dumps(raw_reenvio),
            'modo_edicion': 'editar_boleta',
            'boleta_origen_id': str(ticket_id),
            'modo_operacion': 'reenviar',
        })
        self.assertEqual(response_reenvio.status_code, 200, response_reenvio.content)
        self.assertTrue(response_reenvio.json().get('success'), response_reenvio.json())
        ticket.refresh_from_db()
        fondo.refresh_from_db()
        self.assertEqual(Boleta.objects.count(), 2)
        self.assertEqual(ticket.monto_total, Decimal('40.00'))
        ticket_nueva = Boleta.objects.exclude(id=ticket_id).get()
        self.assertEqual(ticket_nueva.monto_total, Decimal('40.00'))
        self.assertEqual(ticket_nueva.metadata['boleta_origen_id'], ticket_id)
        self.assertEqual(fondo.monto, Decimal('420.00'))

    @patch('jugadas.views._puede_apostar_segun_estado_sorteo', return_value=True)
    @patch('jugadas.views.get_pool_gestor', return_value=Decimal('1000.00'))
    def test_guardar_apuesta_invalid_line_aborts_whole_payload(self, _pool, _draw_open):
        self.client.login(username='cliente1', password='testpass123')
        items = [
            {'tipo':'pick2','numero':'23','monto':'50.00','sorteo_id':self.sorteo.id},
            {'tipo':'pick2','numero':'x','monto':'10.00','sorteo_id':self.sorteo.id},
        ]
        raw_rows = [{
            'sorteo_id':self.sorteo.id,
            'tablas':{
                'tabla-tradicional':{
                    'kind':'multi','forms':['pick2'],
                    'rows':[
                        {'num':'23','montos':{'pick2':'50.00'}},
                        {'num':'x','montos':{'pick2':'10.00'}}
                    ]
                }
            }
        }]
        response = self.client.post(reverse('jugadas:guardar_apuesta'), {
            'fecha': timezone.localdate().isoformat(),
            'cliente_id': str(self.user.id),
            'destinatario_id': str(self.comercial.id),
            'forma_pago': str(self.forma_pago.id),
            'carrito_data': json.dumps(items),
            'superparlet_data': '[]',
            'sorteos': json.dumps([self.sorteo.id]),
            'superparlet_sorteos': '[]',
            'tabla_rows': json.dumps(raw_rows),
        })
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Jugada.objects.count(), 0)
        self.assertEqual(Boleta.objects.count(), 0)
        fondo = Fondo.objects.get(usuario=self.user, forma_pago=self.forma_pago, asignado_por=self.comercial)
        self.assertEqual(fondo.monto, Decimal('500.00'))


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
        self.assertIn(self.forma_pago.id, [fp['id'] for fp in data['formas_pago']])

    def test_api_forma_pago_cliente_sin_id(self):
        self.client.login(username='apiuser', password='testpass123')
        response = self.client.get(reverse('jugadas:api_forma_pago_cliente'))
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['formas_pago'], [])


@override_settings(STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage')
class JugadaProcesarApuestaTest(TestCase):
    """Tests para los métodos del modelo Jugada relacionados con procesamiento."""

    def setUp(self):
        self.user = User.objects.create_user(username='procesador', password='testpass123')
        self.autorizador = User.objects.create_user(username='autorizador', password='testpass123')
        Rol.objects.create(usuario=self.autorizador, tipo='banco', activo=True)
        self.sorteo = Sorteo.objects.create(nombre='Test', activo=True)
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
        movimiento = MovimientoFondo.objects.filter(tipo='apuesta').latest('id')
        self.assertEqual(movimiento.receptor, self.user)

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