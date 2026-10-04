from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from roles.models import Rol
from .models import UbicacionUsuario


class UbicacionesTests(TestCase):
    def setUp(self):
        # Crear usuario con rol banco
        self.banco = User.objects.create_user(username="banco", password="banco123")
        Rol.objects.create(usuario=self.banco, tipo="banco")

        # Crear cliente
        self.cliente = User.objects.create_user(username="cliente", password="cli123")
        Rol.objects.create(usuario=self.cliente, tipo="cliente")

        # Crear ubicación de prueba
        self.ubicacion = UbicacionUsuario.objects.create(
            usuario=self.cliente,
            telefono="+5351234567",
            direccion="Calle 23 #456, Vedado",
            ciudad="La Habana",
            provincia="La Habana"
        )

    def test_banco_busca_ubicaciones(self):
        self.client.login(username="banco", password="banco123")
        response = self.client.get(
            reverse("ubicaciones:buscar_telefono", args=["+5351234567"])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Calle 23")

    def test_cliente_no_accede_buscar(self):
        self.client.login(username="cliente", password="cli123")
        response = self.client.get(
            reverse("ubicaciones:buscar_telefono", args=["+5351234567"])
        )
        self.assertEqual(response.status_code, 404)

    def test_cliente_ve_sus_ubicaciones(self):
        self.client.login(username="cliente", password="cli123")
        response = self.client.get(reverse("ubicaciones:mis_ubicaciones"))
        self.assertEqual(response.status_code, 200)

    def test_registrar_ubicacion(self):
        self.client.login(username="cliente", password="cli123")
        response = self.client.post(reverse("ubicaciones:registrar"), {
            "telefono": "+5359876543",
            "direccion": "Calle 12 #789, Centro",
            "ciudad": "La Habana",
            "provincia": "La Habana",
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(UbicacionUsuario.objects.count(), 2)

    def test_eliminar_ubicacion(self):
        self.client.login(username="cliente", password="cli123")
        response = self.client.post(
            reverse("ubicaciones:eliminar", args=[self.ubicacion.id])
        )
        self.assertEqual(response.status_code, 302)
        self.ubicacion.refresh_from_db()
        self.assertFalse(self.ubicacion.activo)