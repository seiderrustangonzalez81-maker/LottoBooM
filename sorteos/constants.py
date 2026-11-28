# -*- coding: utf-8 -*-
"""Matriz de formas por sorteo, centralizada en config_sorteos_formas.json."""

import json
from pathlib import Path

CONFIG_FORMAS_PATH = Path(__file__).resolve().parent.parent / "config_sorteos_formas.json"

with CONFIG_FORMAS_PATH.open("r", encoding="utf-8") as archivo:
    MATRIZ = json.load(archivo)

if not isinstance(MATRIZ, dict):
    raise TypeError("config_sorteos_formas.json debe contener un objeto JSON")
