import os
import unittest
import re

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "LottoBooM.settings")
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("SECRET_KEY", "ci-only-not-a-production-secret")
import django
django.setup()

from jugadas.views import _consolidar_tripletas, _validar_items_payload, _validar_items_formas_sorteos


class BettingFormCatalogTests(unittest.TestCase):
    def test_fixture_forms_have_table_mapping(self):
        import json
        from pathlib import Path
        root = Path(__file__).resolve().parents[2]
        fixture = json.loads((root / "sorteos/fixtures/sorteos.json").read_text(encoding="utf-8"))
        html = (root / "jugadas/templates/jugadas/apostar.html").read_text(encoding="utf-8")
        match = re.search(r"const FJ_TO_TABLE\\s*=\\s*\\{([\\s\\S]*?)\\};", html)
        self.assertIsNotNone(match, "FJ_TO_TABLE declaration missing")
        mapping = dict(re.findall(r"'([^']+)'\\s*:\\s*'([^']+)'", match.group(1)))
        fixture_forms = {form for draw in fixture for form in draw["fields"].get("formas_juego", [])}
        self.assertFalse(fixture_forms - mapping.keys(), f"Unmapped active fixture forms: {fixture_forms - mapping.keys()}")
        defs = html[html.index("const TABLE_DEFS"):html.index("const FORM_LABELS")]
        table_keys = set(re.findall(r"'(tabla-[^']+)'\\s*:", defs))
        self.assertFalse(set(mapping.values()) - table_keys, f"Unknown table targets: {set(mapping.values()) - table_keys}")

    def test_known_unmapped_choice_is_explicitly_tracked(self):
        from pathlib import Path
        root = Path(__file__).resolve().parents[2]
        choices = (root / "sorteos/forms.py").read_text(encoding="utf-8")
        html = (root / "jugadas/templates/jugadas/apostar.html").read_text(encoding="utf-8")
        match = re.search(r"const FJ_TO_TABLE\\s*=\\s*\\{([\\s\\S]*?)\\};", html)
        mapping = dict(re.findall(r"'([^']+)'\\s*:\\s*'([^']+)'", match.group(1)))
        form_choices = set(re.findall(r"\\('([^']+)'\\s*,", choices))
        unmapped = form_choices - mapping.keys() - {"superparlet"}
        self.assertEqual(unmapped, {"par frontal"}, "Review form-to-table mapping changes; do not auto-alias without confirming semantics")


class DrawFormValidationTests(unittest.TestCase):
    def test_accepts_corridos_alias_when_draw_enables_corrido1_or2(self):
        self.assertEqual(_validar_items_formas_sorteos([{"tipo":"corridos","numero":"12","monto":"1","sorteo_id":1}], {"1":["corrido1"]}), [])
        self.assertEqual(_validar_items_formas_sorteos([{"tipo":"corridos","numero":"12","monto":"1","sorteo_id":2}], {"2":["corrido2"]}), [])

    def test_accepts_centenas_alias(self):
        self.assertEqual(_validar_items_formas_sorteos([{"tipo":"centenas corridas","numero":"123","monto":"1","sorteo_id":1}], {"1":["centena corrida1"]}), [])

    def test_rejects_disabled_form_and_wrong_draw(self):
        self.assertTrue(_validar_items_formas_sorteos([{"tipo":"pick2","numero":"12","monto":"1","sorteo_id":1}], {"1":["fijo"]}))
        self.assertTrue(_validar_items_formas_sorteos([{"tipo":"fijo","numero":"12","monto":"1","sorteo_id":2}], {"1":["fijo"]}))

    def test_item_without_draw_id_must_be_allowed_on_all_selected_draws(self):
        self.assertTrue(_validar_items_formas_sorteos([{"tipo":"corridos","numero":"12","monto":"1"}], {"1":["corrido1"],"2":["pick2"]}))


class PayloadValidationTests(unittest.TestCase):
    def test_valid_payload_item(self):
        self.assertEqual(_validar_items_payload([{"tipo":"fijo","numero":"12","monto":"1.25","sorteo_id":3}]), [])

    def test_rejects_zero_negative_and_nonfinite_amounts(self):
        for amount in ["0", "-2", "NaN", "Infinity", ""]:
            self.assertTrue(_validar_items_payload([{"tipo":"fijo","numero":"12","monto":amount}]), amount)

    def test_rejects_more_than_two_decimals_and_overflow(self):
        self.assertTrue(_validar_items_payload([{"tipo":"fijo","numero":"12","monto":"1.001"}]))
        self.assertTrue(_validar_items_payload([{"tipo":"fijo","numero":"12","monto":"100000000.00"}]))

    def test_rejects_invalid_shape_empty_type_or_number(self):
        self.assertTrue(_validar_items_payload("not a list"))
        self.assertTrue(_validar_items_payload([None]))
        self.assertTrue(_validar_items_payload([{"tipo":"","numero":"12","monto":"1"}]))
        self.assertTrue(_validar_items_payload([{"tipo":"fijo","numero":"","monto":"1"}]))

    def test_validates_number_format_by_form(self):
        valid = [
            {"tipo":"pick2","numero":"12","monto":"1"},
            {"tipo":"pick3","numero":"123","monto":"1"},
            {"tipo":"pick4","numero":"1234","monto":"1"},
            {"tipo":"pick5","numero":"12345","monto":"1"},
            {"tipo":"vs","numero":"12x34","monto":"1"},
            {"tipo":"superparlet","numero":"12x34 56x78","monto":"1"},
            {"tipo":"tripleta","numero":"12 34 56","monto":"1"},
            {"tipo":"centenas corridas","numero":"123","monto":"1"},
        ]
        for item in valid:
            self.assertEqual(_validar_items_payload([item]), [], item)
        invalid = [
            {"tipo":"pick2","numero":"123","monto":"1"},
            {"tipo":"pick3","numero":"12","monto":"1"},
            {"tipo":"pick4","numero":"123","monto":"1"},
            {"tipo":"pick5","numero":"1234","monto":"1"},
            {"tipo":"vs","numero":"1234","monto":"1"},
            {"tipo":"tripleta","numero":"12 34","monto":"1"},
            {"tipo":"superparlet","numero":"12x34,56x78","monto":"1"},
            {"tipo":"mystery","numero":"12","monto":"1"},
        ]
        for item in invalid:
            self.assertTrue(_validar_items_payload([item]), item)

    def test_rejects_invalid_sorteo_id_and_position(self):
        self.assertTrue(_validar_items_payload([{"tipo":"fijo","numero":"12","monto":"1","sorteo_id":"x"}]))
        self.assertTrue(_validar_items_payload([{"tipo":"posicion","numero":"12","monto":"1","posicion":"4"}]))


class TripletaConsolidationTests(unittest.TestCase):
    def test_preserves_grouped_rows_with_same_amount(self):
        items = [
            {"tipo": "tripleta", "numero": "12 34 56", "monto": "5", "sorteo_id": 1},
            {"tipo": "tripleta", "numero": "01 02 03", "monto": "5", "sorteo_id": 1},
        ]
        result = _consolidar_tripletas(items)
        self.assertEqual(len(result), 2)
        self.assertEqual([item["numero"] for item in result], ["12 34 56", "01 02 03"])
        self.assertEqual(sum(float(item["monto"]) for item in result), 10)

    def test_legacy_single_number_items_group_in_threes(self):
        items = [
            {"tipo": "tripleta", "numero": n, "monto": "4", "sorteo_id": 2}
            for n in ["11", "22", "33", "44", "55", "66"]
        ]
        result = _consolidar_tripletas(items)
        self.assertEqual(len(result), 2)
        self.assertEqual([item["numero"] for item in result], ["11 22 33", "44 55 66"])
        self.assertEqual(sum(float(item["monto"]) for item in result), 8)

    def test_rejects_incomplete_legacy_tripleta(self):
        with self.assertRaises(ValueError):
            _consolidar_tripletas([
                {"tipo": "tripleta", "numero": "12", "monto": "3", "sorteo_id": 1},
                {"tipo": "tripleta", "numero": "34", "monto": "3", "sorteo_id": 1},
            ])

    def test_non_tripleta_items_are_unchanged(self):
        item = {"tipo": "fijo", "numero": "12", "monto": "2", "sorteo_id": 1}
        self.assertEqual(_consolidar_tripletas([item]), [item])


if __name__ == "__main__":
    unittest.main()
