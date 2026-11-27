from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

from django.test import SimpleTestCase

from sorteos.utils import calcular_estado_sorteo, get_hora_cierre
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
