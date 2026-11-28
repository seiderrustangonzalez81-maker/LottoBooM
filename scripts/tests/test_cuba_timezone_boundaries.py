import ast
import os
import sys
import unittest
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo

import tzdata

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "LottoBooM.settings")
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("SECRET_KEY", "ci-only-not-a-production-secret")

import django
django.setup()

from LottoBooM.utils import (  # noqa: E402
    CUBA_UTC4_START_UTC,
    CUBA_UTC4_END_UTC,
    es_verano_cuba,
)
from sorteos.utils import (  # noqa: E402
    _tz_cuba,
    _ahora_local,
    obtener_hora_desde_horarios,
    get_hora_cierre,
    calcular_estado_sorteo,
    get_proximo_datetime_sorteo,
)
from sorteos.views import (  # noqa: E402
    _tz_cuba as _tz_cuba_view,
    _calcular_estado as calcular_estado_vista,
    _temporada_actual,
)
from resultados.views import es_verano_cuba as es_verano_cuba_resultados  # noqa: E402
from sorteos.helpers import get_hora_cierre as get_hora_cierre_legacy  # noqa: E402
from jugadas.management.commands.cancelar_sobrelimites import (  # noqa: E402
    _obtener_cierre_jugada,
)
from sorteos.management.commands.load_results import (  # noqa: E402
    obtener_ahora_cuba,
    temporada_actual as temporada_load_results,
)


UTC = timezone.utc


def _sorteo_transicion():
    return SimpleNamespace(
        nombre="Sorteo de prueba",
        horarios={
            "verano": {"domingo": "11:00"},
            "invierno": {"domingo": "10:00"},
        },
        hora_salida=None,
        minutos_cierre=10,
    )


class WeekdayWithoutLocale:
    def __init__(self, weekday):
        self._weekday = weekday

    def weekday(self):
        return self._weekday

    def strftime(self, *_args, **_kwargs):
        raise AssertionError("La selección del día no debe depender del locale")


class CubaTimezoneBoundaryTests(unittest.TestCase):
    def test_override_has_explicit_start_and_excludes_historical_dates(self):
        self.assertEqual(CUBA_UTC4_START_UTC, datetime(2026, 11, 1, 5, 0, tzinfo=UTC))
        self.assertEqual(CUBA_UTC4_END_UTC, datetime(2027, 11, 7, 5, 0, tzinfo=UTC))

        self.assertFalse(es_verano_cuba(date(2026, 1, 15)))
        self.assertTrue(es_verano_cuba(date(2026, 7, 15)))
        self.assertTrue(es_verano_cuba(date(2026, 10, 31)))
        self.assertTrue(es_verano_cuba(date(2026, 11, 1)))
        self.assertTrue(es_verano_cuba(date(2027, 11, 6)))
        self.assertFalse(es_verano_cuba(date(2027, 11, 7)))

    def test_aware_instants_follow_exact_utc_boundaries(self):
        cases = (
            (datetime(2026, 11, 1, 4, 59, 59, tzinfo=UTC), -4),
            (datetime(2026, 11, 1, 5, 0, 0, tzinfo=UTC), -4),
            (datetime(2027, 11, 7, 4, 59, 59, tzinfo=UTC), -4),
            (datetime(2027, 11, 7, 5, 0, 0, tzinfo=UTC), -5),
        )
        for instant, expected_hours in cases:
            expected = timedelta(hours=expected_hours)
            with self.subTest(instant=instant):
                self.assertEqual(es_verano_cuba(instant), expected_hours == -4)
                self.assertEqual(_tz_cuba(instant).utcoffset(None), expected)
                self.assertEqual(_tz_cuba_view(instant).utcoffset(None), expected)

    def test_repeated_local_hour_uses_fold(self):
        first_0030 = datetime(2027, 11, 7, 0, 30, fold=0)
        second_0030 = datetime(2027, 11, 7, 0, 30, fold=1)
        self.assertTrue(es_verano_cuba(first_0030))
        self.assertFalse(es_verano_cuba(second_0030))

    def test_results_view_uses_shared_season_helper(self):
        self.assertFalse(es_verano_cuba_resultados(date(2026, 1, 15)))
        self.assertTrue(es_verano_cuba_resultados(date(2026, 11, 28)))

    def test_sorteos_view_season_label_uses_cuba_calendar_not_month(self):
        self.assertEqual(_temporada_actual(date(2026, 11, 28)), "Verano")
        self.assertEqual(_temporada_actual(date(2027, 11, 7)), "Invierno")

    def test_current_cuba_time_uses_explicit_override(self):
        instant = datetime(2026, 11, 28, 13, 0, tzinfo=UTC)
        with patch("sorteos.utils.timezone.now", return_value=instant):
            now_cuba = _ahora_local()
        self.assertEqual(now_cuba.hour, 9)
        self.assertEqual(now_cuba.utcoffset(), timedelta(hours=-4))

    def test_closing_and_state_use_destination_date_offset(self):
        draw = _sorteo_transicion()
        target = date(2027, 11, 7)
        expected_close = datetime(2027, 11, 7, 9, 50, tzinfo=timezone(timedelta(hours=-5)))

        self.assertEqual(get_hora_cierre(draw, target), expected_close)

        instant = datetime(2027, 11, 7, 5, 30, tzinfo=UTC)
        state = calcular_estado_sorteo(draw, instant, target)
        self.assertEqual(state.hora_cierre, expected_close)
        self.assertEqual(state.estado_actual, "abierto")

        view_state = calcular_estado_vista(
            draw,
            time(10, 0),
            instant.astimezone(timezone(timedelta(hours=-5))),
        )
        self.assertEqual(view_state["hora_cierre"], expected_close)
        self.assertEqual(view_state["estado"], "abierto")

    def test_legacy_and_overlimit_closure_use_canonical_aware_datetime(self):
        draw = _sorteo_transicion()
        target = date(2027, 11, 7)
        expected_close = datetime(
            2027, 11, 7, 9, 50,
            tzinfo=timezone(timedelta(hours=-5)),
        )

        self.assertEqual(get_hora_cierre_legacy(draw, target), expected_close)
        self.assertEqual(
            _obtener_cierre_jugada(
                SimpleNamespace(sorteo=draw, fecha_sorteo=target)
            ),
            expected_close,
        )
        self.assertIsNone(
            _obtener_cierre_jugada(
                SimpleNamespace(sorteo=draw, fecha_sorteo=None)
            )
        )

    def test_next_draw_uses_explicit_cuba_offset(self):
        draw = _sorteo_transicion()
        instant = datetime(2027, 11, 7, 5, 30, tzinfo=UTC)
        now_cuba = instant.astimezone(_tz_cuba(instant))

        next_draw, is_today = get_proximo_datetime_sorteo(draw, now_cuba)
        self.assertTrue(is_today)
        self.assertEqual(next_draw, datetime(2027, 11, 7, 10, 0, tzinfo=timezone(timedelta(hours=-5))))

    def test_weekday_selection_is_locale_independent_for_all_days(self):
        dias = ("lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo")
        with patch("sorteos.utils._temporada", return_value="verano"):
            for weekday, dia in enumerate(dias):
                draw = SimpleNamespace(
                    horarios={"verano": {dia: "08:00"}},
                    hora_salida=None,
                )
                with self.subTest(dia=dia):
                    self.assertEqual(
                        obtener_hora_desde_horarios(draw, WeekdayWithoutLocale(weekday)),
                        time(8, 0),
                    )

    def test_null_or_missing_schedule_returns_no_draw_time(self):
        target = date(2026, 11, 28)
        self.assertIsNone(
            obtener_hora_desde_horarios(
                SimpleNamespace(horarios=None, hora_salida=None),
                target,
            )
        )
        self.assertIsNone(
            get_hora_cierre(
                SimpleNamespace(horarios={}, hora_salida=None, minutos_cierre=10),
                target,
            )
        )

    def test_results_loader_uses_shared_cuba_override(self):
        instant = datetime(2026, 11, 28, 13, 0, tzinfo=UTC)
        local = obtener_ahora_cuba(instant)
        self.assertEqual(local.hour, 9)
        self.assertEqual(local.utcoffset(), timedelta(hours=-4))
        self.assertEqual(temporada_load_results(local), "verano")

        winter = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
        self.assertEqual(temporada_load_results(winter), "invierno")

    def test_tzdata_release_and_eastern_central_dst_rules(self):
        self.assertGreaterEqual(tzdata.IANA_VERSION, "2026f")
        eastern = ZoneInfo("America/New_York")
        central = ZoneInfo("America/Chicago")

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

    def test_scraper_and_django_override_instants_stay_aligned(self):
        tree = ast.parse((ROOT / "scraper.py").read_text(encoding="utf-8"))
        wanted = {"CUBA_UTC4_DESDE_UTC", "CUBA_UTC4_HASTA_UTC"}
        nodes = [
            node for node in tree.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id in wanted for target in node.targets)
        ]
        namespace = {"datetime": datetime, "timezone": timezone, "timedelta": timedelta}
        exec(compile(ast.Module(body=nodes, type_ignores=[]), "scraper.py", "exec"), namespace)
        self.assertEqual(namespace["CUBA_UTC4_DESDE_UTC"], CUBA_UTC4_START_UTC)
        self.assertEqual(namespace["CUBA_UTC4_HASTA_UTC"], CUBA_UTC4_END_UTC)


if __name__ == "__main__":
    unittest.main()
