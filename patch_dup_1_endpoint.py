from pathlib import Path

# ═══════════════════════════════════════════════════════════════
# PASO 1: Añadir endpoint a jugadas/views.py
# ═══════════════════════════════════════════════════════════════
p = Path("/home/LottoBooM/jugadas/views.py")
src = p.read_text(encoding="utf-8")

if "def api_check_duplicados" in src:
    print("PASO 1: SKIP (endpoint ya existe)")
else:
    endpoint = '''

# ═══════════════════════════════════════════════════════════════
# API · Check de duplicados (cliente + sorteo + fecha + numero + forma + monto + FP)
# ═══════════════════════════════════════════════════════════════
@login_required
@require_POST
def api_check_duplicados(request):
    """
    Recibe {items: [...], cliente_id, forma_pago_id, fecha_sorteo}.
    Devuelve lista de items que ya existen en BD para ese cliente+sorteo+fecha+FP.
    Un item es duplicado si coinciden: sorteo, numero, forma_juego, monto.
    """
    from decimal import Decimal, InvalidOperation
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError as e:
        return JsonResponse({'success': False, 'error': 'JSON invalido: ' + str(e)}, status=400)

    items = data.get('items') or []
    cliente_id = data.get('cliente_id')
    forma_pago_id = data.get('forma_pago_id')
    fecha_sorteo_str = data.get('fecha_sorteo')

    if not items or not cliente_id or not forma_pago_id or not fecha_sorteo_str:
        return JsonResponse({'success': True, 'duplicados': [], 'count': 0})

    try:
        cliente_id = int(cliente_id)
        forma_pago_id = int(forma_pago_id)
    except (ValueError, TypeError):
        return JsonResponse({'success': False, 'error': 'cliente_id/forma_pago_id invalidos'}, status=400)

    # Fecha
    try:
        from datetime import datetime as _dt
        fecha_sorteo = _dt.strptime(fecha_sorteo_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return JsonResponse({'success': False, 'error': 'fecha_sorteo invalida'}, status=400)

    # Mapeo tipo → forma_juego_id
    from jugadas.models import FormaJuego
    formas_map = {}
    for fj in FormaJuego.objects.filter(activo=True):
        formas_map[fj.nombre.lower()] = fj.id

    # Recolectar sorteos involucrados
    sorteo_ids = set()
    for it in items:
        sid = it.get('sorteo_id')
        if sid:
            try:
                sorteo_ids.add(int(sid))
            except (ValueError, TypeError):
                pass

    if not sorteo_ids:
        return JsonResponse({'success': True, 'duplicados': [], 'count': 0})

    # Traer existentes (solo los que importan)
    existentes = set()
    qs = Jugada.objects.filter(
        usuario_id=cliente_id,
        sorteo_id__in=sorteo_ids,
        fecha_sorteo=fecha_sorteo,
        forma_pago_id=forma_pago_id,
        estado__in=['confirmada', 'pendiente'],
    ).values_list('sorteo_id', 'numero', 'forma_juego_id', 'monto')

    for sid, num, fj_id, monto in qs:
        # Normalizar numero
        num_norm = str(num).strip().upper() if num is not None else ''
        # Normalizar monto a 2 decimales
        try:
            monto_norm = str(Decimal(str(monto)).quantize(Decimal('0.01')))
        except (InvalidOperation, ValueError, TypeError):
            monto_norm = str(monto)
        existentes.add((sid, num_norm, fj_id, monto_norm))

    # Comparar
    duplicados = []
    for it in items:
        tipo_norm = (it.get('tipo') or '').strip().lower()
        fj_id = formas_map.get(tipo_norm)
        if not fj_id:
            continue
        try:
            sid = int(it.get('sorteo_id') or 0)
        except (ValueError, TypeError):
            continue
        num_norm = str(it.get('numero', '')).strip().upper()
        try:
            monto_norm = str(Decimal(str(it.get('monto', 0))).quantize(Decimal('0.01')))
        except (InvalidOperation, ValueError, TypeError):
            monto_norm = str(it.get('monto', 0))

        key = (sid, num_norm, fj_id, monto_norm)
        if key in existentes:
            duplicados.append({
                'numero': it.get('numero'),
                'tipo': it.get('tipo'),
                'sorteo_id': sid,
                'monto': float(it.get('monto', 0)),
            })

    return JsonResponse({
        'success': True,
        'duplicados': duplicados,
        'count': len(duplicados),
    })

'''
    src = src + endpoint
    p.write_text(src, encoding="utf-8")
    print("PASO 1: OK (endpoint api_check_duplicados agregado)")

# Verificar sintaxis
import ast
try:
    ast.parse(src)
    print("OK: sintaxis correcta")
except SyntaxError as e:
    print(f"ERROR: sintaxis linea {e.lineno}: {e.msg}")
    raise SystemExit(1)

# ═══════════════════════════════════════════════════════════════
# PASO 2: Registrar URL
# ═══════════════════════════════════════════════════════════════
import re
pu = Path("/home/LottoBooM/jugadas/urls.py")
srcurls = pu.read_text(encoding="utf-8")

if "api_check_duplicados" in srcurls:
    print("PASO 2: SKIP (URL ya existe)")
else:
    m = re.search(r"urlpatterns\s*=\s*\[", srcurls)
    if not m:
        print("ERROR: no encontre urlpatterns")
        raise SystemExit(1)
    nueva_url = "\n    path('api/check-duplicados/', views.api_check_duplicados, name='api_check_duplicados'),"
    srcurls = srcurls[:m.end()] + nueva_url + srcurls[m.end():]
    pu.write_text(srcurls, encoding="utf-8")
    print("PASO 2: OK (URL registrada)")

try:
    ast.parse(srcurls)
    print("OK: sintaxis urls.py correcta")
except SyntaxError as e:
    print(f"ERROR urls.py: {e}")
    raise SystemExit(1)

print("\n✅ Patch 1 completo")

