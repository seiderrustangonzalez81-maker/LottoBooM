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


if __name__ == "__main__":
    unittest.main()
