import os
import unittest

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "LottoBooM.settings")
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("SECRET_KEY", "ci-only-not-a-production-secret")
import django
django.setup()

from jugadas.views import _consolidar_tripletas


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
