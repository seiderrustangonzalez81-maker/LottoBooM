#!/usr/bin/env python3
# scripts/cargar_matriz_sorteos.py
import os
import sys

# Añadir el directorio base del proyecto al sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # /home/LottoBooM
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Configurar Django antes de importar cualquier modelo
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'LottoBooM.settings')

import django
django.setup()

from decimal import Decimal
from django.db import transaction
from django.db.models import Q
from sorteos.models import Sorteo, SorteoFormaJuego, DosisBase
from jugadas.models import FormaJuego

# Importar la matriz desde constants.py (ya actualizada con parlet)
from sorteos.constants import MATRIZ

# ============================================================
# 1. FORMAS DE JUEGO REQUERIDAS (incluir 'parlet')
# ============================================================
FORMAS_REQUERIDAS = [
    'Pick2', 'pick3', 'pick4', 'pick5', 'PF', 'fijo',
    'corrido1', 'corrido2', 'centena corrida1', 'centena corrida2',
    'VsPick2', 'vspf', 'pick2vspf', 'tripleta', 'posicion', 'parlet'
]

DOSIS_POR_DEFECTO = {
    'Pick2': 80,
    'pick3': 200,
    'pick4': 2000,
    'pick5': 5000,
    'PF': 80,
    'fijo': 80,
    'corrido1': 30,
    'corrido2': 30,
    'centena corrida1': 200,
    'centena corrida2': 200,
    'VsPick2': 1000,
    'vspf': 1000,
    'pick2vspf': 1000,
    'tripleta': 5000,
    'posicion': 80,
    'parlet': 80,   # Dosis por defecto para parlet
}

# ============================================================
# FUNCIONES AUXILIARES
# ============================================================
def normalize_name(name):
    if '|' in name:
        parts = name.split('|', 1)
        if len(parts) == 2:
            return parts[1].strip()
    return name.strip()

def find_sorteo(nombre_busqueda):
    nombre_limpio = nombre_busqueda
    if '|' in nombre_busqueda:
        nombre_limpio = nombre_busqueda.split('|', 1)[1].strip()
    try:
        return Sorteo.objects.get(nombre=nombre_limpio)
    except Sorteo.DoesNotExist:
        pass
    for s in Sorteo.objects.all():
        nombre_sorteo_limpio = s.nombre
        if '|' in s.nombre:
            nombre_sorteo_limpio = s.nombre.split('|', 1)[1].strip()
        if nombre_limpio.lower() == nombre_sorteo_limpio.lower():
            return s
        if nombre_limpio.lower() in nombre_sorteo_limpio.lower():
            return s
    return None

# ============================================================
# PROCESO PRINCIPAL
# ============================================================
def run():
    print("=" * 70)
    print("🚀 CARGANDO MATRIZ DE SORTEOS Y DOSIS BASE")
    print("=" * 70)

    print("\n📋 Sorteos existentes:")
    for s in Sorteo.objects.all().order_by('nombre'):
        print(f"   - '{s.nombre}'")

    print("\n📌 Verificando formas de juego...")
    forma_map = {}
    for nombre in FORMAS_REQUERIDAS:
        obj, created = FormaJuego.objects.get_or_create(
            nombre=nombre,
            defaults={'activo': True}
        )
        forma_map[nombre] = obj
        print(f"   {'✅ Creada' if created else '⏳ Ya existe'}: {nombre}")

    print("\n📌 Procesando sorteos...")
    total_sorteos = len(MATRIZ)
    procesados = 0
    errores = 0
    total_relaciones = 0
    total_dosis = 0
    no_encontrados = []

    for nombre_sorteo, formas_activas in MATRIZ.items():
        sorteo = find_sorteo(nombre_sorteo)
        if not sorteo:
            print(f"   ⚠️ Sorteo '{nombre_sorteo}' NO ENCONTRADO. Omite.")
            errores += 1
            no_encontrados.append(nombre_sorteo)
            continue

        with transaction.atomic():
            # Limpiar solo las relaciones de este sorteo
            SorteoFormaJuego.objects.filter(sorteo=sorteo).delete()
            DosisBase.objects.filter(sorteo=sorteo).delete()

            for nombre_forma in formas_activas:
                forma = forma_map.get(nombre_forma)
                if not forma:
                    print(f"      ⚠️ Forma '{nombre_forma}' no encontrada")
                    continue

                dosis_valor = DOSIS_POR_DEFECTO.get(nombre_forma, Decimal('1.0'))
                if dosis_valor <= 0:
                    dosis_valor = Decimal('1.0')

                # Crear relación
                SorteoFormaJuego.objects.get_or_create(
                    sorteo=sorteo,
                    forma_juego=forma,
                    defaults={'activo': True}
                )
                total_relaciones += 1

                # Crear DosisBase
                DosisBase.objects.get_or_create(
                    sorteo=sorteo,
                    forma_juego=forma,
                    defaults={'dosis_por_peso': Decimal(str(dosis_valor)), 'activo': True}
                )
                total_dosis += 1

            procesados += 1
            print(f"   ✅ {procesados}/{total_sorteos}: {sorteo.nombre} ({len(formas_activas)} formas activas)")

    print("\n" + "=" * 70)
    print("📊 RESUMEN FINAL")
    print("=" * 70)
    print(f"✅ Sorteos procesados: {procesados}")
    print(f"⚠️ Sorteos no encontrados: {errores}")
    if no_encontrados:
        print("   Nombres no encontrados:")
        for nom in no_encontrados:
            print(f"      - {nom}")
    print(f"🔗 Relaciones SorteoFormaJuego creadas: {total_relaciones}")
    print(f"💊 DosisBase creadas: {total_dosis}")
    print("\n✅ ¡CARGA COMPLETADA!")

if __name__ == "__main__":
    run()