import re
from pathlib import Path

p = Path("/home/LottoBooM/jugadas/views.py")
src = p.read_text(encoding="utf-8")
original = src

# ═══════════════════════════════════════════════════════════════
# PASO 1: Reemplazar el helper _jugada_duplicada por _boleta_duplicada
# ═══════════════════════════════════════════════════════════════
patron_helpers = re.compile(
    r"(# ═+\n# Helper · Detecta si una jugada ya existe en BD.*?)(?=\n# ═+\n# Helper · Consolidar tripletas|\n@login_required|\ndef _guardar_apuesta_impl)",
    re.DOTALL,
)

nuevo_helper = '''# ═══════════════════════════════════════════════════════════════
# Helper · Detecta si una BOLETA completa ya existe en BD
# Firma = (cliente, sorteo, fecha, forma_pago, sorted[(numero, forma_juego, monto)])
# ═══════════════════════════════════════════════════════════════
def _boleta_duplicada(cliente_id, forma_pago_id, fecha_sorteo, items):
    """
    Recibe los items NORMALIZADOS a guardar (con sorteo_id, tipo, numero, monto).
    Compara contra las Jugadas existentes del cliente en esa fecha + FP.
    Devuelve el listado de boletas que coinciden exactamente (firma completa).
    """
    from decimal import Decimal, InvalidOperation
    from collections import defaultdict

    if not items or not cliente_id or not forma_pago_id or not fecha_sorteo:
        return []

    # ─── Agrupar items por sorteo_id ───
    por_sorteo = defaultdict(list)
    for it in items:
        sid = it.get('sorteo_id')
        if not sid:
            continue
        try:
            num_norm = str(it.get('numero', '')).strip().upper()
            tipo_norm = str(it.get('tipo', '')).strip().lower()
            monto_dec = Decimal(str(it.get('monto', 0))).quantize(Decimal('0.01'))
        except (InvalidOperation, ValueError, TypeError):
            continue
        if not num_norm:
            continue
        por_sorteo[sid].append((num_norm, tipo_norm, str(monto_dec)))

    # ─── Para cada sorteo, buscar si ya existe una boleta con misma firma ───
    duplicados = []
    for sid, firma_nueva in por_sorteo.items():
        firma_nueva_set = set(firma_nueva)

        # Traer jugadas del cliente para ese sorteo + fecha + FP
        jugadas_existentes = Jugada.objects.filter(
            usuario_id=cliente_id,
            sorteo_id=sid,
            fecha_sorteo=fecha_sorteo,
            forma_pago_id=forma_pago_id,
            estado__in=['confirmada', 'pendiente'],
        ).values('numero', 'forma_juego__nombre', 'monto')

        firma_existente = set()
        for j in jugadas_existentes:
            num_norm = str(j['numero'] or '').strip().upper()
            tipo_norm = str(j['forma_juego__nombre'] or '').strip().lower()
            try:
                monto_norm = str(Decimal(str(j['monto'])).quantize(Decimal('0.01')))
            except (InvalidOperation, ValueError, TypeError):
                monto_norm = str(j['monto'])
            firma_existente.add((num_norm, tipo_norm, monto_norm))

        # Si son idénticas → duplicada
        if firma_nueva_set and firma_nueva_set == firma_existente:
            duplicados.append({'sorteo_id': sid, 'cantidad': len(firma_nueva_set)})

    return duplicados
'''

src_new, n = patron_helpers.subn(nuevo_helper + "\n", src, count=1)
if n == 0:
    print("WARN: no matcheo el bloque de helpers")
    # Intentar alternativa: buscar solo _jugada_duplicada
    patron_jd = re.compile(
        r"# ═+\n# Helper · Detecta si una jugada ya existe en BD.*?\n    \)\.exists\(\)\n",
        re.DOTALL,
    )
    src_new, n = patron_jd.subn(nuevo_helper, src, count=1)
    if n == 0:
        print("ERROR: no pude reemplazar el helper")
        raise SystemExit(1)

src = src_new
p.write_text(src, encoding="utf-8")
print("PASO 1: OK (helper _boleta_duplicada en su lugar)")

import ast
try:
    ast.parse(src)
except SyntaxError as e:
    print(f"ERROR sintaxis tras paso 1: {e}")
    p.write_text(original, encoding="utf-8")
    raise SystemExit(1)

# ═══════════════════════════════════════════════════════════════
# PASO 2: Quitar el check individual en items_normales
# ═══════════════════════════════════════════════════════════════
viejo_check_norm = """
                    # ═══ Check duplicados ═══
                    if _jugada_duplicada(cliente.id, sorteo.id, forma_juego.id, forma_pago.id, numero, monto_final, fecha_apuesta):
                        advertencias.append(
                            f'⚠️ {numero} ({forma_juego.nombre}) ${monto_final} en {sorteo.nombre} ya existe para este cliente. Se omitió.'
                        )
                        continue
"""

if viejo_check_norm in src:
    src = src.replace(viejo_check_norm, "", 1)
    p.write_text(src, encoding="utf-8")
    print("PASO 2: OK (check individual en items_normales eliminado)")
else:
    # Variante flexible
    patron_chk = re.compile(
        r"\n\s+# ═══ Check duplicados ═══\n\s+if _jugada_duplicada\(.*?\n\s+continue\n",
        re.DOTALL,
    )
    src_new, n = patron_chk.subn("", src, count=1)
    if n:
        src = src_new
        p.write_text(src, encoding="utf-8")
        print(f"PASO 2: OK (variante, {n} eliminado)")
    else:
        print("PASO 2: WARN (no encontre el check individual)")

# ═══════════════════════════════════════════════════════════════
# PASO 3: Quitar el check individual en items_super
# ═══════════════════════════════════════════════════════════════
patron_chk_sup = re.compile(
    r"\n\s+# ═══ Check duplicados \(superparlet\) ═══\n\s+if _jugada_duplicada\(.*?\n\s+continue\n",
    re.DOTALL,
)
src_new, n = patron_chk_sup.subn("", src, count=1)
if n:
    src = src_new
    p.write_text(src, encoding="utf-8")
    print(f"PASO 3: OK ({n} eliminado en superparlet)")
else:
    print("PASO 3: WARN (no encontre el check superparlet)")

# ═══════════════════════════════════════════════════════════════
# PASO 4: Insertar el check de boleta COMPLETA antes del pago
# ═══════════════════════════════════════════════════════════════
# El check va justo después de crear todas las jugadas (después del loop de items_super)
# y antes de la cascada de pago.
# Ancla: "ref_boleta = boleta.referencia" o el primer "monto_fondo_consumido = Decimal('0.00')"

viejo_pago = """            ref_boleta = boleta.referencia if boleta else f"#{jugadas_creadas[0].id}"

            monto_fondo_consumido = Decimal('0.00')"""

nuevo_pago = """            ref_boleta = boleta.referencia if boleta else f"#{jugadas_creadas[0].id}"

            # ═══════════════════════════════════════════════════════════
            # Check de BOLETA DUPLICADA (firma completa)
            # Solo aplica en modo NUEVO (no en editar/reenviar)
            # ═══════════════════════════════════════════════════════════
            if not es_edicion_boleta and not es_solo_editar and forma_pago:
                try:
                    _items_firma = []
                    for _j in jugadas_creadas:
                        _items_firma.append({
                            'sorteo_id': _j.sorteo_id,
                            'tipo': (_j.forma_juego.nombre if _j.forma_juego else '').lower(),
                            'numero': _j.numero,
                            'monto': float(_j.monto),
                        })
                    _dups = _boleta_duplicada(cliente.id, forma_pago.id, fecha_apuesta, _items_firma)
                    if _dups:
                        # Revertir: cancelar las jugadas creadas y salir
                        for _j in jugadas_creadas:
                            _j.estado = 'cancelada'
                            _j.save(update_fields=['estado'])
                        # Si la boleta es nueva (no reusada) borrarla
                        if boleta and boleta.jugadas.exclude(estado='cancelada').count() == 0:
                            pass  # dejarla pero sin jugadas
                        _sorteos_msg = ', '.join([str(d['sorteo_id']) for d in _dups])
                        return JsonResponse({
                            'success': False,
                            'message': '⚠️ Ya existe una boleta idéntica para este cliente/sorteo/fecha/forma de pago. Modifica números, montos o forma de pago para continuar.',
                            'advertencias': advertencias + [
                                f'Duplicado en sorteo(s) ID: {_sorteos_msg}'
                            ],
                        }, status=400)
                except Exception as _e:
                    logger.warning(f'[duplicado check] {_e}')

            monto_fondo_consumido = Decimal('0.00')"""

if "_boleta_duplicada(cliente.id" in src:
    print("PASO 4: SKIP (ya existe)")
elif viejo_pago in src:
    src = src.replace(viejo_pago, nuevo_pago, 1)
    p.write_text(src, encoding="utf-8")
    print("PASO 4: OK (check de boleta completa insertado)")
else:
    print("PASO 4: ERROR (no encontre el ancla 'ref_boleta = ...')")

# ═══════════════════════════════════════════════════════════════
# VERIFICACIÓN FINAL
# ═══════════════════════════════════════════════════════════════
try:
    ast.parse(src)
    print("\nOK: sintaxis final correcta")
except SyntaxError as e:
    print(f"\nERROR: {e.lineno}: {e.msg}")
    p.write_text(original, encoding="utf-8")
    print("REVERTIDO")
    raise SystemExit(1)

print(f"\n_jugada_duplicada restos: {src.count('_jugada_duplicada')}")
print(f"_boleta_duplicada: {src.count('_boleta_duplicada')}")
