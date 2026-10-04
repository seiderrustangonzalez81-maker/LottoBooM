from pathlib import Path

p = Path("/home/LottoBooM/jugadas/views.py")
src = p.read_text(encoding="utf-8")

if "GUARD_POOL_BACKEND_V1" in src:
    print("SKIP: ya aplicado")
    raise SystemExit(0)

# ═══════════════════════════════════════════════════════════════
# 1) Helper _validar_pool_items — antes de _guardar_apuesta_impl
# ═══════════════════════════════════════════════════════════════
helper_code = '''

# ═══════════════════════════════════════════════════════════════
# GUARD_POOL_BACKEND_V1
# Réplica server-side de _getPoolYConsumido (frontend) + endpoint
# api_disponible_por_numero. Agrupa items por (sorteo, forma, numero),
# suma montos, y compara contra (pool - consumido).
# ═══════════════════════════════════════════════════════════════
def _norm_nombre_forma(s):
    """Normaliza nombre: lowercase + sin acentos."""
    import unicodedata
    s = (s or '').lower().strip()
    s = unicodedata.normalize('NFD', s)
    return ''.join(c for c in s if unicodedata.category(c) != 'Mn')


def _validar_pool_items(gestor, fecha, forma_pago, items, excluir_jugada_ids=None):
    """Devuelve lista de errores (vacía si todo OK).
    Cada error: {sorteo_id, forma, numero, pedido, disponible, falta}.
    """
    from jugadas.models import Jugada, FormaJuego, Sorteo
    from django.db.models import Sum

    excluir_jugada_ids = excluir_jugada_ids or []

    formas_map = {}
    for fj in FormaJuego.objects.filter(activo=True):
        formas_map[_norm_nombre_forma(fj.nombre)] = fj

    # Agrupar items por (sorteo_id, fj_id, numero) sumando montos
    grupos = {}
    for it in items:
        try:
            sid = int(it.get('sorteo_id') or 0)
        except (ValueError, TypeError):
            continue
        if not sid:
            continue
        tipo = _norm_nombre_forma(it.get('tipo', ''))
        fj = formas_map.get(tipo)
        if not fj:
            continue
        numero = str(it.get('numero', '')).strip().upper()
        if not numero:
            continue
        try:
            monto = float(it.get('monto', 0) or 0)
        except (ValueError, TypeError):
            monto = 0.0
        if monto <= 0:
            continue
        key = (sid, fj.id, numero)
        grupos[key] = grupos.get(key, 0.0) + monto

    if not grupos:
        return []

    pool_cache = {}
    def _pool(sorteo_id, fj):
        key = (sorteo_id, fj.id)
        if key not in pool_cache:
            try:
                sorteo = Sorteo.objects.get(id=sorteo_id)
                pool_cache[key] = float(get_pool_gestor(gestor, sorteo, fj, forma_pago))
            except Exception:
                pool_cache[key] = 0.0
        return pool_cache[key]

    errores = []
    for (sid, fj_id, numero), pedido in grupos.items():
        fj = FormaJuego.objects.filter(id=fj_id).first()
        if not fj:
            continue
        pool = _pool(sid, fj)
        if pool <= 0:
            continue  # sin pool configurado → no validar

        qs = Jugada.objects.filter(
            destinatario=gestor,
            sorteo_id=sid,
            forma_juego=fj,
            forma_pago=forma_pago,
            fecha_sorteo=fecha,
            numero=numero,
            estado__in=['confirmada', 'pendiente'],
        )
        if excluir_jugada_ids:
            qs = qs.exclude(id__in=excluir_jugada_ids)

        consumido = float(qs.aggregate(total=Sum('monto'))['total'] or 0)
        disponible = max(0.0, pool - consumido)

        if pedido > disponible + 0.001:
            errores.append({
                'sorteo_id': sid,
                'forma': fj.nombre,
                'numero': numero,
                'pedido': round(pedido, 2),
                'disponible': round(disponible, 2),
                'falta': round(pedido - disponible, 2),
            })

    return errores


'''

anchor_helper = "def _guardar_apuesta_impl(request):"
if anchor_helper not in src:
    print("ERROR: no encontré def _guardar_apuesta_impl")
    raise SystemExit(1)
src = src.replace(anchor_helper, helper_code + anchor_helper, 1)
print("OK 1: helper _validar_pool_items + _norm_nombre_forma insertados")


# ═══════════════════════════════════════════════════════════════
# 2) Guard — antes de with transaction.atomic()
# ═══════════════════════════════════════════════════════════════
anchor_guard = """                logger.warning('[dup check pre] ERROR: ' + str(_e))

        with transaction.atomic():"""

guard_code = """                logger.warning('[dup check pre] ERROR: ' + str(_e))

        # ═══ GUARD_POOL_BACKEND_V1 ═══
        try:
            if items_normales and destinatario and forma_pago:
                _excluir_jugada_ids = []
                if es_edicion_pura and jugada_id and str(jugada_id).isdigit():
                    _excluir_jugada_ids.append(int(jugada_id))
                _errores_pool = _validar_pool_items(
                    gestor=destinatario,
                    fecha=fecha_apuesta,
                    forma_pago=forma_pago,
                    items=items_normales,
                    excluir_jugada_ids=_excluir_jugada_ids,
                )
                if _errores_pool:
                    _msg = '\\u26d4 ' + str(len(_errores_pool)) + ' jugada(s) exceden el disponible del gestor'
                    _detalle = ' \\u00b7 '.join([
                        e['forma'] + ' ' + e['numero'] + ' (falta $' + str(e['falta']) + ')'
                        for e in _errores_pool[:5]
                    ])
                    return JsonResponse({
                        'success': False,
                        'message': _msg,
                        'detalle': _detalle,
                        'errores': _errores_pool,
                    }, status=400)
        except Exception as _ePool:
            # Fail-open: si la validación falla por bug interno,
            # permitimos pasar pero dejamos rastro en logs.
            logger.warning('[GUARD_POOL_BACKEND_V1] error interno: ' + str(_ePool))
        # ═══ FIN GUARD_POOL_BACKEND_V1 ═══

        with transaction.atomic():"""

if anchor_guard not in src:
    print("ERROR: no encontré el ancla del guard")
    print("Pégame: grep -n 'with transaction.atomic' jugadas/views.py")
    raise SystemExit(1)
src = src.replace(anchor_guard, guard_code, 1)
print("OK 2: GUARD_POOL_BACKEND_V1 insertado")

p.write_text(src, encoding="utf-8")

import ast
try:
    ast.parse(src)
    print("OK 3: sintaxis Python correcta")
except SyntaxError as e:
    print(f"ERROR: sintaxis rota: {e}")
    raise SystemExit(1)

print()
print("═══ Resumen ═══")
print("GUARD_POOL_BACKEND_V1 :", src.count("GUARD_POOL_BACKEND_V1"))
print("_validar_pool_items   :", src.count("_validar_pool_items"))
print("_norm_nombre_forma    :", src.count("_norm_nombre_forma"))
