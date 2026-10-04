from django.test import TestCase
from django.contrib.auth.models import User
from roles.models import Rol, RelacionUsuario, RelacionUsuario


class ComercialTests(TestCase):
    def setUp(self):
        # Crear banco
        self.banco = User.objects.create_user(username="banco", password="banco123")
        Rol.objects.create(usuario=self.banco, tipo="banco")

        # Crear comercial
        self.comercial = User.objects.create_user(username="comercial", password="com123")
        Rol.objects.create(usuario=self.comercial, tipo="comercial")

        # Asignar comercial al banco
        RelacionUsuario.objects.create(banco=self.banco, comercial=self.comercial)

        # Crear cliente
        self.cliente = User.objects.create_user(username="cliente", password="cli123")
        Rol.objects.create(usuario=self.cliente, tipo="cliente")

        # Asignar cliente al comercial
        RelacionUsuario.objects.create(comercial=self.comercial, cliente=self.cliente)

    def test_comercial_accede_panel(self):
        self.client.login(username="comercial", password="com123")
        response = self.client.get("/comercial/panel/")
        self.assertEqual(response.status_code, 200)

    def test_comercial_ve_clientes(self):
        self.client.login(username="comercial", password="com123")
        response = self.client.get("/comercial/clientes/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "cliente")

    def test_comercial_ve_detalle_cliente(self):
        self.client.login(username="comercial", password="com123")
        response = self.client.get(f"/comercial/clientes/{self.cliente.id}/")
        self.assertEqual(response.status_code, 200)

    def test_banco_no_accede_panel_comercial(self):
        self.client.login(username="banco", password="banco123")
        response = self.client.get("/comercial/panel/")
        self.assertNotEqual(response.status_code, 200)

    def test_desvincular_cliente(self):
        self.client.login(username="comercial", password="com123")
        response = self.client.post(f"/comercial/clientes/{self.cliente.id}/desvincular/")
        self.assertEqual(response.status_code, 302)

        # Verificar que se desvinculó
        relacion = RelacionUsuario.objects.get(comercial=self.comercial, cliente=self.cliente)
        self.assertFalse(relacion.activo)