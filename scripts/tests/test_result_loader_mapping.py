import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOADER = ROOT / "sorteos" / "management" / "commands" / "load_results.py"


class ResultLoaderMappingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tree = ast.parse(LOADER.read_text(encoding="utf-8"))
        assignment = next(
            node for node in tree.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "MAPEO_NOMBRES"
                    for target in node.targets)
        )
        cls.mapping = ast.literal_eval(assignment.value)

    def test_georgia_night_result_maps_to_existing_catalog_draw(self):
        self.assertEqual(self.mapping["Georgia 11:34 PM"], "Georgia 11:40 PM")

    def test_georgia_night_result_does_not_map_to_nonexistent_midnight_name(self):
        self.assertNotEqual(self.mapping["Georgia 11:34 PM"], "Georgia 12:34 AM")


    def test_every_catalog_draw_has_an_explicit_identity_mapping(self):
        import json
        fixture = json.loads((ROOT / "sorteos" / "fixtures" / "sorteos.json").read_text(encoding="utf-8"))
        names = {
            item["fields"]["nombre"]
            for item in fixture
            if item.get("model") == "sorteos.sorteo"
        }
        self.assertEqual(len(names), 59)
        self.assertEqual({name for name in names if self.mapping.get(name) != name}, set())

    def test_dominican_source_aliases_map_to_their_own_draws(self):
        self.assertEqual(self.mapping["Loteka 1:30 PM"], "Loteka Tarde")
        self.assertEqual(self.mapping["Loteka 7:50 PM"], "Loteka 7:55 PM")
        self.assertEqual(self.mapping["Nacional Gana Más"], "Gana Más 2:30 PM")
        self.assertEqual(self.mapping["Nacional Noche"], "Nacional")
        self.assertEqual(self.mapping["El Quemaito Mayor Noche"], "Quemaito Noche")
        self.assertEqual(self.mapping["El Quinielon Noche"], "Quinielón Noche")


    def test_catalog_refresh_preserves_history_and_deactivates_duplicate_aliases(self):
        script = (ROOT / "cargar_sorteos.py").read_text(encoding="utf-8")
        self.assertIn("from sorteos.management.commands.load_results import MAPEO_NOMBRES", script)
        self.assertIn("anterior.activo = False", script)
        self.assertNotIn(".delete()", script)
        self.assertNotIn("Sorteo.objects.all().delete()", script)

    def test_similar_draw_names_are_not_merged(self):
        self.assertNotEqual(self.mapping["Loteka Tarde"], self.mapping["Loteka 7:55 PM"])
        self.assertNotEqual(self.mapping["Suerte 12:30 PM"], self.mapping["Suerte 6 PM"])
        self.assertNotEqual(self.mapping["Nacional"], self.mapping["Gana Más 2:30 PM"])


if __name__ == "__main__":
    unittest.main()
