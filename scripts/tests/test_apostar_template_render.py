import os
import unittest
import re

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

    def test_heading_contains_only_title_and_highlight_css_is_in_style_block(self):
        html = render_to_string("jugadas/apostar.html", context={})
        heading = re.search(r'<div class="page-title">\\s*<h4>(.*?)</h4>', html, re.S)
        self.assertIsNotNone(heading, "No se encontró el encabezado principal de Apostar")
        self.assertEqual(heading.group(1).strip(), "🎲 Apostar")

        styles = re.findall(r'<style\\b[^>]*>(.*?)</style>', html, re.I | re.S)
        self.assertTrue(
            any(".proc-mirror-wrap" in style and ".proc-token-err" in style for style in styles),
            "Los estilos de resaltado deben estar dentro de un bloque <style>",
        )

        scripts = re.findall(r'<script\\b[^>]*>(.*?)</script>', html, re.I | re.S)
        self.assertTrue(any("function fechaCubaGeorgia" in script for script in scripts))
        self.assertNotIn("<script", heading.group(1))
        self.assertNotIn(".proc-mirror-wrap", heading.group(1))


if __name__ == "__main__":
    unittest.main()
