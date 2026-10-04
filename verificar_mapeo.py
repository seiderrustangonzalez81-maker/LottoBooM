# -*- coding: utf-8 -*-
"""Verifica que cada FormaJuego en la BD se mapea correctamente desde su clave corta"""
from jugadas.models import FormaJuego

MAPEO_FJ = {
    'pick2': 'Pick 2',
    'pick3': 'Pick 3',
    'pick4': 'Pick 4',
    'pick5': 'Pick 5',
    'fijo': 'Fijo',
    'corridos': 'Corridos',
    'pf': 'PF',
    'vspf': 'VS PF',
    'vspick2': 'VS Pick2',
    'pick2vspf': 'Pick2 vs PF',
    'tripleta': 'Tripleta',
    'posicion': 'Posición',
    'centenas corridas': 'Centenas Corridas',
    'superparlet': 'Superparlet',
    'parlet': 'Parlet',
    'par frontal': 'Par frontal',
    'vs': 'VS',
    'vs100': 'VS100',
    'candado': 'Candado',
}

print("=" * 72)
print("VERIFICACIÓN MAPEO_FJ ↔ FormaJuego en BD")
print("=" * 72)

# Mapa nombre_lower → FormaJuego
fj_por_nombre = {fj.nombre.lower(): fj for fj in FormaJuego.objects.filter(activo=True)}

print(f"\n{'CLAVE':<22} {'MAPEO_FJ →':<25} {'BD ENCONTRADO':<25} {'OK'}")
print("-" * 80)

problemas = []
for clave, nombre_real in MAPEO_FJ.items():
    fj = fj_por_nombre.get(nombre_real.lower())
    ok = "✅" if fj else "❌"
    if not fj:
        problemas.append(clave)
    print(f"{clave:<22} {nombre_real:<25} {(fj.nombre if fj else 'NO EXISTE'):<25} {ok}")

# FormaJuego en BD sin clave en MAPEO_FJ
print(f"\n▸ FormaJuego en BD sin clave en MAPEO_FJ:")
todas_mapes = set(n.lower() for n in MAPEO_FJ.values())
for fj in FormaJuego.objects.filter(activo=True):
    if fj.nombre.lower() not in todas_mapes:
        print(f"  ⚠️  {fj.nombre} (id={fj.id})")

if problemas:
    print(f"\n❌ FALTAN en BD: {problemas}")
else:
    print(f"\n✅ Todas las claves mapean correctamente")
