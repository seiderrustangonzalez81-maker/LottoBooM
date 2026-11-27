#!/usr/bin/env python3
# Compatibilidad histórica: delega en el cargador centralizado y no borra relaciones.
import os
import runpy
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "LottoBooM.settings")
runpy.run_path(str(BASE_DIR / "scripts" / "cargar_matriz_sorteos.py"), run_name="__main__")
