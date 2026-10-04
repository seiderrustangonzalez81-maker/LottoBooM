# -*- coding: utf-8 -*-
"""
Tablas unicas de dosis, limites y sobres para la plataforma.
Esta es la FUENTE DE VERDAD. Cualquier otro DEFAULTS debe eliminarse.
"""

MULTIPLICADOR_SUPERADMIN = 50

# Dosis: cuanto se paga por cada $1 apostado
DOSIS_GLOBAL = {
    'fijo': 80,
    'pf': 80,
    'pick 2': 80,
    'pick 3': 400,
    'pick 4': 2000,
    'pick 5': 5000,
    'corridos': 30,
    'centenas corridas': 200,
    'tripleta': 9000,
    'parlet': 1000,
    'super parlet': 1500,
    'superparlet': 1500,
    'vs pick2': 1000,
    'vspick2': 1000,
    'vs pf': 1000,
    'vspf': 1000,
    'pick2 vs pf': 1000,
    'pick2vspf': 1000,
    'posicion': 80,
}  # PATCH_DOSIS_CLEANUP_V1: 'posición' eliminada — _normalizar() ahora quita acentos

# Limites: monto maximo por apuesta (el sobre = mismo valor por default)
LIMITES_POR_FORMA = {
    'fijo': 2000,
    'pf': 2000,
    'pick 2': 2000,
    'pick 3': 500,
    'pick 4': 1000,
    'pick 5': 5000,
    'corridos': 3000,
    'centenas corridas': 500,
    'tripleta': 100,
    'parlet': 1000,
    'super parlet': 1000,
    'superparlet': 1000,
    'vs pick2': 200,
    'vspick2': 200,
    'vs pf': 200,
    'vspf': 200,
    'pick2 vs pf': 200,
    'pick2vspf': 200,
    'posicion': 1000,
}  # PATCH_DOSIS_CLEANUP_V1

# Sobrelimite = mismo valor que limite por default
SOBRE_POR_FORMA = dict(LIMITES_POR_FORMA)

# Limites globales de plataforma (fallback)
LIMITES_GLOBAL = {
    'minimo': 1,
    'maximo': 10000,
    'sobrelimite': 10000,
}


def _normalizar(nombre):
    # PATCH_DOSIS_CLEANUP_V1: quita acentos para que 'Posición' == 'posicion'
    import unicodedata
    s = (nombre or '').strip().lower()
    s = unicodedata.normalize('NFD', s)
    return ''.join(c for c in s if unicodedata.category(c) != 'Mn')


def get_dosis_global(forma_juego_nombre):
    return DOSIS_GLOBAL.get(_normalizar(forma_juego_nombre), 0)


def get_limite_por_forma(forma_juego_nombre):
    return LIMITES_POR_FORMA.get(_normalizar(forma_juego_nombre), 1000)


def get_sobre_por_forma(forma_juego_nombre):
    return SOBRE_POR_FORMA.get(_normalizar(forma_juego_nombre), get_limite_por_forma(forma_juego_nombre))


def get_limites_globales():
    return LIMITES_GLOBAL


def get_pool_global():
    return LIMITES_GLOBAL['maximo'] + LIMITES_GLOBAL['sobrelimite']


def get_pool_global_superadmin():
    base = LIMITES_GLOBAL['maximo'] + LIMITES_GLOBAL['sobrelimite']
    return base * MULTIPLICADOR_SUPERADMIN


def get_sobrelimite_global_superadmin():
    return LIMITES_GLOBAL['sobrelimite'] * MULTIPLICADOR_SUPERADMIN
