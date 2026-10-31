# usuarios/api_views.py
"""
Endpoints AJAX para polling de estado en tiempo real.
PythonAnywhere Free: 1 worker, LocMemCache.
- heartbeat: 204, solo cache.set (ultra liviano)
- state: agregado, ETag + cache 5s + rate limit 4s
"""
import hashlib
import json
import logging

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.cache import cache
from django.db.models import Q, Sum
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt

from usuarios.cache_utils import (
    marcar_online, esta_online, mapa_online, contar_online,
    last_activity_cache, snapshot_sesiones,
)

logger = logging.getLogger(__name__)


def _rate_limited(user_id, scope, min_sg=4):
    key = f'rl:{user_id}:{scope}'
    if cache.get(key):
        return True
    cache.set(key, 1, timeout=min_sg)
    return False


@login_required
@csrf_exempt
@require_POST
def api_heartbeat(request):
    marcar_online(request.user)
    return HttpResponse(status=204)


@login_required
def api_state(request):
    user = request.user
    scope = (request.GET.get('scope') or 'global').strip()
    cliente_id = (request.GET.get('cliente_id') or '').strip()

    if _rate_limited(user.id, scope):
        cached = cache.get(f'state:last:{user.id}:{scope}:{cliente_id}')
        if cached:
            etag, payload = cached
            if request.headers.get('If-None-Match') == etag:
                return HttpResponse(status=304)
            resp = JsonResponse(payload)
            resp['ETag'] = etag
            return resp
        return JsonResponse({'success': False, 'error': 'rate_limited'}, status=429)

    cache_key = f'state:last:{user.id}:{scope}:{cliente_id}'
    cached = cache.get(cache_key)

    if cached:
        etag, payload = cached
    else:
        try:
            payload = _build_state(user, scope, cliente_id)
            payload['ts'] = timezone.now().isoformat()
            raw = json.dumps(payload, sort_keys=True, default=str)
            etag = hashlib.md5(raw.encode()).hexdigest()[:16]
            payload['etag'] = etag
            cache.set(cache_key, (etag, payload), timeout=5)
        except Exception as e:
            logger.exception(f'[api_state] scope={scope} uid={user.id}: {e}')
            return JsonResponse({'success': False, 'error': str(e)}, status=500)

    if request.headers.get('If-None-Match') == etag:
        return HttpResponse(status=304)

    resp = JsonResponse(payload)
    resp['ETag'] = etag
    resp['Cache-Control'] = 'private, max-age=0, must-revalidate'
    return resp


def _build_state(user, scope, cliente_id):
    if scope == 'global': return _state_global(user)
    if scope == 'lista-clientes': return _state_lista_clientes(user)
    if scope == 'recarga-directa': return _state_recarga_directa(user, cliente_id)
    if scope == 'apostar': return _state_apostar(user, cliente_id)
    if scope == 'paneles': return _state_paneles(user)
    return {'success': False, 'error': 'scope desconocido'}


def _state_global(user):
    """
    Contadores globales para el sidebar.
    Devuelve tanto usuarios únicos como sesiones activas (pestañas/dispositivos).
    """
    snap = snapshot_sesiones()
    total_users = User.objects.filter(is_active=True).count()
    return {
        'success': True,
        'online': snap['usuarios_unicos'],   # ← compat con código existente
        'sesiones': snap['sesiones'],         # ← NUEVO: pestañas/dispositivos
        'usuarios_unicos': snap['usuarios_unicos'],
        'total': total_users,
    }

def _state_lista_clientes(user):
    es_superadmin = user.is_superuser or user.roles.filter(tipo='superadmin', activo=True).exists()
    es_banco = user.roles.filter(tipo='banco', activo=True).exists()
    es_comercial = user.roles.filter(tipo='comercial', activo=True).exists()

    from roles.models import Fondo, Subordinacion

    if es_superadmin:
        qs_users = User.objects.filter(is_active=True)
    elif es_banco:
        comerciales_ids = list(Subordinacion.objects.filter(
            jefe=user, activo=True
        ).values_list('subordinado_id', flat=True))
        clientes_ids = list(Fondo.objects.filter(
            Q(asignado_por__in=comerciales_ids) | Q(asignado_por=user),
            activo=True
        ).values_list('usuario_id', flat=True).distinct())
        qs_users = User.objects.filter(Q(id__in=clientes_ids) | Q(id__in=comerciales_ids), is_active=True)
    elif es_comercial:
        clientes_ids = list(Fondo.objects.filter(
            asignado_por=user, activo=True
        ).values_list('usuario_id', flat=True).distinct())
        qs_users = User.objects.filter(id__in=clientes_ids, is_active=True)
    else:
        return {'success': False, 'error': 'sin permiso'}

    qs_agg = qs_users.annotate(
        total_fondo=Sum('fondos__monto', filter=Q(fondos__activo=True)),
    ).values('id', 'username', 'total_fondo')

    ids = [u['id'] for u in qs_agg]
    mapa = mapa_online(ids)

    clientes = []
    total_fondo_sum = 0.0
    online_n = 0
    for u in qs_agg:
        tf = float(u['total_fondo'] or 0)
        total_fondo_sum += tf
        on = mapa.get(u['id'], False)
        if on:
            online_n += 1
        clientes.append({
            'id': u['id'],
            'username': u['username'],
            'online': on,
            'total_fondo': round(tf, 2),
        })

    return {
        'success': True,
        'online': online_n,
        'total': len(clientes),
        'total_fondo': round(total_fondo_sum, 2),
        'clientes': clientes,
    }


def _state_recarga_directa(user, cliente_id):
    if not cliente_id or not cliente_id.isdigit():
        return {'success': False, 'error': 'falta cliente_id'}

    from roles.models import Fondo
    from pagos.models import FormaPago

    try:
        cliente = User.objects.get(id=int(cliente_id), is_active=True)
    except User.DoesNotExist:
        return {'success': False, 'error': 'cliente no encontrado'}

    from django.db.models import Sum as _Sum
    fondos = {}
    total = 0.0
    for fp in FormaPago.objects.filter(activo=True).order_by('nombre'):
        m = Fondo.objects.filter(
            usuario=cliente, forma_pago=fp, activo=True
        ).aggregate(t=_Sum('monto'))['t'] or 0
        m = float(m)
        if m != 0:
            fondos[fp.nombre] = round(m, 2)
            total += m

    online = esta_online(cliente.id)
    last_act = last_activity_cache(cliente.id)

    return {
        'success': True,
        'cliente_id': cliente.id,
        'username': cliente.username,
        'online': online,
        'last_activity': last_act.isoformat() if last_act else None,
        'fondos': fondos,
        'total_fondo': round(total, 2),
    }


def _state_apostar(user, cliente_id):
    if not cliente_id or not cliente_id.isdigit():
        return {'success': True, 'clientes': []}
    cid = int(cliente_id)
    return {'success': True, 'clientes': [{'id': cid, 'online': esta_online(cid)}]}


def _state_paneles(user):
    from roles.models import Rol
    bancos_ids = list(Rol.objects.filter(tipo='banco', activo=True).values_list('usuario_id', flat=True))
    comerciales_ids = list(Rol.objects.filter(tipo='comercial', activo=True).values_list('usuario_id', flat=True))
    clientes_ids = list(Rol.objects.filter(tipo='cliente', activo=True).values_list('usuario_id', flat=True))
    mb = mapa_online(bancos_ids)
    mc = mapa_online(comerciales_ids)
    mcl = mapa_online(clientes_ids)
    return {
        'success': True,
        'bancos': {'online': sum(1 for v in mb.values() if v), 'total': len(bancos_ids)},
        'comerciales': {'online': sum(1 for v in mc.values() if v), 'total': len(comerciales_ids)},
        'clientes': {'online': sum(1 for v in mcl.values() if v), 'total': len(clientes_ids)},
    }


@login_required
@csrf_exempt
@require_POST
def api_offline(request):
    """
    Borra la sesión/tab del índice activo. Best-effort al cerrar pestaña.
    """
    from usuarios.cache_utils import TAB_INDEX_KEY, TAB_KEY
    tid = request.POST.get('tab_id') or request.headers.get('X-Tab-Id')
    if tid:
        tid = str(tid)[:64]
        cache.delete(TAB_KEY.format(tid=tid))
        idx = cache.get(TAB_INDEX_KEY) or {}
        if isinstance(idx, dict):
            idx.pop(tid, None)
            cache.set(TAB_INDEX_KEY, idx, timeout=600)
    return HttpResponse(status=204)
