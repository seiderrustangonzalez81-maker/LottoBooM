from django.test import TestCase, RequestFactory
from django.contrib.auth.models import User
from django.utils import timezone
from .models import VisitaDiaria
from .middleware import RegistrarVisitaMiddleware


class VisitaDiariaModelTest(TestCase):
    def test_creacion_visita(self):
        visita = VisitaDiaria.objects.create(
            session_key='abc123',
            fecha=timezone.now().date(),
            ip='127.0.0.1',
            user_agent='Mozilla/5.0'
        )
        self.assertEqual(str(visita), 'abc123 - ' + str(timezone.now().date()))

    def test_visita_con_usuario(self):
        user = User.objects.create_user(username='testuser', password='12345')
        visita = VisitaDiaria.objects.create(
            usuario=user,
            session_key='xyz789',
            fecha=timezone.now().date(),
        )
        self.assertEqual(visita.usuario.username, 'testuser')


class RegistrarVisitaMiddlewareTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = RegistrarVisitaMiddleware(lambda req: None)

    def test_no_registra_rutas_excluidas(self):
        request = self.factory.get('/static/css/style.css')
        request.session = self.client.session
        self.middleware(request)
        self.assertEqual(VisitaDiaria.objects.count(), 0)

    def test_registra_visita_anonima(self):
        request = self.factory.get('/')
        request.session = self.client.session
        request.user = type('User', (), {'is_authenticated': False})()
        self.middleware(request)
        self.assertEqual(VisitaDiaria.objects.count(), 1)