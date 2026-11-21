import os
import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "LottoBooM.settings")
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("SECRET_KEY", "ci-only-not-a-production-secret")

import django
django.setup()

from django.db import connection
from django.test import RequestFactory
from resultados.models import Premio
from resultados.views import solicitar_cobro


class PremioCobroAtomicTests(unittest.TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = SimpleNamespace(is_authenticated=True, id=7, username="test-client")
        self.forma_pago = object()
        self.jugada = SimpleNamespace(
            id=41,
            forma_pago=self.forma_pago,
            sorteo=SimpleNamespace(nombre="Sorteo de prueba"),
        )
        self.premio = SimpleNamespace(
            id=12,
            jugada=self.jugada,
            monto_premio=Decimal("12.50"),
            cobrado=False,
            estado="pendiente",
            fecha_pago=None,
            pagado_por=None,
            save=None,
        )

    def _request(self):
        request = self.factory.post("/resultados/cobrar/12/")
        request.user = self.user
        return request

    def test_all_payout_steps_run_inside_locked_atomic_transaction(self):
        def assert_atomic(*args, **kwargs):
            self.assertTrue(connection.in_atomic_block, "payout step escaped transaction.atomic")

        self.premio.save = patch_save = Mock(side_effect=assert_atomic)
        with (
            patch.object(Premio.objects, "select_for_update", return_value="locked-prize-query") as lock,
            patch("resultados.views.get_object_or_404", return_value=self.premio) as get_prize,
            patch("roles.utils._aplicar_ingreso_a_fondo", side_effect=lambda **kwargs: (assert_atomic() or (Decimal("10.00"), Decimal("2.50")))) as apply_income,
            patch("resultados.views.MovimientoFondo.objects.create", side_effect=assert_atomic) as movement,
            patch("resultados.views.crear_notificacion", side_effect=assert_atomic) as notification,
            patch("resultados.views.messages.success", side_effect=assert_atomic),
            patch("resultados.views.redirect", return_value="redirected"),
        ):
            result = solicitar_cobro(self._request(), 12)

        self.assertEqual(result, "redirected")
        self.assertTrue(self.premio.cobrado)
        self.assertEqual(self.premio.estado, "pagado")
        lock.assert_called_once_with()
        get_prize.assert_called_once_with(
            "locked-prize-query", id=12, jugada__usuario=self.user
        )
        patch_save.assert_called_once()
        apply_income.assert_called_once()
        movement.assert_called_once()
        notification.assert_called_once()
        self.assertFalse(connection.in_atomic_block)

    def test_already_paid_prize_does_not_apply_income_or_create_movement(self):
        self.premio.cobrado = True
        with (
            patch.object(Premio.objects, "select_for_update", return_value="locked-prize-query"),
            patch("resultados.views.get_object_or_404", return_value=self.premio),
            patch("resultados.views.messages.info"),
            patch("resultados.views.redirect", return_value="redirected"),
            patch("roles.utils._aplicar_ingreso_a_fondo") as apply_income,
            patch("resultados.views.MovimientoFondo.objects.create") as movement,
        ):
            result = solicitar_cobro(self._request(), 12)

        self.assertEqual(result, "redirected")
        apply_income.assert_not_called()
        movement.assert_not_called()


if __name__ == "__main__":
    unittest.main()
