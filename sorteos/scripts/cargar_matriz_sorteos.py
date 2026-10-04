# scripts/cargar_matriz_sorteos.py
# Ejecutar con: python manage.py shell < scripts/cargar_matriz_sorteos.py

import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'LottoBooM.settings')
django.setup()

from decimal import Decimal
from django.db import transaction
from sorteos.models import Sorteo, SorteoFormaJuego, DosisBase
from jugadas.models import FormaJuego

# ============================================================
# 1. FORMAS DE JUEGO REQUERIDAS (15 en total)
# ============================================================
FORMAS_REQUERIDAS = [
    'Pick2', 'pick3', 'pick4', 'pick5', 'PF', 'fijo',
    'corrido1', 'corrido2', 'centena corrida1', 'centena corrida2',
    'VsPick2', 'vspf', 'pick2vspf', 'tripleta', 'posicion'
]

# ============================================================
# 2. VALORES POR FORMA DE JUEGO (DOSIS y LÍMITES)
# ============================================================
VALORES_POR_FORMA = {
    'Pick2': {'dosis': 80, 'limite': 2000},
    'pick3': {'dosis': 200, 'limite': 500},
    'pick4': {'dosis': 2000, 'limite': 1000},
    'pick5': {'dosis': 5000, 'limite': 5000},
    'PF': {'dosis': 80, 'limite': 2000},
    'fijo': {'dosis': 80, 'limite': 2000},
    'corrido1': {'dosis': 30, 'limite': 3000},
    'corrido2': {'dosis': 30, 'limite': 3000},
    'centena corrida1': {'dosis': 200, 'limite': 500},
    'centena corrida2': {'dosis': 200, 'limite': 500},
    'VsPick2': {'dosis': 1000, 'limite': 200},
    'vspf': {'dosis': 1000, 'limite': 200},
    'pick2vspf': {'dosis': 1000, 'limite': 200},
    'tripleta': {'dosis': 5000, 'limite': 100},
    'posicion': {'dosis': 80, 'limite': 1000},
}

# ============================================================
# 3. MATRIZ COMPLETA (solo donde hay "Si")
# ============================================================
MATRIZ = {
    'Anguila 8 AM': ['Fijo', 'Corridos', 'Tripleta','Parlet', 'Posicion','VS100'],
    'Anguila 9 AM': ['Fijo', 'Corridos', 'Tripleta','Parlet', 'Posicion','VS100'],
    'Haití 1': ['Fijo', 'Corridos', 'Tripleta','Parlet', 'Posicion','VS100'],
    'Anguila 10 AM': ['Fijo', 'Corridos', 'Tripleta','Parlet', 'Posicion','VS100'],
    'Tennessee 10:20 AM': ['Pick3', 'PF', 'Fijo', 'Corridos', 'Centenas corridas', 'Tripleta','Parlet', 'Posicion','VS100'],
    'Haití 2': ['Fijo', 'Corridos', 'Tripleta','Parlet', 'Posicion','VS100'],
    'Anguila 11 AM': ['Fijo', 'Corridos', 'Tripleta','Parlet', 'Posicion','VS100'],
    'Texas 11 AM': ['Pick3', 'PF', 'Fijo', 'Corridos', 'Centenas corridas', 'Tripleta','Parlet', 'Posicion','VS100'],
    'Haití 3': ['Fijo', 'Corridos', 'Tripleta','Parlet', 'Posicion','VS100'],
    'Lotedom': ['Fijo', 'Corridos', 'Tripleta','Parlet', 'Posicion','VS100'],
    'Quemaito': ['Fijo'],
    'Anguila 12 PM': ['Fijo', 'Corridos', 'Tripleta','Parlet', 'Posicion','VS100'],
    'Primera': ['Fijo', 'Corridos', 'Tripleta','Parlet', 'Posicion','VS100'],
    'Quinielón': ['Fijo'],
    'Suerte 12:30 PM': ['Fijo', 'Corridos', 'Tripleta','Parlet', 'Posicion','VS100'],
    'King Lottery 12:30 PM': ['Pick3', 'Pick4', 'PF', 'Fijo', 'Corridos', 'Centenas corridas', 'Tripleta','Parlet', 'Posicion','VS100'],
    'Georgia 12:30 PM': ['Pick3', 'Pick4', 'PF', 'Fijo', 'Corridos', 'Centenas corridas', 'Tripleta','Parlet', 'Posicion','VS100'],
    'Real 12:50 PM': ['Fijo', 'Corridos', 'Tripleta','Parlet', 'Posicion','VS100'],
    'New York Real 12:50 PM': ['PF', 'Fijo', 'Corridos', 'Centenas corridas', 'Tripleta','Parlet', 'Posicion','VS100'],
    'New Jersey 12:50 PM': ['Pick3', 'PF', 'Fijo', 'Corridos', 'Centenas corridas', 'Tripleta','Parlet', 'Posicion','VS100'],
    'Anguila 1 PM': ['Fijo', 'Corridos', 'Tripleta','Parlet', 'Posicion','VS100'],
    'Tennessee 1:20 PM': ['Pick3', 'PF', 'Fijo', 'Corridos', 'Centenas corridas', 'Tripleta','Parlet', 'Posicion','VS100'],
    'Texas 1:20 PM': ['Pick3', 'PF', 'Fijo', 'Corridos', 'Centenas corridas', 'Tripleta','Parlet', 'Posicion','VS100'],
    'Florida 1:35 PM': ['Pick2', 'VSPick2' 'Pick3', 'Pick4', 'Pick5', 'PF', 'Fijo', 'Corridos', 'Centenas corridas', 'VSPick2', 'VSpf', 'Pick2VSpf', 'Tripleta','Parlet', 'Posicion','VS100'],
    'Anguila 2 PM': ['Fijo', 'Corridos', 'Tripleta','Parlet', 'Posicion','VS100'],
    'Gana Más 2:30 PM': ['Fijo', 'Corridos', 'Tripleta','Parlet', 'Posicion','VS100'],
    'New York 2:30 PM': ['Pick3', 'PF', 'Fijo', 'Corridos', 'Centenas corridas', 'Tripleta','Parlet', 'Posicion','VS100'],
    'Anguila 3 PM': ['Fijo', 'Corridos', 'Tripleta','Parlet', 'Posicion','VS100'],
    'Anguila 4 PM': ['Fijo', 'Corridos', 'Tripleta','Parlet', 'Posicion','VS100'],
    'Anguila 5 PM': ['Fijo', 'Corridos', 'Tripleta','Parlet', 'Posicion','VS100'],
    'Haití 4': ['Pick3', 'Pick4', 'PF', 'Fijo', 'Corridos', 'Tripleta','Parlet', 'Posicion','VS100'],
    'Suerte 6 PM': ['Fijo', 'Corridos', 'Tripleta','Parlet', 'Posicion','VS100'],
    'Anguila 6 PM': ['Fijo', 'Corridos', 'Tripleta','Parlet', 'Posicion','VS100'],
    'Haití 5': ['Pick3', 'Pick4', 'PF', 'Fijo', 'Corridos', 'Tripleta','Parlet', 'Posicion','VS100'],
    'Anguila 7 PM': ['Fijo', 'Corridos', 'Tripleta','Parlet', 'Posicion','VS100'],
    'Primera 7 PM': ['Fijo', 'Corridos', 'Tripleta','Parlet', 'Posicion','VS100'],
    'Georgia 7 PM': ['Pick3', 'Pick4', 'Pick5', 'PF', 'Fijo', 'Corridos', 'Centenas corridas', 'VSPF', 'Tripleta','Parlet', 'Posicion','VS100'],
    'Texas 7 PM': ['Pick3', 'PF', 'Fijo', 'Corridos', 'Centenas corridas', 'Tripleta','Parlet', 'Posicion','VS100'],
    'Tennessee 7:20 PM': ['Pick3', 'PF', 'Fijo', 'Corridos', 'Centenas corridas', 'Tripleta','Parlet', 'Posicion','VS100'],
    'King Lottery 7:30 PM': ['Pick3', 'Pick4', 'Pick5', 'PF', 'Fijo', 'Corridos', 'Centenas corridas', 'VSpf', 'Tripleta','Parlet', 'Posicion','VS100'],
    'Haití 6': ['Pick3', 'Pick4', 'PF', 'Fijo', 'Corridos', 'Tripleta','Parlet', 'Posicion','VS100'],
    'Loteka 7:50 PM': ['Fijo', 'Corridos', 'Tripleta','Parlet', 'Posicion','VS100'],
    'Tok 3': ['Pick3', 'PF', 'Fijo', 'Corridos', 'Centenas corridas', 'VSpf', 'Tripleta','Parlet', 'Posicion','VS100'],
    'Anguila 8 PM': ['Fijo', 'Corridos', 'Tripleta','Parlet', 'Posicion','VS100'],
    'Nacional': ['Fijo', 'Corridos', 'Centenas corridas', 'Tripleta','Parlet', 'Posicion','VS100'],
    'Leidsa 8:55 PM': ['Fijo', 'Corridos', 'Tripleta','Parlet', 'Posicion','VS100'],
    'Pega 3+': ['Pick3', 'PF', 'Fijo', 'VS100'],
    'Anguila 9 PM': ['Fijo', 'Corridos', 'Tripleta','Parlet', 'Posicion','VS100'],
    'Florida 9:50 PM': ['Pick2', 'VSPick2' 'Pick3', 'Pick4', 'Pick5', 'PF', 'Fijo', 'Corridos', 'Centenas corridas', 'VSPick2', 'VSpf', 'Pick2VSpf', 'Tripleta','Parlet', 'Posicion','VS100'],
    'Anguila 10 PM': ['Fijo', 'Corridos', 'Tripleta','Parlet', 'Posicion','VS100'],
    'New York 10:30 PM': ['Pick3', 'PF', 'Fijo', 'Corridos', 'Centenas corridas', 'Tripleta','Parlet', 'Posicion','VS100'],
    'New Jersey 10:50 PM': ['Pick3', 'PF', 'Fijo', 'Corridos', 'Centenas corridas', 'Tripleta','Parlet', 'Posicion','VS100'],
    'Texas 11 PM': ['Pick3', 'PF', 'Fijo', 'Corridos', 'Centenas corridas', 'Tripleta','Parlet', 'Posicion','VS100'],
    'Georgia 11:40 PM': ['Pick3', 'PF', 'Fijo', 'Corridos', 'Centenas corridas', 'Tripleta','Parlet', 'Posicion','VS100'],
}

def run():
    print("=" * 70)
    print("🚀 CARGANDO MATRIZ DE SORTEOS, DOSIS Y LÍMITES BASE")
    print("=" * 70)

    # 1. Crear formas de juego que no existan
    print("\n📌 Verificando formas de juego...")
    forma_map = {}
    for nombre in FORMAS_REQUERIDAS:
        obj, created = FormaJuego.objects.get_or_create(
            nombre=nombre,
            defaults={'activo': True, 'descripcion': f'Forma de juego {nombre}'}
        )
        forma_map[nombre] = obj
        print(f"   {'✅ Creada' if created else '⏳ Ya existe'}: {nombre}")

    # 2. Procesar cada sorteo
    print("\n📌 Procesando sorteos...")
    total_sorteos = len(MATRIZ)
    procesados = 0
    errores = 0
    total_relaciones = 0

    for nombre_sorteo, formas_activas in MATRIZ.items():
        try:
            sorteo = Sorteo.objects.get(nombre=nombre_sorteo)
        except Sorteo.DoesNotExist:
            print(f"   ⚠️ Sorteo '{nombre_sorteo}' NO ENCONTRADO. Omite.")
            errores += 1
            continue

        with transaction.atomic():
            # Limpiar relaciones existentes para este sorteo (para evitar duplicados)
            SorteoFormaJuego.objects.filter(sorteo=sorteo).delete()
            DosisBase.objects.filter(sorteo=sorteo).delete()

            for nombre_forma in formas_activas:
                forma = forma_map.get(nombre_forma)
                if not forma:
                    print(f"      ⚠️ Forma '{nombre_forma}' no encontrada")
                    continue

                # Crear SorteoFormaJuego
                SorteoFormaJuego.objects.create(
                    sorteo=sorteo,
                    forma_juego=forma,
                    activo=True
                )
                total_relaciones += 1

                # Crear DosisBase (con dosis y límite)
                valores = VALORES_POR_FORMA.get(nombre_forma, {'dosis': 1.0, 'limite': 0})
                DosisBase.objects.create(
                    sorteo=sorteo,
                    forma_juego=forma,
                    dosis_por_peso=Decimal(str(valores['dosis'])),
                    limite_maximo=Decimal(str(valores['limite'])),  # ← NUEVO CAMPO
                    activo=True
                )

            procesados += 1
            print(f"   ✅ {procesados}/{total_sorteos}: {sorteo.nombre} ({len(formas_activas)} formas activas)")

    # 3. Resumen final
    print("\n" + "=" * 70)
    print("📊 RESUMEN FINAL")
    print("=" * 70)
    print(f"✅ Sorteos procesados: {procesados}")
    print(f"⚠️ Sorteos no encontrados: {errores}")
    print(f"🔗 Relaciones SorteoFormaJuego creadas: {total_relaciones}")
    print(f"💊 DosisBase creadas: {DosisBase.objects.count()}")
    print("\n✅ ¡CARGA COMPLETADA!")


if __name__ == "__main__":
    run()