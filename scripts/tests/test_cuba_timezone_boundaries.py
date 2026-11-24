import ast
import os
import unittest
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "LottoBooM.settings")
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("SECRET_KEY", "ci-only-not-a-production-secret")
import django
django.setup()

from LottoBooM.utils import CUBA_UTC4_START_UTC, CUBA_UTC4_END_UTC, es_verano_cuba
from jugadas.views import _zona_horaria_cuba
from sorteos.utils import _tz_cuba, calcular_estado_sorteo, get_proximo_datetime_sorteo


ROOT = Path(__file__).resolve().parents[2]


class CubaTimezoneBoundaryIntegrationTests(unittest.TestCase):
    def test_shared_helpers_follow_exact_utc_transition(self):
        cases = (
            (datetime(2026, 11, 1, 4, 59, 59, tzinfo=timezone.utc), -4),
            (datetime(2026, 11, 1, 5, 0, 0, tzinfo=timezone.utc), -4),
            (datetime(2027, 11, 7, 4, 59, 59, tzinfo=timezone.utc), -4),
            (datetime(2027, 11, 7, 5, 0, 0, tzinfo=timezone.utc), -5),
        )
        self.assertEqual(CUBA_UTC4_START_UTC, cases[1][0])
        self.assertEqual(CUBA_UTC4_END_UTC, cases[3][0])
        for instant, hours in cases:
            expected = timedelta(hours=hours)
            self.assertEqual(_tz_cuba(instant).utcoffset(None), expected)
            self.assertEqual(_zona_horaria_cuba(instant).utcoffset(None), expected)
            self.assertEqual(es_verano_cuba(instant), hours == -4)

    def test_date_and_naive_schedule_use_post_transition_calendar(self):
        self.assertFalse(es_verano_cuba(date(2027, 11, 7)))
        self.assertEqual(_tz_cuba(date(2027, 11, 7)).utcoffset(None), timedelta(hours=-5))
        self.assertEqual(_tz_cuba(datetime(2027, 11, 7, 0, 30)).utcoffset(None), timedelta(hours=-4))
        self.assertEqual(_tz_cuba(datetime(2027, 11, 7, 1, 30)).utcoffset(None), timedelta(hours=-5))

    def test_draw_state_uses_current_instant_and_future_draw_offset_separately(self):
        draw = SimpleNamespace(
            nombre="Test transition draw",
            horarios={
                "verano": {"domingo": "11:00"},
                "invierno": {"domingo": "10:00"},
            },
            hora_salida=None,
        )
        before_fallback = datetime(2027, 11, 7, 4, 30, tzinfo=timezone.utc)
        result = calcular_estado_sorteo(draw, before_fallback, date(2027, 11, 7))
        self.assertEqual(result.hora_salida, time(10, 0))
        self.assertEqual(result.hora_cierre.utcoffset(), timedelta(hours=-5))
        self.assertEqual(result.estado_actual, "abierto")

        after_fallback = datetime(2027, 11, 7, 5, 30, tzinfo=timezone.utc)
        result_after = calcular_estado_sorteo(draw, after_fallback, date(2027, 11, 7))
        self.assertEqual(result_after.hora_cierre.utcoffset(), timedelta(hours=-5))
        self.assertEqual(result_after.estado_actual, "abierto")

    def test_next_draw_datetime_uses_destination_date_offset(self):
        draw = SimpleNamespace(
            nombre="Test next draw",
            horarios={"invierno": {"domingo": "10:00"}},
            hora_salida=None,
        )
        instant = datetime(2027, 11, 7, 5, 30, tzinfo=timezone.utc)
        now_cuba = instant.astimezone(_tz_cuba(instant))
        next_draw, is_today = get_proximo_datetime_sorteo(draw, now_cuba)
        self.assertTrue(is_today)
        self.assertEqual(next_draw.date(), date(2027, 11, 7))
        self.assertEqual(next_draw.time(), time(10, 0))
        self.assertEqual(next_draw.utcoffset(), timedelta(hours=-5))

    def test_scraper_and_django_share_identical_override_boundaries(self):
        path = ROOT / "scraper.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        wanted = {"CUBA_UTC4_DESDE_UTC", "CUBA_UTC4_HASTA_UTC", "CUBA_UTC4"}
        nodes = [
            node for node in tree.body
            if (
                isinstance(node, ast.Assign)
                and any(isinstance(target, ast.Name) and target.id in wanted for target in node.targets)
            ) or (
                isinstance(node, ast.FunctionDef) and node.name == "obtener_hora_cuba"
            )
        ]
        namespace = {
            "datetime": datetime,
            "timezone": timezone,
            "timedelta": timedelta,
            "TZ_CUBA": ZoneInfo("America/Havana"),
        }
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), namespace)
        self.assertEqual(namespace["CUBA_UTC4_DESDE_UTC"], CUBA_UTC4_START_UTC)
        self.assertEqual(namespace["CUBA_UTC4_HASTA_UTC"], CUBA_UTC4_END_UTC)
        for instant, hours in (
            (datetime(2026, 11, 1, 5, 0, tzinfo=timezone.utc), -4),
            (datetime(2027, 11, 7, 4, 59, 59, tzinfo=timezone.utc), -4),
            (datetime(2027, 11, 7, 5, 0, tzinfo=timezone.utc), -5),
        ):
            self.assertEqual(
                namespace["obtener_hora_cuba"](instant).utcoffset(),
                timedelta(hours=hours),
            )


if __name__ == "__main__":
    unittest.main()
