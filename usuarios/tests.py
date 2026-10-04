# -*- coding: utf-8 -*-
"""
Tests para usuarios: perfil por rol.
"""
from django.test import TestCase
from django.contrib.auth.models import User

from roles.models import Rol


class PerfilTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Banco
        cls.banco = User.objects.create_user('banco_p', password='Test1234!')
        Rol.objects.create(usuario=cls.banco, tipo='banco', activo=True)

        # Auditor
        cls.auditor = User.objects.create_user('auditor_p', password='Test1234!')
        Rol.objects.create(
            usuario=cls.auditor, tipo='auditor',
            activo=True, banco_asignado=cls.banco,
        )

        # Cliente normal
        cls.cliente = User.objects.create_user('cliente_p', password='Test1234!')
        Rol.objects.create(usuario=cls.cliente, tipo='cliente', activo=True)

    def test_auditor_ve_bloque_auditoria(self):
        self.client.force_login(self.auditor)
        r = self.client.get('/usuarios/perfil/')
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertIn('Banco Asignado', html)
        self.assertIn('Totales de la Red', html)

    def test_cliente_no_ve_bloque_auditoria(self):
        self.client.force_login(self.cliente)
        r = self.client.get('/usuarios/perfil/')
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertNotIn('Totales de la Red', html)

    def test_perfil_renderiza_variables_nuevas(self):
        self.client.force_login(self.cliente)
        r = self.client.get('/usuarios/perfil/')
        html = r.content.decode()
        # Las variables que añadimos en Pendiente B
        self.assertIn('stroke-dashoffset', html)  # rings
        self.assertIn('pf-hm-day', html)           # heatmap
