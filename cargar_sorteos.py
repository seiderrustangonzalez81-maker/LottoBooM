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

# Renombrar únicamente si el nombre nuevo aún no existe. Nunca se borran
# sorteos ni se tocan las apuestas/resultados vinculados por FK.
for nombre_anterior, nombre_nuevo in (
    ("Loteka 7:50 PM", "Loteka 7:55 PM"),
    ("Real 12:50 PM", "Real 12:55 PM"),
):
    anterior = Sorteo.objects.filter(nombre=nombre_anterior).first()
    nuevo_existe = Sorteo.objects.filter(nombre=nombre_nuevo).exists()
    if anterior and not nuevo_existe:
        anterior.nombre = nombre_nuevo
        anterior.save(update_fields=["nombre"])

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
if omitidos:
    print("Sorteos del fixture no incluidos en la matriz de formas (no modificados):")
    for nombre in omitidos:
        print(f"  - {nombre}")
print(f"Total de sorteos en base de datos: {Sorteo.objects.count()}")
