import importlib.util, unittest
from pathlib import Path
SCRIPT=Path(__file__).resolve().parents[2]/"scripts"/"auditar_sorteos.py"
spec=importlib.util.spec_from_file_location("audit_draws",SCRIPT)
audit=importlib.util.module_from_spec(spec); spec.loader.exec_module(audit)
class NormalizeTests(unittest.TestCase):
    def test_accent_case_spacing(self):
        self.assertEqual(audit.norm("  QUINIELÓN  "), "quinielon")
    def test_alias_results(self):
        self.assertEqual(audit.canon("El Quinielon Dia"), audit.canon("Quinielón"))
        self.assertEqual(audit.canon("Anguilla 8AM"), audit.canon("Anguila 8 AM"))
    def test_known_schedule_alias(self):
        self.assertNotEqual(audit.canon("Florida 9:45 PM"), audit.canon("Florida 9:50 PM"))
    def test_different_draws_not_collapsed(self):
        self.assertNotEqual(audit.canon("Suerte 12:30 PM"), audit.canon("Suerte 6 PM"))
class CanonicalNamesTests(unittest.TestCase):
    def test_external_aliases_canonicalize(self):
        import sys
        sys.path.insert(0, str(SCRIPT.parents[1]))
        import scraper
        self.assertEqual(scraper.canonizar_nombre_sorteo("Anguilla 8AM"), "Anguila 8 AM")
        self.assertEqual(scraper.canonizar_nombre_sorteo("El Quinielon Dia"), "Quinielón")
        self.assertEqual(scraper.canonizar_nombre_sorteo("Florida 9:45 PM"), "Florida 9:50 PM")
        self.assertEqual(scraper.canonizar_nombre_sorteo("Tennessee 6:30 PM"), "Tennessee 6:30 PM")

if __name__=="__main__": unittest.main()
