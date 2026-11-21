import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "LottoBooM.settings")
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("SECRET_KEY", "ci-only-not-a-production-secret")
import django
django.setup()

import unittest
from django.core.exceptions import ValidationError
from sorteos.forms import SorteoForm


class SorteoHorarioValidationTests(unittest.TestCase):
    def clean(self, value):
        form = SorteoForm()
        form.cleaned_data = {"horarios": value}
        return form.clean_horarios()

    def test_valid_seasonal_schedule(self):
        self.assertEqual(
            self.clean('{"invierno":{"lunes":"08:15","domingo":null},"verano":{"martes":"09:00"}}'),
            {"invierno":{"lunes":"08:15","domingo":None},"verano":{"martes":"09:00"}},
        )

    def test_rejects_json_array(self):
        with self.assertRaises(ValidationError):
            self.clean("[]")

    def test_rejects_non_object_season(self):
        with self.assertRaises(ValidationError):
            self.clean('{"invierno":["08:00"]}')

    def test_rejects_unknown_day(self):
        with self.assertRaises(ValidationError):
            self.clean('{"invierno":{"funday":"08:00"}}')

    def test_rejects_invalid_clock_time(self):
        with self.assertRaises(ValidationError):
            self.clean('{"invierno":{"lunes":"25:61"}}')

    def test_allows_blank_or_unscheduled_days(self):
        self.assertEqual(self.clean('{"invierno":{"lunes":"","domingo":null}}'), {"invierno":{"lunes":"","domingo":None}})


if __name__ == "__main__":
    unittest.main()
