# -*- coding: utf-8 -*-
"""Catálogo de formas por sorteo, centralizado en config_sorteos_formas.json."""
import json
from pathlib import Path

CONFIG_FORMAS_PATH = Path(__file__).resolve().parent.parent / "config_sorteos_formas.json"
with CONFIG_FORMAS_PATH.open(encoding="utf-8") as archivo:
    MATRIZ = json.load(archivo)
