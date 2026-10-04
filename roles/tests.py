# -*- coding: utf-8 -*-
"""
Tests para roles: vías de pago, formulario dinámico y flujo de retiro.
"""
from django.test import TestCase
from django.contrib.auth.models import User
from decimal import Decimal

from roles.models import Rol, Fondo, ViaPago, SolicitudRetiro, MovimientoFondo
from roles.forms import ViaPagoForm
from pagos.models import FormaPago


class BaseSetup(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Formas de pago
        cls.fp_tarjeta = FormaPago.objects.create(nombre='Tarjeta', activo=True)
        cls.fp_saldo = FormaPago.objects.create(nombre='Saldo móvil', activo=True)
        cls.fp_efectivo = FormaPago.objects.create(nombre='Efectivo', activo=True)

        # Banco
        cls.banco = User.objects.create_user('banco_test', password='Test1234!')
        Rol.objects.create(usuario=cls.banco, tipo='banco', activo=True)

        # Cliente
        cls.cliente = User.objects.create_user('cliente_test', password='Test1234!')
        Rol.objects.create(usuario=cls.cliente, tipo='cliente', activo=True)

        # Fondo del cliente con el banco
        cls.fondo = Fondo.objects.create(
            usuario=cls.cliente,
            forma_pago=cls.fp_tarjeta,
            asignado_por=cls.banco,
            monto=Decimal('100.00'),
            activo=True,
        )


class ViaPagoFormTests(BaseSetup):
    def test_tarjeta_valida_guarda_16_digitos(self):
        form = ViaPagoForm({
            'forma_pago': self.fp_tarjeta.id,
            'nombre': 'Mi Visa',
            'numero_tarjeta': '1234567890123456',
            'telefono': '+53 5555 0001',
        }, gestor=self.banco)
        self.assertTrue(form.is_valid(), form.errors)
        via = form.save()
        self.assertEqual(via.numero_tarjeta, '1234 5678 9012 3456')
        self.assertEqual(via.telefono, '+53 5555 0001')

    def test_tarjeta_con_menos_de_16_digitos_falla(self):
        form = ViaPagoForm({
            'forma_pago': self.fp_tarjeta.id,
            'nombre': 'Mi Visa',
            'numero_tarjeta': '1234567890',
            'telefono': '+53 5555 0001',
        }, gestor=self.banco)
        self.assertFalse(form.is_valid())

    def test_tarjeta_sin_telefono_falla(self):
        form = ViaPagoForm({
            'forma_pago': self.fp_tarjeta.id,
            'nombre': 'Mi Visa',
            'numero_tarjeta': '1234567890123456',
        }, gestor=self.banco)
        self.assertFalse(form.is_valid())

    def test_saldo_movil_solo_requiere_telefono(self):
        form = ViaPagoForm({
            'forma_pago': self.fp_saldo.id,
            'nombre': 'Mi saldo',
            'telefono': '+53 5555 0002',
        }, gestor=self.banco)
        self.assertTrue(form.is_valid(), form.errors)


class SolicitudRetiroTests(BaseSetup):
    def test_cliente_puede_crear_solicitud(self):
        self.client.force_login(self.cliente)
        r = self.client.post('/roles/solicitar/retiro/', {
            'gestor': self.banco.id,
            'forma_pago': self.fp_tarjeta.id,
            'monto': '10.00',
            'numero_tarjeta': '1234567890123456',
            'telefono_via': '+53 5555 0001',
            'mensaje': 'Test',
        })
        self.assertEqual(r.status_code, 302)
        sol = SolicitudRetiro.objects.filter(cliente=self.cliente).first()
        self.assertIsNotNone(sol)
        self.assertEqual(sol.estado, 'pendiente')
        self.assertEqual(sol.monto, Decimal('10.00'))

    def test_monto_mayor_al_saldo_falla(self):
        self.client.force_login(self.cliente)
        self.client.post('/roles/solicitar/retiro/', {
            'gestor': self.banco.id,
            'forma_pago': self.fp_tarjeta.id,
            'monto': '500.00',
            'numero_tarjeta': '1234567890123456',
            'telefono_via': '+53 5555 0001',
        })
        self.assertFalse(SolicitudRetiro.objects.filter(cliente=self.cliente).exists())

    def test_flujo_completo_retiro(self):
        # 1) Cliente crea
        self.client.force_login(self.cliente)
        self.client.post('/roles/solicitar/retiro/', {
            'gestor': self.banco.id,
            'forma_pago': self.fp_tarjeta.id,
            'monto': '10.00',
            'numero_tarjeta': '1234567890123456',
            'telefono_via': '+53 5555 0001',
        })
        sol = SolicitudRetiro.objects.get(cliente=self.cliente)

        # 2) Banco acepta
        self.client.force_login(self.banco)
        self.client.post(f'/roles/responder-solicitud/retiro/{sol.id}/aceptar/', {})
        sol.refresh_from_db()
        self.assertEqual(sol.estado, 'aceptada')

        # 3) Banco confirma pago
        self.client.post(f'/roles/responder-solicitud/retiro/{sol.id}/confirmar/', {
            'monto_pagado': '10.00',
        })
        sol.refresh_from_db()
        self.assertEqual(sol.estado, 'pagada')

        # 4) Verificar Fondo y MovimientoFondo
        self.fondo.refresh_from_db()
        self.assertEqual(self.fondo.monto, Decimal('90.00'))

        mov = MovimientoFondo.objects.filter(
            emisor=self.cliente, receptor=self.banco, tipo='retiro'
        ).first()
        self.assertIsNotNone(mov)
        self.assertEqual(mov.monto, Decimal('10.00'))
