import ast
import os
import unittest
from unittest.mock import patch
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo
import tzdata

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "LottoBooM.settings")
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("SECRET_KEY", "ci-only-not-a-production-secret")
import django
django.setup()

from LottoBooM.utils import CUBA_UTC4_START_UTC, CUBA_UTC4_END_UTC, es_verano_cuba
from jugadas.views import _zona_horaria_cuba
from sorteos.utils import (
    _tz_cuba, calcular_estado_sorteo, get_proximo_datetime_sorteo,
    obtener_hora_desde_horarios,
)
from sorteos.views import DIAS_SEMANA_ES, _temporada_actual


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


    def test_georgia_previous_cycle_window_survives_instant_aware_change(self):
        draw = SimpleNamespace(
            nombre="Georgia 11:34 PM",
            horarios={"verano": {"lunes": "23:34"}},
            hora_salida=None,
            minutos_cierre=5,
        )
        now_utc = datetime(2026, 11, 24, 4, 10, tzinfo=timezone.utc)
        result = calcular_estado_sorteo(draw, now_utc, date(2026, 11, 23))
        # 23:34 Eastern (UTC-5) equivale a 00:34 del día siguiente en Cuba (UTC-4).
        self.assertEqual(result.hora_salida, time(0, 34))
        self.assertEqual(result.hora_cierre, datetime(2026, 11, 24, 0, 24, tzinfo=timezone(timedelta(hours=-4))))
        self.assertEqual(result.hora_cierre.utcoffset(), timedelta(hours=-4))

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


    def test_weekday_selection_is_locale_independent(self):
        class WeekdayOnly:
            def __init__(self, weekday):
                self._weekday = weekday

            def weekday(self):
                return self._weekday

            def strftime(self, *_args, **_kwargs):
                raise AssertionError("No debe consultarse el nombre del día mediante locale")

        days = ("lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo")
        horarios = {"verano": {day: f"{8 + index:02d}:00" for index, day in enumerate(days)}}
        draw = SimpleNamespace(horarios=horarios, hora_salida=None)

        with patch("sorteos.utils._temporada", return_value="verano"):
            for weekday in range(7):
                with self.subTest(weekday=weekday):
                    self.assertEqual(
                        obtener_hora_desde_horarios(draw, WeekdayOnly(weekday)),
                        time(8 + weekday, 0),
                    )

    def test_view_season_and_weekday_use_shared_cuba_calendar(self):
        self.assertEqual(_temporada_actual(date(2026, 11, 24)), "Verano")
        self.assertEqual(_temporada_actual(date(2027, 11, 7)), "Invierno")
        self.assertEqual(DIAS_SEMANA_ES[date(2026, 11, 23).weekday()], "Lunes")
        self.assertEqual(DIAS_SEMANA_ES[date(2026, 11, 29).weekday()], "Domingo")

    def test_tzdata_release_is_iana_2026f_or_later(self):
        self.assertGreaterEqual(tzdata.IANA_VERSION, "2026f")

    def test_usa_draw_zones_use_iana_dst_and_source_mapping(self):
        tree = ast.parse((ROOT / "scraper.py").read_text(encoding="utf-8"))
        node = next(
            item for item in tree.body
            if isinstance(item, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "ZONAS_ESTADOS" for target in item.targets)
        )
        namespace = {"ZoneInfo": ZoneInfo}
        exec(compile(ast.Module(body=[node], type_ignores=[]), "scraper.py", "exec"), namespace)
        zones = namespace["ZONAS_ESTADOS"]

        self.assertEqual(zones["Florida"].key, "America/New_York")
        self.assertEqual(zones["New York"].key, "America/New_York")
        self.assertEqual(zones["Texas"].key, "America/Chicago")
        self.assertEqual(zones["Tennessee"].key, "America/Chicago")

        eastern = zones["Florida"]
        central = zones["Texas"]
        self.assertEqual(datetime(2026, 1, 15, 12, tzinfo=eastern).utcoffset(), timedelta(hours=-5))
        self.assertEqual(datetime(2026, 7, 15, 12, tzinfo=eastern).utcoffset(), timedelta(hours=-4))
        self.assertEqual(datetime(2026, 1, 15, 12, tzinfo=central).utcoffset(), timedelta(hours=-6))
        self.assertEqual(datetime(2026, 7, 15, 12, tzinfo=central).utcoffset(), timedelta(hours=-5))

        self.assertEqual(datetime(2026, 3, 8, 1, 30, tzinfo=eastern).utcoffset(), timedelta(hours=-5))
        self.assertEqual(datetime(2026, 3, 8, 3, 30, tzinfo=eastern).utcoffset(), timedelta(hours=-4))
        self.assertEqual(datetime(2026, 11, 1, 1, 30, tzinfo=eastern, fold=0).utcoffset(), timedelta(hours=-4))
        self.assertEqual(datetime(2026, 11, 1, 1, 30, tzinfo=eastern, fold=1).utcoffset(), timedelta(hours=-5))
        self.assertEqual(datetime(2026, 3, 8, 1, 30, tzinfo=central).utcoffset(), timedelta(hours=-6))
        self.assertEqual(datetime(2026, 3, 8, 3, 30, tzinfo=central).utcoffset(), timedelta(hours=-5))
        self.assertEqual(datetime(2026, 11, 1, 1, 30, tzinfo=central, fold=0).utcoffset(), timedelta(hours=-5))
        self.assertEqual(datetime(2026, 11, 1, 1, 30, tzinfo=central, fold=1).utcoffset(), timedelta(hours=-6))


if __name__ == "__main__":
    unittest.main()

    def test_legacy_five_minute_setting_cannot_shorten_fixed_cutoff(self):
        draw = SimpleNamespace(
            nombre="Test fixed cutoff",
            horarios={"verano": {"lunes": "11:15"}},
            hora_salida=None,
            minutos_cierre=5,
        )
        cuba_utc4 = timezone(timedelta(hours=-4))
        now = datetime(2026, 11, 23, 11, 5, tzinfo=cuba_utc4)
        result = calcular_estado_sorteo(draw, now, date(2026, 11, 23))
        self.assertEqual(result.hora_cierre, datetime(2026, 11, 23, 11, 5, tzinfo=cuba_utc4))
        self.assertEqual(result.estado_actual, "cerrado")

    def test_texas_draws_with_null_sunday_are_not_scheduled(self):
        draw = SimpleNamespace(
            nombre="Texas 11 PM",
            horarios={"verano": {"domingo": None}, "invierno": {"domingo": None}},
            hora_salida=None,
        )
        from sorteos.utils import get_datetime_salida_cuba
        self.assertIsNone(get_datetime_salida_cuba(draw, date(2026, 11, 29)))

    def test_sunday_schedule_uses_its_own_time_not_weekday_time(self):
        from sorteos.utils import get_datetime_salida_cuba
        primera = SimpleNamespace(
            nombre="Primera 7 PM",
            horarios={
                "verano": {"domingo": "16:00"},
                "invierno": {"domingo": "15:00"},
            },
            hora_salida=None,
        )
        self.assertEqual(
            get_datetime_salida_cuba(primera, date(2026, 11, 29)).time(),
            time(16, 0),
        )
        real_noche = SimpleNamespace(
            nombre="Real Noche",
            horarios={
                "verano": {"domingo": "20:00"},
                "invierno": {"domingo": "19:00"},
            },
            hora_salida=None,
        )
        self.assertEqual(
            get_datetime_salida_cuba(real_noche, date(2026, 11, 29)).time(),
            time(20, 0),
        )

    def test_winter_sunday_schedule_uses_winter_clock(self):
        from sorteos.utils import get_datetime_salida_cuba
        winter_sunday = date(2027, 11, 14)
        primera = SimpleNamespace(
            nombre="Primera 7 PM",
            horarios={"invierno": {"domingo": "15:00"}, "verano": {"domingo": "16:00"}},
            hora_salida=None,
        )
        real_noche = SimpleNamespace(
            nombre="Real Noche",
            horarios={"invierno": {"domingo": "19:00"}, "verano": {"domingo": "20:00"}},
            hora_salida=None,
        )
        self.assertEqual(get_datetime_salida_cuba(primera, winter_sunday).time(), time(15, 0))
        self.assertEqual(get_datetime_salida_cuba(real_noche, winter_sunday).time(), time(19, 0))
    def test_haiti_bolet_morning_uses_haitian_timezone_and_evening_uses_dominican(self):
        from sorteos.utils import get_datetime_salida_cuba
        haiti_morning = SimpleNamespace(
            nombre="Haití 1",
            horarios={"invierno": {"jueves": "09:30"}, "verano": {"jueves": "09:30"}},
            hora_salida=None,
        )
        haiti_evening = SimpleNamespace(
            nombre="Haití 4",
            horarios={"invierno": {"jueves": "17:30"}, "verano": {"jueves": "17:30"}},
            hora_salida=None,
        )
        self.assertEqual(get_datetime_salida_cuba(haiti_morning, date(2026, 11, 26)).time(), time(10, 30))
        self.assertEqual(get_datetime_salida_cuba(haiti_evening, date(2026, 11, 26)).time(), time(17, 30))

    def test_haiti_and_cuba_realign_after_haitian_dst_returns(self):
        from sorteos.utils import get_datetime_salida_cuba
        haiti_morning = SimpleNamespace(
            nombre="Haití 1",
            horarios={"invierno": {"domingo": "09:30"}, "verano": {"domingo": "09:30"}},
            hora_salida=None,
        )
        self.assertEqual(get_datetime_salida_cuba(haiti_morning, date(2027, 11, 14)).time(), time(9, 30))
