from django.test import TestCase
from django.contrib.auth.models import User
from roles.models import Rol, Subordinacion


class BancoTests(TestCase):
    def setUp(self):
        # Crear banco
        self.banco = User.objects.create_user(username="banco", password="banco123")
        Rol.objects.create(usuario=self.banco, tipo="banco")

        # Crear comercial
        self.comercial = User.objects.create_user(username="comercial", password="com123")
        Rol.objects.create(usuario=self.comercial, tipo="comercial")

        # Asignar comercial al banco
        self.relacion = Subordinacion.objects.create(
            jefe=self.banco,
            subordinado=self.comercial
        )

    def test_banco_accede_panel(self):
        self.client.login(username="banco", password="banco123")
        response = self.client.get("/banco/panel/")
        self.assertEqual(response.status_code, 200)

    def test_banco_ve_comerciales(self):
        self.client.login(username="banco", password="banco123")
        response = self.client.get("/banco/comerciales/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "comercial")

    def test_cliente_no_accede_banco(self):
        cliente = User.objects.create_user(username="cliente", password="cli123")
        Rol.objects.create(usuario=cliente, tipo="cliente")
        self.client.login(username="cliente", password="cli123")
        response = self.client.get("/banco/panel/")
        self.assertNotEqual(response.status_code, 200)