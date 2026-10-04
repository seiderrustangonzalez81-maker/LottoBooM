from pathlib import Path
import ast

p = Path("/home/LottoBooM/jugadas/views.py")
src = p.read_text(encoding="utf-8")

if "_dentro_ventana_banco" in src:
    print("SKIP: ya aplicado")
    raise SystemExit(0)

# ═══════════════════════════════════════════════════════════════
# PASO 1: Añadir helper _dentro_ventana_banco
# ═══════════════════════════════════════════════════════════════
helper = '''

# ═══════════════════════════════════════════════════════════════
# Helper · ¿El banco aún puede insertar (dentro de 24h post-cierre)?
# ═══════════════════════════════════════════════════════════════
def _dentro_ventana_banco(estado_sorteo, ahora=None, horas=24):
    """
    Devuelve True si:
      - el sorteo tiene hora_cierre calculada, y
      - no han pasado más de `horas` desde ese cierre.
    Caso especial: si aún está abierto (hora_cierre futura) → True.
    """
    from datetime import timedelta
    if ahora is None:
        from django.utils import timezone as _tz
        ahora = _tz.now()
    hc = getattr(estado_sorteo, 'hora_cierre', None)
    if hc is None:
        return False
    # Si el cierre es futuro, obviamente puede
    if hc >= ahora:
        return True
    # Sino, verificar que no hayan pasado más de `horas` horas
    return (ahora - hc) <= timedelta(hours=horas)

'''

# Insertar antes de _guardar_apuesta_impl
anchor = "def _guardar_apuesta_impl(request):"
if anchor not in src:
    print("ERROR: no encontre _guardar_apuesta_impl")
    raise SystemExit(1)
src = src.replace(anchor, helper + "\n" + anchor, 1)
print("PASO 1: OK (helper _dentro_ventana_banco insertado)")

# ═══════════════════════════════════════════════════════════════
# PASO 2: Modificar check de items_normales (línea ~1342)
# ═══════════════════════════════════════════════════════════════
viejo_norm = """                    if not esta_abierto:
                        es_superadmin_ = usuario.is_superuser or usuario.roles.filter(tipo='superadmin', activo=True).exists()
                        es_banco_ = usuario.roles.filter(tipo='banco', activo=True).exists()
                        if not (es_superadmin_ or es_banco_):
                            advertencias.append(
                                f'El sorteo "{sorteo.nombre}" ya está cerrado. Solo banco o superadmin pueden cargar jugadas fuera de tiempo.'
                            )
                            continue"""

nuevo_norm = """                    if not esta_abierto:
                        es_superadmin_ = usuario.is_superuser or usuario.roles.filter(tipo='superadmin', activo=True).exists()
                        es_banco_ = usuario.roles.filter(tipo='banco', activo=True).exists()
                        # Superadmin: sin límite. Banco: solo dentro de 24h del cierre.
                        permitido = False
                        if es_superadmin_:
                            permitido = True
                        elif es_banco_:
                            permitido = _dentro_ventana_banco(estado_sorteo, timezone.now(), horas=24)
                        if not permitido:
                            advertencias.append(
                                f'El sorteo "{sorteo.nombre}" ya está cerrado y ha pasado más de 24h. Solo superadmin puede cargar jugadas fuera de tiempo.'
                            )
                            continue"""

if viejo_norm in src:
    src = src.replace(viejo_norm, nuevo_norm, 1)
    print("PASO 2: OK (check items_normales con ventana 24h)")
else:
    print("PASO 2: ERROR (no encontre el bloque en items_normales)")
    raise SystemExit(1)

# ═══════════════════════════════════════════════════════════════
# PASO 3: Modificar check de items_super (Superparlet)
# ═══════════════════════════════════════════════════════════════
viejo_sup = """                    if not esta_abierto:
                        es_superadmin_ = usuario.is_superuser or usuario.roles.filter(tipo='superadmin', activo=True).exists()
                        es_banco_ = usuario.roles.filter(tipo='banco', activo=True).exists()
                        if not (es_superadmin_ or es_banco_):
                            advertencias.append(
                                f'El sorteo "{sorteo_principal.nombre}" ya está cerrado. Solo banco o superadmin pueden cargar Superparlet fuera de tiempo.'
                            )
                            continue"""

nuevo_sup = """                    if not esta_abierto:
                        es_superadmin_ = usuario.is_superuser or usuario.roles.filter(tipo='superadmin', activo=True).exists()
                        es_banco_ = usuario.roles.filter(tipo='banco', activo=True).exists()
                        permitido = False
                        if es_superadmin_:
                            permitido = True
                        elif es_banco_:
                            permitido = _dentro_ventana_banco(estado_sorteo, timezone.now(), horas=24)
                        if not permitido:
                            advertencias.append(
                                f'El sorteo "{sorteo_principal.nombre}" ya está cerrado y ha pasado más de 24h. Solo superadmin puede cargar Superparlet fuera de tiempo.'
                            )
                            continue"""

if viejo_sup in src:
    src = src.replace(viejo_sup, nuevo_sup, 1)
    print("PASO 3: OK (check superparlet con ventana 24h)")
else:
    print("PASO 3: WARN (no encontre el bloque superparlet, puede que no aplique)")

p.write_text(src, encoding="utf-8")

try:
    ast.parse(src)
    print("OK: sintaxis correcta")
except SyntaxError as e:
    print("ERROR sintaxis:", e)
    raise SystemExit(1)

print("")
print("--- VERIFICACION ---")
print("_dentro_ventana_banco:", src.count("_dentro_ventana_banco"))
