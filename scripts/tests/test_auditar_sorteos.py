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
        self.assertEqual(audit.canon("Loteka 1:30 PM"), audit.canon("Loteka 7:50 PM"))
    def test_known_schedule_alias(self):
        self.assertEqual(audit.canon("Florida 9:45 PM"), audit.canon("Florida 9:50 PM"))
    def test_different_draws_not_collapsed(self):
        self.assertNotEqual(audit.canon("Suerte 12:30 PM"), audit.canon("Suerte 6 PM"))
class CanonicalNamesTests(unittest.TestCase):
    def test_external_aliases_canonicalize_without_scraper_import(self):
        import ast, re, unicodedata
        path=SCRIPT.parents[1]/"scraper.py"
        tree=ast.parse(path.read_text(encoding="utf-8"))
        nodes=[n for n in tree.body if isinstance(n,(ast.Assign,ast.FunctionDef)) and (
            (isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=="ALIASES_NOMBRES_SORTEOS" for t in n.targets))
            or (isinstance(n,ast.FunctionDef) and n.name=="canonizar_nombre_sorteo"))]
        ns={"re":re,"unicodedata":unicodedata}
        exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),"exec"),ns)
        canon=ns["canonizar_nombre_sorteo"]
        self.assertEqual(canon("Anguilla 8AM"), "Anguila 8 AM")
        self.assertEqual(canon("El Quinielon Dia"), "Quinielón")
        self.assertEqual(canon("Florida 9:45 PM"), "Florida 9:50 PM")
        self.assertEqual(canon("Tennessee 6:30 PM"), "Tennessee 6:30 PM")

class TemplateIdTests(unittest.TestCase):
    def test_mutually_exclusive_template_branches_are_not_duplicates(self):
        self.assertEqual(audit.template_duplicate_ids('{% if a %}<input id="x">{% else %}<input id="x">{% endif %}'), [])
    def test_simultaneous_static_ids_are_reported(self):
        self.assertEqual(audit.template_duplicate_ids('<div id="x"></div><div id="x"></div>'), ["x"])
    def test_ids_inside_scripts_are_ignored(self):
        self.assertEqual(audit.template_duplicate_ids('<div id="x"></div><script>const str = "id=x";</script>'), [])

class CubaOverrideTests(unittest.TestCase):
    def test_override_has_explicit_start_and_end(self):
        import importlib.util
        path=SCRIPT.parents[1]/"LottoBooM"/"utils.py"
        spec=importlib.util.spec_from_file_location("cuba_utils",path)
        mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        from datetime import date
        self.assertFalse(mod.es_verano_cuba(date(2025,1,15)))
        self.assertTrue(mod.es_verano_cuba(date(2025,7,15)))
        self.assertTrue(mod.es_verano_cuba(date(2026,11,1)))
        self.assertTrue(mod.es_verano_cuba(date(2027,11,7)))
        self.assertFalse(mod.es_verano_cuba(date(2027,11,8)))

if __name__=="__main__": unittest.main()
