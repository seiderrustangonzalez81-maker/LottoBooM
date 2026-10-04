from pathlib import Path

p = Path("/home/LottoBooM/jugadas/views.py")
src = p.read_text(encoding="utf-8")

# ═══════════════════════════════════════════════════════════════
# PASO 1: Renombrar guardar_apuesta → _guardar_apuesta_impl
# ═══════════════════════════════════════════════════════════════
if "def _guardar_apuesta_impl(request):" in src:
    print("SKIP paso 1: ya renombrado")
else:
    viejo = "def guardar_apuesta(request):"
    if viejo not in src:
        print("ERROR paso 1: no encontre def guardar_apuesta")
        raise SystemExit(1)
    src = src.replace(viejo, "def _guardar_apuesta_impl(request):", 1)
    print("OK paso 1: renombrado a _guardar_apuesta_impl")

# ═══════════════════════════════════════════════════════════════
# PASO 2: Añadir preview al return final
# ═══════════════════════════════════════════════════════════════
if "'preview':" in src and "preview_jugadas" in src:
    print("SKIP paso 2: preview ya presente")
else:
    viejo_return = """        return JsonResponse({
            'success': True,
            'message': mensaje,
            'cantidad': len(jugadas_creadas),
            'boleta_id': boleta.id if boleta else None,
            'boleta_referencia': boleta.referencia if boleta else None,
            'advertencias': advertencias
        })"""

    nuevo_return = """        # Serializar jugadas para el preview (usado en dry_run)
        preview_jugadas = []
        for _j in jugadas_creadas:
            preview_jugadas.append({
                'numero': _j.numero,
                'forma_juego': _j.forma_juego.nombre if _j.forma_juego else '',
                'sorteo': _j.sorteo.nombre if _j.sorteo else '',
                'monto': float(_j.monto),
            })
        _items_originales = len(items_normales) + len(items_super)
        _descartadas = max(0, _items_originales - len(jugadas_creadas))

        return JsonResponse({
            'success': True,
            'message': mensaje,
            'cantidad': len(jugadas_creadas),
            'boleta_id': boleta.id if boleta else None,
            'boleta_referencia': boleta.referencia if boleta else None,
            'advertencias': advertencias,
            'preview': {
                'jugadas': preview_jugadas,
                'total': float(total_apostado),
                'descartadas': _descartadas,
                'items_originales': _items_originales,
            },
        })"""

    if viejo_return not in src:
        print("ERROR paso 2: no encontre el return final")
        print("Corre: grep -n \"'boleta_referencia': boleta.referencia\" jugadas/views.py")
        raise SystemExit(1)
    src = src.replace(viejo_return, nuevo_return, 1)
    print("OK paso 2: preview agregado al return")

# ═══════════════════════════════════════════════════════════════
# PASO 3: Añadir wrapper al final del archivo
# ═══════════════════════════════════════════════════════════════
if "def guardar_apuesta(request):" in src and "dry_run" in src:
    print("SKIP paso 3: wrapper ya presente")
else:
    wrapper = '''

# ═══════════════════════════════════════════════════════════════
# Wrapper: soporta dry_run para preview de apuesta
# ═══════════════════════════════════════════════════════════════
@login_required
@require_POST
def guardar_apuesta(request):
    """
    Si POST trae dry_run=true: ejecuta la logica completa en una
    transaccion que se REVIERTE al final. Devuelve el preview de lo
    que se guardaria, sin persistir nada.
    Si dry_run es falso: guarda normalmente.
    """
    from django.db import transaction

    dry_run = (request.POST.get('dry_run', '').lower() == 'true')

    if not dry_run:
        return _guardar_apuesta_impl(request)

    try:
        with transaction.atomic():
            response = _guardar_apuesta_impl(request)
            transaction.set_rollback(True)

            try:
                import json as _json
                data = _json.loads(response.content)
                data['dry_run'] = True
                data['boleta_id'] = None
                return JsonResponse(data, status=response.status_code)
            except Exception:
                return response
    except Exception as e:
        logger.exception(f"[dry_run preview] Error: {e}")
        return JsonResponse({
            'success': False,
            'message': f'Error en preview: {str(e)}'
        }, status=500)

'''
    src = src + wrapper
    print("OK paso 3: wrapper agregado al final")

p.write_text(src, encoding="utf-8")

# Verificar sintaxis
import ast
try:
    ast.parse(src)
    print("OK sintaxis")
except SyntaxError as e:
    print(f"ERROR sintaxis linea {e.lineno}: {e.msg}")
    raise SystemExit(1)
