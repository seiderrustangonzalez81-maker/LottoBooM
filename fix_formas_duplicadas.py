import os
import sys
sys.path.insert(0, '/home/LottoBooM')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'LottoBooM.settings')

import django
django.setup()

from jugadas.models import FormaJuego, Jugada
from roles.models import LimiteApuesta, DosisPago, NumeroRestringido
from django.db import transaction

print("=" * 60)
print("  FUSIONAR FormaJuego DUPLICADAS")
print("=" * 60)

# Pares a fusionar: (duplicado_id, canonical_id)
# canonical es el ORIGINAL (menor id)
PARES = [
    (39, 5),   # fijo → Fijo
    (41, 10),  # parlet → Parlet
    (40, 17),  # corridos → Corridos
]

with transaction.atomic():
    for dup_id, canon_id in PARES:
        dup = FormaJuego.objects.filter(id=dup_id).first()
        canon = FormaJuego.objects.filter(id=canon_id).first()
        
        if not dup:
            print(f"\n[SKIP] FormaJuego id={dup_id} no existe")
            continue
        if not canon:
            print(f"\n[ERR] Canonical id={canon_id} no existe — no puedo fusionar {dup.nombre}")
            continue
        
        print(f"\n═══ Fusionando '{dup.nombre}' (id={dup.id}) → '{canon.nombre}' (id={canon.id}) ═══")
        
        # 1. Jugadas
        n_jugadas = Jugada.objects.filter(forma_juego=dup).update(forma_juego=canon)
        print(f"  Jugadas reasignadas: {n_jugadas}")
        
        # 2. LimiteApuesta
        n_limites = LimiteApuesta.objects.filter(forma_juego=dup).update(forma_juego=canon)
        print(f"  LimiteApuesta reasignadas: {n_limites}")
        
        # 3. DosisPago
        n_dosis = DosisPago.objects.filter(forma_juego=dup).update(forma_juego=canon)
        print(f"  DosisPago reasignadas: {n_dosis}")
        
        # 4. NumeroRestringido
        n_restr = NumeroRestringido.objects.filter(forma_juego=dup).update(forma_juego=canon)
        print(f"  NumeroRestringido reasignadas: {n_restr}")
        
        # 5. Borrar el duplicado
        dup.delete()
        print(f"  ✅ '{dup.nombre}' (id={dup_id}) eliminado")

print("\n" + "=" * 60)
print("  VERIFICACIÓN")
print("=" * 60)

# Verificar que ya no hay duplicados
grupos = {}
for fj in FormaJuego.objects.all().order_by('id'):
    key = fj.nombre.strip().lower()
    grupos.setdefault(key, []).append(fj)

dups_restantes = 0
for key, lista in grupos.items():
    if len(lista) > 1:
        dups_restantes += 1
        print(f"  ⚠️ '{key}': {len(lista)} variantes")
        for fj in lista:
            print(f"    id={fj.id} '{fj.nombre}'")

if dups_restantes == 0:
    print("  ✅ NO hay más duplicados")
else:
    print(f"  ⚠️ Quedan {dups_restantes} grupos duplicados")

