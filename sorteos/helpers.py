# -*- coding: utf-8 -*-
"""Compatibilidad para los consumidores antiguos del cálculo de cierre.

La fuente única de verdad está en sorteos.utils.get_hora_cierre, que devuelve
un datetime aware en hora Cuba y respeta el calendario semanal del sorteo.
"""
def get_hora_cierre(sorteo, fecha=None):
    from sorteos.utils import get_hora_cierre as calcular_cierre
    return calcular_cierre(sorteo, fecha)
