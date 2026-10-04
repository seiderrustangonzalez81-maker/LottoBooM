# -*- coding: utf-8 -*-
"""
Tests para resultados: permisos de creación.
"""
from django.test import TestCase
from django.contrib.auth.models import User

from roles.models import Rol


class ResultadoPermissionsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.superadmin = User.objects.create_user('sa_t', password='Test1234!')
        Rol.objects.create(usuario=cls.superadmin, tipo='superadmin', activo=True)

        cls.banco = User.objects.create_user('b_t', password='Test1234!')
        Rol.objects.create(usuario=cls.banco, tipo='banco', activo=True)

        cls.cliente = User.objects.create_user('c_t', password='Test1234!')
        Rol.objects.create(usuario=cls.cliente, tipo='cliente', activo=True)

        cls.auditor = User.objects.create_user('a_t', password='Test1234!')
        Rol.objects.create(usuario=cls.auditor, tipo='auditor', activo=True)

        cls.sin_rol = User.objects.create_user('sr_t', password='Test1234!')

    def test_permisos_gestionar_resultados(self):
        from resultados.views import _puede_gestionar_resultados
        self.assertTrue(_puede_gestionar_resultados(self.superadmin))
        self.assertTrue(_puede_gestionar_resultados(self.banco))
        self.assertTrue(_puede_gestionar_resultados(self.auditor))
        self.assertFalse(_puede_gestionar_resultados(self.cliente))
        self.assertFalse(_puede_gestionar_resultados(self.sin_rol))
