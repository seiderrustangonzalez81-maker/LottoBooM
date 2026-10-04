from pathlib import Path
import re
import sys

# ═══════════════════════════════════════════════════════════════
# PARTE 1: Fusionar FormaJuego duplicadas (Fijo/fijo, etc.)
# ═══════════════════════════════════════════════════════════════
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'LottoBooM.settings')
sys.path.insert(0, '/home/LottoBooM')
django.setup()

from jugadas.models import FormaJuego, Jugada
from django.db.models import Count
from django.db.models.functions import Lower

print("═" * 60)
print("PARTE 1: Fusionar FormaJuego duplicadas (case-insensitive)")
print("═" * 60)

# Agrupar por nombre en minúsculas
grupos = {}
for fj in FormaJuego.objects.all().order_by('id'):
    key = fj.nombre.strip().lower()
    if key not in grupos:
        grupos[key] = []
    grupos[key].append(fj)

fusiones = 0
for key, lista in grupos.items():
    if len(lista) < 2:
        continue
    principal = lista[0]  # el más antiguo
    duplicados = lista[1:]
    print(f"\n  Grupo '{key}': principal=id={principal.id} '{principal.nombre}'")
    for dup in duplicados:
        # Contar jugadas usando el duplicado
        n_jugadas = Jugada.objects.filter(forma_juego=dup).count()
        print(f"    Fusionando id={dup.id} '{dup.nombre}' → id={principal.id} ({n_jugadas} jugadas)")
        # Reasignar
        Jugada.objects.filter(forma_juego=dup).update(forma_juego=principal)
        # Eliminar
        dup.delete()
        fusiones += 1

print(f"\n  Total fusiones: {fusiones}")

# ═══════════════════════════════════════════════════════════════
# PARTE 2: Mejorar logging del check
# ═══════════════════════════════════════════════════════════════
print("\n" + "═" * 60)
print("PARTE 2: Mejorar logging del check")
print("═" * 60)

p = Path("/home/LottoBooM/jugadas/views.py")
src = p.read_text(encoding="utf-8")
original = src

if "[dup check] firma nueva" in src:
    print("SKIP: logging ya presente")
else:
    viejo = """            if not es_edicion_boleta and not es_solo_editar and forma_pago:
                try:
                    _items_firma = []
                    for _j in jugadas_creadas:
                        _items_firma.append({
                            'sorteo_id': _j.sorteo_id,
                            'tipo': (_j.forma_juego.nombre if _j.forma_juego else '').lower(),
                            'numero': _j.numero,
                            'monto': float(_j.monto),
                        })
                    _dups = _boleta_duplicada(cliente.id, forma_pago.id, fecha_apuesta, _items_firma)"""

    nuevo = """            if not es_edicion_boleta and not es_solo_editar and forma_pago:
                try:
                    _items_firma = []
                    for _j in jugadas_creadas:
                        _items_firma.append({
                            'sorteo_id': _j.sorteo_id,
                            'tipo': (_j.forma_juego.nombre if _j.forma_juego else '').lower(),
                            'numero': _j.numero,
                            'monto': float(_j.monto),
                        })
                    logger.info(f'[dup check] cliente={cliente.id} fp={forma_pago.id} fecha={fecha_apuesta} items_firma={_items_firma}')
                    _dups = _boleta_duplicada(cliente.id, forma_pago.id, fecha_apuesta, _items_firma)
                    logger.info(f'[dup check] duplicados={_dups}')"""

    if viejo in src:
        src = src.replace(viejo, nuevo, 1)
        p.write_text(src, encoding="utf-8")
        print("  OK: logging insertado")
    else:
        print("  WARN: no encontre el bloque exacto")

# ═══════════════════════════════════════════════════════════════
# VERIFICACIÓN
# ═══════════════════════════════════════════════════════════════
import ast
try:
    ast.parse(src)
    print("\nOK: sintaxis correcta")
except SyntaxError as e:
    print(f"ERROR: {e}")
    p.write_text(original, encoding="utf-8")
    sys.exit(1)

# ═══════════════════════════════════════════════════════════════
# PARTE 3: Verificar el helper con datos reales
# ═══════════════════════════════════════════════════════════════
print("\n" + "═" * 60)
print("PARTE 3: Verificar el helper con datos reales")
print("═" * 60)

from django.contrib.auth.models import User
from datetime import date

# Crear una jugada de prueba
cli = User.objects.get(id=39)
dest = User.objects.get(id=3)
fj_fijo = FormaJuego.objects.filter(nombre__iexact='fijo').first()
from sorteos.models import Sorteo
from pagos.models import FormaPago
s = Sorteo.objects.get(id=1)
fp = FormaPago.objects.get(id=3)

# Crear
j, created = Jugada.objects.get_or_create(
    usuario=cli, sorteo=s, fecha_sorteo=date(2026, 10, 1),
    forma_juego=fj_fijo, forma_pago=fp, numero='99', monto=5,
    defaults={'destinatario': dest, 'estado': 'confirmada'}
)
print(f"  Jugada base: created={created}, id={j.id}, forma={j.forma_juego.nombre}, forma_id={j.forma_juego_id}")

# Ver qué trae la query
from jugadas.models import Jugada as J
existentes = J.objects.filter(
    usuario_id=39, sorteo_id=1, fecha_sorteo=date(2026,10,1),
    forma_pago_id=3, estado__in=['confirmada', 'pendiente']
).values('numero', 'forma_juego__nombre', 'monto')

print(f"  Existentes en BD: {list(existentes)}")

# Simular _boleta_duplicada
from decimal import Decimal
from collections import defaultdict

items_test = [{'sorteo_id': 1, 'tipo': 'fijo', 'numero': '99', 'monto': 5}]
por_sorteo = defaultdict(list)
for it in items_test:
    sid = it.get('sorteo_id')
    num_norm = str(it.get('numero', '')).strip().upper()
    tipo_norm = str(it.get('tipo', '')).strip().lower()
    monto_dec = Decimal(str(it.get('monto', 0))).quantize(Decimal('0.01'))
    por_sorteo[sid].append((num_norm, tipo_norm, str(monto_dec)))

print(f"  Firma nueva: {dict(por_sorteo)}")

for sid, firma_nueva in por_sorteo.items():
    firma_nueva_set = set(firma_nueva)
    jugadas_existentes = J.objects.filter(
        usuario_id=39, sorteo_id=sid, fecha_sorteo=date(2026,10,1),
        forma_pago_id=3, estado__in=['confirmada', 'pendiente'],
    ).values('numero', 'forma_juego__nombre', 'monto')
    firma_existente = set()
    for jx in jugadas_existentes:
        num_norm = str(jx['numero'] or '').strip().upper()
        tipo_norm = str(jx['forma_juego__nombre'] or '').strip().lower()
        monto_norm = str(Decimal(str(jx['monto'])).quantize(Decimal('0.01')))
        firma_existente.add((num_norm, tipo_norm, monto_norm))
    print(f"  Firma existente: {firma_existente}")
    print(f"  Match: {firma_nueva_set == firma_existente}")

# Limpiar
if created:
    j.delete()
    print("  Jugada base eliminada.")
