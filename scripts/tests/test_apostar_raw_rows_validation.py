import os
import unittest

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "LottoBooM.settings")
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("SECRET_KEY", "ci-only-not-a-production-secret")
import django
django.setup()

from jugadas.views import _validar_tablas_crudas_payload


def payload(table, kind, forms, rows, sid="54"):
    return [{"sorteo_id":sid,"tablas":{table:{"kind":kind,"forms":forms,"rows":rows}}}]


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

    def test_rejects_wrong_table_kind_and_bad_shape(self):
        errors=_validar_tablas_crudas_payload(payload(
            "tabla-vs","single",["vs"],[{"num":"12","montos":{"vs":"1"}}]
        ))
        self.assertTrue(any("tipo de tabla no coincide" in e for e in errors), errors)
        self.assertTrue(_validar_tablas_crudas_payload("not-a-list"))


if __name__ == "__main__":
    unittest.main()
