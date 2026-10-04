from django.test import TestCase
from django.contrib.auth.models import User
from roles.models import Rol


class SuperadminTests(TestCase):
    def setUp(self):
        self.superadmin = User.objects.create_superuser(
            username="admin",
            email="admin@test.com",
            password="admin123"
        )
        self.cliente = User.objects.create_user(
            username="cliente",
            password="cliente123"
        )
        Rol.objects.create(usuario=self.cliente, tipo="cliente")

    def test_superadmin_accede_dashboard(self):
        self.client.login(username="admin", password="admin123")
        response = self.client.get("/superadmin/")
        self.assertEqual(response.status_code, 200)

    def test_cliente_no_accede_dashboard(self):
        self.client.login(username="cliente", password="cliente123")
        response = self.client.get("/superadmin/")
        self.assertNotEqual(response.status_code, 200)

    def test_ascender_usuario(self):
        self.client.login(username="admin", password="admin123")
        response = self.client.get(f"/superadmin/usuarios/ascender/{self.cliente.id}/")
        self.assertEqual(response.status_code, 302)  # Redirección

        # Verificar que se ascendió
        rol = Rol.objects.get(usuario=self.cliente)
        self.assertEqual(rol.tipo, "comercial")