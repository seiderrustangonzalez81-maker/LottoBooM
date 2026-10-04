from pathlib import Path
import re

VIEJO = "New York Real 12:50 PM"
NUEVO = "New Yol Real 12:50 PM"

# ══════════════════════════════════════════════════════════════
# 1. ACTUALIZAR BD
# ══════════════════════════════════════════════════════════════
print("═══ 1. BD ═══")
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "LottoBooM.settings")
import django
django.setup()

from sorteos.models import Sorteo

s = Sorteo.objects.filter(nombre=VIEJO).first()
if s:
    s.nombre = NUEVO
    s.save(update_fields=['nombre'])
    print(f"OK: BD · id={s.id} actualizado a '{NUEVO}'")
elif Sorteo.objects.filter(nombre=NUEVO).exists():
    print(f"SKIP: BD ya tiene '{NUEVO}'")
else:
    print(f"WARN: no encontré '{VIEJO}' en BD")

# ══════════════════════════════════════════════════════════════
# 2. ACTUALIZAR ARCHIVOS
# ══════════════════════════════════════════════════════════════
print("\n═══ 2. Archivos ═══")

archivos = [
    "/home/LottoBooM/sorteos/fixtures/sorteos.json",
    "/home/LottoBooM/sorteos/scripts/cargar_matriz_sorteos.py",
    "/home/LottoBooM/config_sorteos_formas.json",
    "/home/LottoBooM/cargar_sorteos.py",
    "/home/LottoBooM/cargar_sorteos_corregidos.py",
    "/home/LottoBooM/sorteos_formas.csv",
]

for ruta in archivos:
    p = Path(ruta)
    if not p.exists():
        print(f"  SKIP (no existe): {ruta}")
        continue
    src = p.read_text(encoding="utf-8")
    n = src.count(VIEJO)
    if n == 0:
        if NUEVO in src:
            print(f"  SKIP (ya aplicado): {ruta}")
        else:
            print(f"  SKIP (sin match): {ruta}")
        continue
    src = src.replace(VIEJO, NUEVO)
    p.write_text(src, encoding="utf-8")
    print(f"  OK: {n} reemplazo(s) en {ruta}")

# ══════════════════════════════════════════════════════════════
# 3. ACTUALIZAR es_dominicano EN jugadas/views.py
# ══════════════════════════════════════════════════════════════
print("\n═══ 3. es_dominicano (jugadas/views.py) ═══")

p_views = Path("/home/LottoBooM/jugadas/views.py")
src_views = p_views.read_text(encoding="utf-8")

if "'new yol'" in src_views:
    print("  SKIP: 'new yol' ya está en la lista")
else:
    # Agregar 'new yol' a la lista de dominicanos
    viejo_lista = "        'anguila', 'haiti', 'lotedom', 'primera', 'real', 'king',\n        'new york', 'new jersey', 'nacional', 'leidsa'"
    nuevo_lista = "        'anguila', 'haiti', 'lotedom', 'primera', 'real', 'king',\n        'new york', 'new yol', 'new jersey', 'nacional', 'leidsa'"
    if viejo_lista in src_views:
        src_views = src_views.replace(viejo_lista, nuevo_lista, 1)
        p_views.write_text(src_views, encoding="utf-8")
        print("  OK: 'new yol' agregado a la lista de dominicanos")
    else:
        # Buscar variantes
        patron = re.compile(r"('new york',\s*'new jersey')")
        m = patron.search(src_views)
        if m:
            src_views = src_views[:m.start()] + "'new york', 'new yol', 'new jersey'" + src_views[m.end():]
            p_views.write_text(src_views, encoding="utf-8")
            print("  OK: aplicado via regex")
        else:
            print("  WARN: no encontré la lista — revísala manualmente")

print("\n✅ Listo")
