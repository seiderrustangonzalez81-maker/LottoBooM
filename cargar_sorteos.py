# -*- coding: utf-8 -*-
"""Actualiza el catálogo de sorteos desde el fixture validado, sin borrar registros."""
import json
import os
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "LottoBooM.settings")

import django
django.setup()

from sorteos.models import Sorteo


BASE_DIR = Path(__file__).resolve().parent
FIXTURE_PATH = BASE_DIR / "sorteos" / "fixtures" / "sorteos.json"
CONFIG_PATH = BASE_DIR / "config_sorteos_formas.json"

with FIXTURE_PATH.open(encoding="utf-8") as archivo:
    fixture = json.load(archivo)
with CONFIG_PATH.open(encoding="utf-8") as archivo:
    formas_configuradas = json.load(archivo)

# Conciliar nombres antiguos usando exactamente el mismo mapa que el cargador.
# Si ya existe el nombre canónico, se desactiva el alias antiguo pero no se borra:
# las apuestas y resultados históricos conservan su FK al registro original.
from sorteos.management.commands.load_results import MAPEO_NOMBRES

nombres_canonicos = {
    registro.get("fields", {}).get("nombre")
    for registro in fixture
    if registro.get("fields", {}).get("nombre")
}
renombrados = 0
desactivados = 0

for nombre_anterior, nombre_nuevo in MAPEO_NOMBRES.items():
    if nombre_anterior in nombres_canonicos or nombre_nuevo not in nombres_canonicos:
        continue

    anterior = Sorteo.objects.filter(nombre=nombre_anterior).first()
    if not anterior:
        continue

    nuevo = Sorteo.objects.filter(nombre=nombre_nuevo).first()
    if nuevo and nuevo.pk != anterior.pk:
        if anterior.activo:
            anterior.activo = False
            anterior.save(update_fields=["activo"])
            desactivados += 1
    else:
        anterior.nombre = nombre_nuevo
        anterior.save(update_fields=["nombre"])
        renombrados += 1


actualizados = 0
creados = 0
omitidos = []

for registro in fixture:
    campos = registro.get("fields", {})
    nombre = campos.get("nombre")
    if not nombre or nombre not in formas_configuradas:
        if nombre:
            omitidos.append(nombre)
        continue

    defaults = {
        "activo": campos.get("activo", True),
        "horarios": campos.get("horarios") or {},
        "hora_salida": campos.get("hora_salida"),
        "minutos_cierre": campos.get("minutos_cierre", 10),
        "origen": campos.get("origen", "dominicano"),
    }
    _, creado = Sorteo.objects.update_or_create(
        nombre=nombre,
        defaults=defaults,
    )
    if creado:
        creados += 1
    else:
        actualizados += 1

print(f"Catálogo conciliado: {actualizados} actualizados, {creados} creados.")
print(f"Alias históricos: {renombrados} renombrados, {desactivados} desactivados (sin borrar registros).")
if omitidos:
    print("Sorteos del fixture no incluidos en la matriz de formas (no modificados):")
    for nombre in omitidos:
        print(f"  - {nombre}")
print(f"Total de sorteos en base de datos: {Sorteo.objects.count()}")
