import csv
import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class SundayDrawCalendarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads((ROOT / "sorteos" / "fixtures" / "sorteos.json").read_text(encoding="utf-8"))
        cls.draws = {item["fields"]["nombre"]: item["fields"] for item in cls.fixture}
        cls.config = json.loads((ROOT / "config_sorteos_formas.json").read_text(encoding="utf-8"))
        with (ROOT / "sorteos_formas.csv").open(encoding="utf-8-sig", newline="") as handle:
            cls.csv_names = {row["nombre_sorteo"] for row in csv.DictReader(handle)}
        scraper = (ROOT / "scraper.py").read_text(encoding="utf-8")
        match = re.search(r"SORTEOS_ESPERADOS\s*=\s*\[([\s\S]*?)\n\]", scraper)
        cls.expected = set(re.findall(r'"([^"]+)"', match.group(1)))

    def test_all_four_catalog_sources_have_the_same_59_draws(self):
        fixture_names = set(self.draws)
        self.assertEqual(len(fixture_names), 59)
        self.assertEqual(fixture_names, set(self.config))
        self.assertEqual(fixture_names, self.csv_names)
        self.assertEqual(fixture_names, self.expected)

    def test_texas_draws_without_sunday_are_explicitly_disabled(self):
        for name in (
            "Texas 11 AM", "Texas 1:20 PM", "Texas 7 PM", "Texas 11 PM",
            "Tennessee 9:28 AM", "Tennessee 12:28 PM",
        ):
            with self.subTest(draw=name):
                schedule = self.draws[name]["horarios"]
                self.assertIsNone(schedule["invierno"]["domingo"])
                self.assertIsNone(schedule["verano"]["domingo"])

    def test_sunday_time_changes_are_explicit_for_each_season(self):
        expected = {
            "Primera 7 PM": ("18:00", "19:00"),
            "Nacional": ("17:00", "18:00"),
            "Leidsa 8:55 PM": ("14:55", "15:55"),
            "Pega 3+": ("14:55", "15:55"),
            "Quinielón Noche": ("18:00", "19:00"),
            "Real Noche": ("19:00", "20:00"),
            "Loteka Tarde": ("12:30", "13:30"),
            "Lotedom Noche": ("21:00", "22:00"),
            "Quemaito Noche": ("21:00", "22:00"),
        }
        for name, (winter, summer) in expected.items():
            with self.subTest(draw=name):
                schedule = self.draws[name]["horarios"]
                self.assertEqual(schedule["invierno"]["domingo"], winter)
                self.assertEqual(schedule["verano"]["domingo"], summer)


    def test_usa_catalog_keeps_official_source_local_draw_times(self):
        expected = {
            "Texas 11 AM": "10:00",
            "Texas 1:20 PM": "12:27",
            "Texas 7 PM": "18:00",
            "Texas 11 PM": "22:12",
            "Florida 1:35 PM": "13:30",
            "Florida 9:50 PM": "21:45",
            "Georgia 12:30 PM": "12:29",
            "Georgia 7 PM": "18:59",
            "Georgia 11:40 PM": "23:34",
            "New Jersey 12:50 PM": "12:59",
            "New Jersey 10:50 PM": "22:57",
        }
        for name, source_time in expected.items():
            with self.subTest(draw=name):
                for season in ("invierno", "verano"):
                    for day in ("lunes", "martes", "miercoles", "jueves", "viernes", "sabado"):
                        self.assertEqual(self.draws[name]["horarios"][season][day], source_time)

    def test_all_haiti_bolet_draws_run_every_day_and_use_source_local_time(self):
        source_times = {
            "Haití 1": "09:30", "Haití 2": "10:30", "Haití 3": "11:30",
            "Haití 4": "17:30", "Haití 5": "18:30", "Haití 6": "19:30",
        }
        for name, source_time in source_times.items():
            with self.subTest(draw=name):
                schedule = self.draws[name]["horarios"]
                for season in ("invierno", "verano"):
                    self.assertEqual(set(schedule[season].values()), {source_time})
                    self.assertEqual(schedule[season]["domingo"], source_time)


    def test_only_explicitly_unscheduled_sunday_draws_are_null(self):
        no_sunday = {
            "Texas 11 AM", "Texas 1:20 PM", "Texas 7 PM", "Texas 11 PM",
            "Tennessee 9:28 AM", "Tennessee 12:28 PM",
        }
        for name, fields in self.draws.items():
            with self.subTest(draw=name):
                for season in ("invierno", "verano"):
                    sunday = fields["horarios"][season]["domingo"]
                    if name in no_sunday:
                        self.assertIsNone(sunday)
                    else:
                        self.assertTrue(sunday, f"{name} debe estar programado el domingo en {season}")

    def test_sunday_draws_that_do_not_change_keep_same_time(self):
        for name in ("Georgia 7 PM", "Florida 9:50 PM", "New York 10:30 PM", "Tennessee 6:28 PM"):
            with self.subTest(draw=name):
                schedule = self.draws[name]["horarios"]
                self.assertEqual(schedule["invierno"]["domingo"], schedule["verano"]["domingo"])


if __name__ == "__main__":
    unittest.main()
