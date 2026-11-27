from datetime import datetime, timedelta, timezone

from django.test import SimpleTestCase

from scraper import calcular_fecha_sorteo_enloteria, fecha_operativa_cuba


CUBA_UTC4 = timezone(timedelta(hours=-4))


class FechasOperativasScraperTests(SimpleTestCase):
    def test_cambio_de_dia_operativo_es_a_la_una(self):
        antes = datetime(2026, 11, 27, 0, 59, tzinfo=CUBA_UTC4)
        inicio = datetime(2026, 11, 27, 1, 0, tzinfo=CUBA_UTC4)
        self.assertEqual(fecha_operativa_cuba(antes), "2026-11-26")
        self.assertEqual(fecha_operativa_cuba(inicio), "2026-11-27")

    def test_new_york_noche_usa_hora_del_estado(self):
        antes_del_sorteo = datetime(2026, 11, 26, 22, 45, tzinfo=CUBA_UTC4)
        despues_del_sorteo = datetime(2026, 11, 26, 23, 45, tzinfo=CUBA_UTC4)
        self.assertEqual(
            calcular_fecha_sorteo_enloteria("New York Noche", antes_del_sorteo),
            "2026-11-25",
        )
        self.assertEqual(
            calcular_fecha_sorteo_enloteria("New York Noche", despues_del_sorteo),
            "2026-11-26",
        )

    def test_texas_once_pm_local_cae_en_el_dia_operativo_siguiente(self):
        antes = datetime(2026, 11, 27, 0, 40, tzinfo=CUBA_UTC4)
        despues = datetime(2026, 11, 27, 1, 1, tzinfo=CUBA_UTC4)
        self.assertEqual(
            calcular_fecha_sorteo_enloteria("Texas 11 PM", antes),
            "2026-11-26",
        )
        self.assertEqual(
            calcular_fecha_sorteo_enloteria("Texas 11 PM", despues),
            "2026-11-27",
        )

    def test_haiti_bolet_se_mantiene_en_hora_publicada_dominicana(self):
        antes = datetime(2026, 11, 26, 19, 15, tzinfo=CUBA_UTC4)
        despues = datetime(2026, 11, 26, 19, 45, tzinfo=CUBA_UTC4)
        self.assertEqual(
            calcular_fecha_sorteo_enloteria("Haiti Bolet 7:30 PM", antes),
            "2026-11-25",
        )
        self.assertEqual(
            calcular_fecha_sorteo_enloteria("Haiti Bolet 7:30 PM", despues),
            "2026-11-26",
        )
