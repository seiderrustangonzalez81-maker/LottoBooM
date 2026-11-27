import ast
import re
import unicodedata
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[2]
SCRAPER = ROOT / "scraper.py"


def load_scraper_time_functions():
    tree = ast.parse(SCRAPER.read_text(encoding="utf-8"))
    assignments = {
        "TZ_CUBA", "TZ_ESTE", "TZ_RD", "TZ_HAITI",
        "CUBA_UTC4_DESDE_UTC", "CUBA_UTC4_HASTA_UTC", "CUBA_UTC4",
        "ZONAS_ESTADOS", "HORAS_POR_PALABRA",
    }
    functions = {
        "obtener_hora_cuba", "convertir_a_cuba", "fecha_operativa_cuba",
        "fecha_operativa_actual", "parsear_hora_sorteo", "_hora_enloteria",
        "_ultimo_sorteo_fuente", "calcular_fecha_sorteo_enloteria",
        "zona_horaria_sorteo_usa", "calcular_fechas_esperadas_usa",
    }
    nodes = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id in assignments
            for target in node.targets
        ):
            nodes.append(node)
        elif isinstance(node, ast.FunctionDef) and node.name in functions:
            nodes.append(node)

    namespace = {
        "datetime": datetime,
        "timedelta": timedelta,
        "timezone": timezone,
        "ZoneInfo": ZoneInfo,
        "re": re,
        "unicodedata": unicodedata,
    }
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SCRAPER), "exec"), namespace)
    return namespace


class ScraperSourceCalendarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scraper = load_scraper_time_functions()

    def test_saturday_texas_result_is_not_suppressed_when_run_sunday_after_midnight(self):
        # 00:30 en Cuba el domingo sigue perteneciendo al día operativo sábado.
        now_cuba = datetime(2026, 11, 29, 4, 30, tzinfo=timezone.utc)
        self.assertEqual(
            self.scraper["calcular_fechas_esperadas_usa"]("Texas 11 AM", now_cuba),
            ("2026-11-28", "2026-11-28"),
        )

    def test_sunday_texas_draw_is_not_fabricated_on_monday_after_midnight(self):
        # El candidato de ayer es domingo (sin sorteo); el de hoy aún no ocurrió.
        now_cuba = datetime(2026, 11, 30, 6, 30, tzinfo=timezone.utc)
        self.assertEqual(
            self.scraper["calcular_fechas_esperadas_usa"]("Texas 11 AM", now_cuba),
            (None, None),
        )

    def test_enloteria_uses_candidate_weekday_not_current_weekday(self):
        now_cuba = datetime(2026, 11, 29, 4, 30, tzinfo=timezone.utc)
        self.assertEqual(
            self.scraper["calcular_fecha_sorteo_enloteria"]("Texas 11 AM", now_cuba),
            "2026-11-28",
        )

    def test_us_eastern_and_central_offsets_are_converted_for_both_seasons(self):
        eastern = ZoneInfo("America/New_York")
        winter_now = datetime(2026, 12, 1, 19, 0, tzinfo=timezone.utc)
        summer_now = datetime(2027, 6, 1, 17, 45, tzinfo=timezone.utc)
        winter_draw = self.scraper["_ultimo_sorteo_fuente"](
            "Florida 1:35 PM", winter_now.astimezone(eastern)
        )
        summer_draw = self.scraper["_ultimo_sorteo_fuente"](
            "Florida 1:35 PM", summer_now.astimezone(eastern)
        )
        self.assertEqual(winter_draw.astimezone(timezone.utc), datetime(2026, 12, 1, 18, 30, tzinfo=timezone.utc))
        self.assertEqual(summer_draw.astimezone(timezone.utc), datetime(2027, 6, 1, 17, 30, tzinfo=timezone.utc))

    def test_cuba_keeps_utc_minus_four_until_exact_november_2027_transition(self):
        convert = self.scraper["obtener_hora_cuba"]
        before_extension = convert(datetime(2026, 11, 1, 5, 0, tzinfo=timezone.utc))
        before_end = convert(datetime(2027, 11, 7, 4, 59, tzinfo=timezone.utc))
        at_end = convert(datetime(2027, 11, 7, 5, 0, tzinfo=timezone.utc))
        self.assertEqual(before_extension.utcoffset(), timedelta(hours=-4))
        self.assertEqual(before_end.utcoffset(), timedelta(hours=-4))
        self.assertEqual(at_end.utcoffset(), timedelta(hours=-5))

    def test_naive_cuba_wall_clock_obeys_the_temporary_utc_minus_four_period(self):
        operational_date = self.scraper["fecha_operativa_cuba"]
        self.assertEqual(
            operational_date(datetime(2027, 11, 7, 0, 30)),
            "2027-11-06",
        )
        self.assertEqual(
            operational_date(datetime(2027, 11, 7, 1, 30)),
            "2027-11-07",
        )


if __name__ == "__main__":
    unittest.main()
