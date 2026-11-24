import os
import unittest

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "LottoBooM.settings")
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("SECRET_KEY", "ci-only-not-a-production-secret")
import django
django.setup()

from jugadas.views import _validar_tablas_crudas_payload, _validar_coincidencia_sorteos_tablas, _validar_items_ids_sorteo, _puede_apostar_segun_estado_sorteo, _reconciliar_desglose_pago_edicion, _validar_identidad_boleta_operacion


def payload(table, kind, forms, rows, sid="54"):
    return [{"sorteo_id":sid,"tablas":{table:{"kind":kind,"forms":forms,"rows":rows}}}]


class TicketIdentityOperationTests(unittest.TestCase):
    def _objects(self):
        from types import SimpleNamespace
        return (
            SimpleNamespace(id=11),
            SimpleNamespace(id=11),
            SimpleNamespace(id=22),
            SimpleNamespace(usuario_id=11, destinatario_id=22),
        )

    def test_edit_requires_same_client_and_manager(self):
        boleta, cliente, gestor, original = self._objects()
        self.assertTrue(_validar_identidad_boleta_operacion(original, cliente, gestor, 'editar'))

    def test_reenviar_requires_same_client_and_manager(self):
        boleta, cliente, gestor, original = self._objects()
        self.assertTrue(_validar_identidad_boleta_operacion(original, cliente, gestor, 'reenviar'))

    def test_rejects_different_client(self):
        from types import SimpleNamespace
        _, cliente, gestor, original = self._objects()
        with self.assertRaisesRegex(ValueError, 'no pertenece al cliente'):
            _validar_identidad_boleta_operacion(original, SimpleNamespace(id=99), gestor, 'editar')

    def test_rejects_different_manager(self):
        from types import SimpleNamespace
        _, cliente, gestor, original = self._objects()
        with self.assertRaisesRegex(ValueError, 'cambiar el gestor'):
            _validar_identidad_boleta_operacion(original, cliente, SimpleNamespace(id=99), 'reenviar')

    def test_rejects_unspecified_operation_mode(self):
        _, cliente, gestor, original = self._objects()
        with self.assertRaisesRegex(ValueError, 'Modo de operación inválido'):
            _validar_identidad_boleta_operacion(original, cliente, gestor, '')


class PaymentEditReconciliationTests(unittest.TestCase):
    def test_increase_charges_difference_to_fund(self):
        from decimal import Decimal
        result = _reconciliar_desglose_pago_edicion(
            {'fondo':'3.00','bono':'7.00','postpago':'0.00'}, Decimal('10.00'), Decimal('12.00')
        )
        self.assertEqual(result, {'fondo':Decimal('5.00'),'bono':Decimal('7.00'),'postpago':Decimal('0.00')})
        self.assertEqual(sum(result.values()), Decimal('12.00'))

    def test_decrease_refund_is_reflected_in_current_ticket_breakdown(self):
        from decimal import Decimal
        result = _reconciliar_desglose_pago_edicion(
            {'fondo':'3.00','bono':'7.00','postpago':'0.00'}, Decimal('10.00'), Decimal('6.00')
        )
        self.assertEqual(result, {'fondo':Decimal('1.80'),'bono':Decimal('4.20'),'postpago':Decimal('0.00')})
        self.assertEqual(sum(result.values()), Decimal('6.00'))

    def test_missing_payment_breakdown_defaults_to_fund(self):
        from decimal import Decimal
        result = _reconciliar_desglose_pago_edicion(None, Decimal('8.00'), Decimal('5.50'))
        self.assertEqual(result, {'fondo':Decimal('5.50'),'bono':Decimal('0.00'),'postpago':Decimal('0.00')})

    def test_legacy_inconsistent_breakdown_is_normalized(self):
        from decimal import Decimal
        result = _reconciliar_desglose_pago_edicion(
            {'fondo':'3.00','bono':'6.00','postpago':'0.00'}, Decimal('10.00'), Decimal('11.00')
        )
        self.assertEqual(sum(result.values()), Decimal('11.00'))
        self.assertEqual(result['fondo'], Decimal('4.33'))
        self.assertEqual(result['bono'], Decimal('6.67'))

    def test_negative_or_invalid_legacy_values_are_safely_handled(self):
        from decimal import Decimal
        result = _reconciliar_desglose_pago_edicion(
            {'fondo':'-4','bono':'bad','postpago':'0'}, Decimal('4.00'), Decimal('3.00')
        )
        self.assertEqual(result, {'fondo':Decimal('3.00'),'bono':Decimal('0.00'),'postpago':Decimal('0.00')})


class RawBettingRowsValidationTests(unittest.TestCase):
    def test_empty_trailing_row_is_allowed(self):
        self.assertEqual(_validar_tablas_crudas_payload(payload(
            "tabla-tradicional","multi",["fijo"],[{"num":"","montos":{"fijo":""}}]
        )), [])

    def test_numbers_without_positive_amount_are_blocked(self):
        errors=_validar_tablas_crudas_payload(payload(
            "tabla-tradicional","multi",["fijo","pick2"],[{"num":"12 34","montos":{"fijo":"","pick2":"0"}}]
        ))
        self.assertTrue(any("contiene números pero no tiene importe positivo" in e for e in errors), errors)

    def test_numbers_with_any_positive_applicable_form_are_valid(self):
        self.assertEqual(_validar_tablas_crudas_payload(payload(
            "tabla-tradicional","multi",["fijo","pick2"],[{"num":"12 34","montos":{"fijo":"2.50","pick2":""}}]
        )), [])

    def test_vs_groups_without_amount_are_blocked(self):
        errors=_validar_tablas_crudas_payload(payload(
            "tabla-vs","vs_groups",["vs"],[{"numA":"12 13","numB":"44 45","monto":""}]
        ))
        self.assertTrue(any("contiene números pero no tiene importe positivo" in e for e in errors), errors)

    def test_positions_without_amount_are_blocked(self):
        errors=_validar_tablas_crudas_payload(payload(
            "tabla-posiciones","posiciones",["posicion"],[{"num":"12 34","posicion":"1","monto":""}]
        ))
        self.assertTrue(any("contiene números pero no tiene importe positivo" in e for e in errors), errors)

    def test_amount_without_numbers_is_blocked(self):
        errors=_validar_tablas_crudas_payload(payload(
            "tabla-pick3","single",["pick3"],[{"num":"","montos":{"pick3":"1.00"}}]
        ))
        self.assertTrue(any("tiene importe pero no contiene números" in e for e in errors), errors)

    def test_unknown_form_and_bad_amount_are_blocked(self):
        errors=_validar_tablas_crudas_payload(payload(
            "tabla-pick3","single",["fijo"],[{"num":"123","montos":{"fijo":"1.234"}}]
        ))
        self.assertTrue(any("forma de juego no permitida" in e for e in errors), errors)

    def test_duplicate_forms_are_rejected(self):
        errors = _validar_tablas_crudas_payload(payload(
            "tabla-tradicional","multi",["fijo","fijo"],[{"num":"12","montos":{"fijo":"1"}}]
        ))
        self.assertTrue(any("formas de juego duplicadas" in e for e in errors), errors)

    def test_rejects_wrong_table_kind_and_bad_shape(self):
        errors=_validar_tablas_crudas_payload(payload(
            "tabla-vs","single",["vs"],[{"num":"12","montos":{"vs":"1"}}]
        ))
        self.assertTrue(any("tipo de tabla no coincide" in e for e in errors), errors)
        self.assertTrue(_validar_tablas_crudas_payload("not-a-list"))


class ItemDrawIdValidationTests(unittest.TestCase):
    def test_item_with_selected_draw_passes(self):
        self.assertEqual(_validar_items_ids_sorteo([{"sorteo_id":54}], [54]), [])

    def test_missing_draw_id_is_rejected(self):
        errors = _validar_items_ids_sorteo([{"numero":"12"}], [54])
        self.assertTrue(any("inválido o ausente" in e for e in errors), errors)

    def test_unselected_draw_is_rejected(self):
        errors = _validar_items_ids_sorteo([{"sorteo_id":12}], [54])
        self.assertTrue(any("no seleccionado" in e for e in errors), errors)

    def test_boolean_draw_id_is_rejected(self):
        self.assertTrue(_validar_items_ids_sorteo([{"sorteo_id":True}], [1]))


class DrawTablesPayloadAlignmentTests(unittest.TestCase):
    def test_exact_draw_match_passes(self):
        raw = [{"sorteo_id":"54","tablas":{}},{"sorteo_id":"12","tablas":{}}]
        self.assertEqual(_validar_coincidencia_sorteos_tablas([54,12], raw), [])

    def test_missing_draw_tables_are_rejected(self):
        errors = _validar_coincidencia_sorteos_tablas([54,12], [{"sorteo_id":"54","tablas":{}}])
        self.assertTrue(any("Faltan tablas originales" in e for e in errors), errors)

    def test_extra_draw_tables_are_rejected(self):
        errors = _validar_coincidencia_sorteos_tablas([54], [{"sorteo_id":"54","tablas":{}},{"sorteo_id":"12","tablas":{}}])
        self.assertTrue(any("no seleccionados" in e for e in errors), errors)

    def test_duplicate_selected_draw_is_rejected(self):
        self.assertTrue(_validar_coincidencia_sorteos_tablas([54, "54"], [{"sorteo_id":"54","tablas":{}}]))

    def test_duplicate_raw_draw_is_rejected(self):
        self.assertTrue(_validar_coincidencia_sorteos_tablas([54], [{"sorteo_id":"54","tablas":{}},{"sorteo_id":"54","tablas":{}}]))

    def test_invalid_draw_id_is_rejected(self):
        self.assertTrue(_validar_coincidencia_sorteos_tablas(["54x"], [{"sorteo_id":"54","tablas":{}}]))


if __name__ == "__main__":
    unittest.main()

class DrawStatePermissionTests(unittest.TestCase):
    def _user(self, superuser=False, roles=()):
        from types import SimpleNamespace
        role_qs = SimpleNamespace(filter=lambda **kwargs: SimpleNamespace(exists=lambda: kwargs.get('tipo') in roles and kwargs.get('activo') is True))
        return SimpleNamespace(is_superuser=superuser, roles=role_qs)

    def test_open_draw_allowed_for_user(self):
        self.assertTrue(_puede_apostar_segun_estado_sorteo('abierto', self._user()))

    def test_closed_draw_allowed_only_bank_or_superadmin(self):
        self.assertFalse(_puede_apostar_segun_estado_sorteo('cerrado', self._user(roles=('comercial',))))
        self.assertTrue(_puede_apostar_segun_estado_sorteo('cerrado', self._user(roles=('banco',))))
        self.assertTrue(_puede_apostar_segun_estado_sorteo('cerrado', self._user(roles=('superadmin',))))
        self.assertTrue(_puede_apostar_segun_estado_sorteo('cerrado', self._user(superuser=True)))

    def test_already_drawn_and_unprogrammed_draws_block_everyone(self):
        for state in ('salido', 'no_programado', 'unknown'):
            self.assertFalse(_puede_apostar_segun_estado_sorteo(state, self._user(superuser=True)))
