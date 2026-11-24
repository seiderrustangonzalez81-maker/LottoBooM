import ast
import unittest
from datetime import datetime, date, time, timedelta, timezone as datetime_timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

VIEWS = Path(__file__).resolve().parents[2] / "jugadas" / "views.py"
TREE = ast.parse(VIEWS.read_text(encoding="utf-8"))
NODE = next(n for n in TREE.body if isinstance(n, ast.FunctionDef) and n.name == "_obtener_sorteos_cuba_estricto")
CUBA = ZoneInfo("America/Havana")


class QuerySetStub(list):
    def order_by(self, field):
        return self


class DrawManager:
    def __init__(self, draws):
        self.draws = draws

    def filter(self, **kwargs):
        return QuerySetStub(self.draws)


def build_helper(now, draws):
    namespace = {
        "ZoneInfo": ZoneInfo,
        "pytz": __import__("pytz"),
        "timezone": SimpleNamespace(now=lambda: now),
        "es_verano_cuba": lambda d: False,
        "time": time,
        "datetime": datetime,
        "timedelta": timedelta,
        "datetime_timezone": datetime_timezone,
        "_zona_horaria_cuba": lambda fecha: datetime_timezone(timedelta(hours=-5)),
        "Sorteo": SimpleNamespace(objects=DrawManager(draws)),
        "logger": Mock(),
    }
    exec(compile(ast.Module(body=[NODE], type_ignores=[]), str(VIEWS), "exec"), namespace)
    return namespace[NODE.name]


def draw(name, schedule, manual="11:30", close=10):
    return SimpleNamespace(
        nombre=name,
        activo=True,
        horarios={"invierno": {"lunes": schedule}} if schedule is not False else {},
        hora_salida=time.fromisoformat(manual) if manual else None,
        minutos_cierre=close,
    )


class DrawSelectorCalendarTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 23, 11, 0, tzinfo=CUBA)

    def test_open_draws_only_for_regular_roles(self):
        open_draw = draw("Open", "11:20")
        closed_draw = draw("Closed", "11:05")
        no_schedule = draw("No Sunday", None)
        exited = draw("Already drawn", "10:30")
        helper = build_helper(self.now, [open_draw, closed_draw, no_schedule, exited])
        result = helper(incluir_cerrados=False)
        self.assertEqual([d.nombre for d in result], ["Open"])
        self.assertEqual(open_draw.estado_actual, "abierto")

    def test_bank_and_superadmin_can_select_closed_but_not_exited_draws(self):
        open_draw = draw("Open", "11:20")
        closed_draw = draw("Closed", "11:05")
        exited = draw("Already drawn", "10:30")
        helper = build_helper(self.now, [open_draw, closed_draw, exited])
        result = helper(incluir_cerrados=True)
        self.assertEqual([d.nombre for d in result], ["Open", "Closed"])
        self.assertEqual(closed_draw.estado_actual, "cerrado")

    def test_close_is_exactly_ten_minutes_even_if_record_says_five(self):
        draw_with_legacy_five = draw("Legacy five-minute draw", "11:15", close=5)
        helper = build_helper(self.now + timedelta(minutes=5), [draw_with_legacy_five])
        result = helper(incluir_cerrados=True)
        self.assertEqual(len(result), 1)
        self.assertEqual(draw_with_legacy_five.estado_actual, "cerrado")
        self.assertEqual(draw_with_legacy_five.hora_cierre, datetime(2026, 11, 23, 11, 5, tzinfo=CUBA))

    def test_missing_day_in_weekly_schedule_does_not_fallback_to_manual_time(self):
        missing_day = draw("Unscheduled", None, manual="11:30")
        helper = build_helper(self.now, [missing_day])
        self.assertEqual(helper(incluir_cerrados=True), [])

    def test_default_close_window_is_ten_minutes(self):
        missing_close = draw("Default close", "11:20", close=None)
        helper = build_helper(self.now, [missing_close])
        result = helper()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].hora_cierre.hour, 11)
        self.assertEqual(result[0].hora_cierre.minute, 10)


if __name__ == "__main__":
    unittest.main()
