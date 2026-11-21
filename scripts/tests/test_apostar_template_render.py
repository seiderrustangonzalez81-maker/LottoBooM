import os
import unittest

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "LottoBooM.settings")
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("SECRET_KEY", "ci-only-not-a-production-secret")
import django
django.setup()

from django.template.loader import render_to_string


class ApostarTemplateRenderTests(unittest.TestCase):
    def test_template_renders_and_loads_processor_assets(self):
        html = render_to_string("jugadas/apostar.html", context={})
        self.assertIn("apostar_text_validator.js", html)
        self.assertIn("apostar_tripleta.js", html)
        self.assertIn("procErrores", html)
        self.assertIn("btnProcAhora", html)
        self.assertIn("procesarText", html)


if __name__ == "__main__":
    unittest.main()
