from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

from django.test import SimpleTestCase

from sorteos.utils import (calcular_estado_sorteo, get_hora_cierre, get_datetime_salida_cuba, get_proximo_datetime_sorteo)
from sorteos.helpers import get_hora_cierre as get_hora_cierre_legacy


class CierreSorteosCubaTests(SimpleTestCase):
    def setUp(self):
        self.fecha = date(2026, 11, 23)  # lunes, dentro del UTC-4 configurado
        dias = ("lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo")
        self.sorteo = SimpleNamespace(
            nombre="Prueba horario",
            horarios={"verano": {dia: "12:00" for dia in dias}},
            hora_salida=None,
            minutos_cierre=10,
        )
        self.cuba = timezone(timedelta(hours=-4))

    def test_cierre_es_exactamente_diez_minutos_antes_de_la_salida(self):
        cierre = get_hora_cierre(self.sorteo, self.fecha)
        self.assertEqual(cierre, datetime(2026, 11, 23, 11, 50, tzinfo=self.cuba))
        self.assertIsNotNone(cierre.utcoffset())

    def test_sorteo_sigue_abierto_un_segundo_antes_del_cierre(self):
        ahora = datetime(2026, 11, 23, 11, 49, 59, tzinfo=self.cuba)
        estado = calcular_estado_sorteo(self.sorteo, ahora, self.fecha)
        self.assertEqual(estado.estado_actual, "abierto")

    def test_sorteo_se_cierra_en_el_instante_configurado_no_antes(self):
        ahora = datetime(2026, 11, 23, 11, 50, tzinfo=self.cuba)
        estado = calcular_estado_sorteo(self.sorteo, ahora, self.fecha)
        self.assertEqual(estado.estado_actual, "cerrado")

    def test_compatibilidad_de_jugadas_usa_el_mismo_cierre_aware(self):
        cierre = get_hora_cierre_legacy(self.sorteo, self.fecha)
        self.assertEqual(cierre, get_hora_cierre(self.sorteo, self.fecha))
        self.assertIsNotNone(cierre.utcoffset())

    def _sorteo_usa(self, nombre, hora, origen="americano"):
        dias = ("lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo")
        return SimpleNamespace(
            nombre=nombre,
            origen=origen,
            horarios={
                "verano": {dia: hora for dia in dias},
                "invierno": {dia: hora for dia in dias},
            },
            hora_salida=None,
            minutos_cierre=10,
        )

    def test_new_york_se_convierte_a_hora_cuba(self):
        sorteo = self._sorteo_usa("New York 2:30 PM", "14:30")
        salida = get_datetime_salida_cuba(sorteo, date(2026, 11, 26))
        self.assertEqual(salida, datetime(2026, 11, 26, 15, 30, tzinfo=self.cuba))

    def test_texas_se_convierte_desde_hora_central_a_cuba(self):
        sorteo = self._sorteo_usa("Texas 1:20 PM", "13:20")
        salida = get_datetime_salida_cuba(sorteo, date(2026, 11, 26))
        self.assertEqual(salida, datetime(2026, 11, 26, 15, 20, tzinfo=self.cuba))

    def test_georgia_de_noche_pasa_a_medianoche_cuba_sin_cambiar_dia_operativo(self):
        sorteo = self._sorteo_usa("Georgia 11:40 PM", "23:30")
        salida = get_datetime_salida_cuba(sorteo, date(2026, 11, 26))
        self.assertEqual(salida, datetime(2026, 11, 27, 0, 30, tzinfo=self.cuba))
        cierre = get_hora_cierre(sorteo, date(2026, 11, 26))
        self.assertEqual(cierre, datetime(2026, 11, 27, 0, 20, tzinfo=self.cuba))

    def test_draw_americano_a_la_una_sigue_visible_antes_del_cierre(self):
        sorteo = self._sorteo_usa("Texas 11 PM", "23:00")
        ahora = datetime(2026, 11, 27, 0, 40, tzinfo=self.cuba)
        salida, _ = get_proximo_datetime_sorteo(sorteo, ahora)
        self.assertEqual(salida, datetime(2026, 11, 27, 1, 0, tzinfo=self.cuba))
        estado = calcular_estado_sorteo(sorteo, ahora)
        self.assertEqual(estado.estado_actual, "abierto")

    def test_dominicanas_y_haitianas_no_reciben_desplazamiento_americano(self):
        sorteo = self._sorteo_usa("Haití 6", "19:30", origen="haitiano")
        salida = get_datetime_salida_cuba(sorteo, date(2026, 11, 26))
        self.assertEqual(salida, datetime(2026, 11, 26, 19, 30, tzinfo=self.cuba))

    def test_georgia_sigue_abierto_hasta_diez_minutos_antes_de_la_salida(self):
        sorteo = self._sorteo_usa("Georgia 11:40 PM", "23:30")
        antes = datetime(2026, 11, 27, 0, 19, 59, tzinfo=self.cuba)
        en_cierre = datetime(2026, 11, 27, 0, 20, 0, tzinfo=self.cuba)
        self.assertEqual(
            calcular_estado_sorteo(sorteo, antes, date(2026, 11, 26)).estado_actual,
            "abierto",
        )
        self.assertEqual(
            calcular_estado_sorteo(sorteo, en_cierre, date(2026, 11, 26)).estado_actual,
            "cerrado",
        )

    def test_texas_cierra_a_las_cero_cincuenta_hora_cuba(self):
        sorteo = self._sorteo_usa("Texas 11 PM", "23:00")
        antes = datetime(2026, 11, 27, 0, 49, 59, tzinfo=self.cuba)
        en_cierre = datetime(2026, 11, 27, 0, 50, 0, tzinfo=self.cuba)
        self.assertEqual(calcular_estado_sorteo(sorteo, antes).estado_actual, "abierto")
        self.assertEqual(calcular_estado_sorteo(sorteo, en_cierre).estado_actual, "cerrado")

    def test_new_yol_real_se_convierte_desde_hora_nueva_york(self):
        sorteo = self._sorteo_usa("New Yol Real 12:50 PM", "12:50")
        salida = get_datetime_salida_cuba(sorteo, date(2026, 11, 26))
        self.assertEqual(salida, datetime(2026, 11, 26, 13, 50, tzinfo=self.cuba))
    def test_texas_actual_pick3_draw_times_convert_to_cuba(self):
        from sorteos.utils import get_datetime_salida_cuba
        cases = [
            ("Texas 11 AM", "10:00", time(12, 0)),
            ("Texas 1:20 PM", "12:27", time(14, 27)),
            ("Texas 7 PM", "18:00", time(20, 0)),
            ("Texas 11 PM", "22:12", time(0, 12)),
        ]
        for nombre, hora_fuente, hora_cuba in cases:
            sorteo = SimpleNamespace(
                nombre=nombre,
                horarios={"verano": {"jueves": hora_fuente}, "invierno": {"jueves": hora_fuente}},
                hora_salida=None,
            )
            with self.subTest(draw=nombre):
                salida = get_datetime_salida_cuba(sorteo, date(2026, 11, 26))
                self.assertEqual(salida.time(), hora_cuba)
