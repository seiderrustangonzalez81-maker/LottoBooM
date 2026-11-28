# sorteos/helpers.py
"""Compatibilidad para el helper histórico de cierre de sorteos."""


def get_hora_cierre(sorteo, fecha=None):
    """Delegar en el cálculo canónico, que devuelve un datetime aware de Cuba.

    Se mantiene este módulo porque jugadas.models lo importa durante la carga
    de modelos; la importación diferida evita una dependencia circular.
    """
    from .utils import get_hora_cierre as get_hora_cierre_canonico

    return get_hora_cierre_canonico(sorteo, fecha)
