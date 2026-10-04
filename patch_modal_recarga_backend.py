from pathlib import Path

p = Path("/home/LottoBooM/roles/views.py")
src = p.read_text(encoding="utf-8")

if "def api_recarga_rapida" in src:
    print("SKIP: endpoint ya existe")
    raise SystemExit(0)

# Añadir el endpoint al final del archivo
endpoint = '''

# ═══════════════════════════════════════════════════════════════
# API · Recarga rápida (AJAX desde apostar.html)
# ═══════════════════════════════════════════════════════════════
@login_required
@require_POST
def api_recarga_rapida(request):
    """
    Recarga rápida via AJAX desde el modal en apostar.html.
    Reutiliza _aplicar_ingreso_a_fondo.
    """
    user = request.user
    es_superadmin = user.is_superuser or user.roles.filter(tipo='superadmin', activo=True).exists()
    es_banco = user.roles.filter(tipo='banco', activo=True).exists()
    es_comercial = user.roles.filter(tipo='comercial', activo=True).exists()

    if not (es_superadmin or es_banco or es_comercial):
        return JsonResponse({'success': False, 'error': 'Sin permisos'}, status=403)

    usuario_id = (request.POST.get('usuario_id') or '').strip()
    forma_pago_id = (request.POST.get('forma_pago_id') or '').strip()
    monto_str = (request.POST.get('monto') or '').strip()

    if not usuario_id.isdigit() or not forma_pago_id.isdigit():
        return JsonResponse({'success': False, 'error': 'Datos invalidos'}, status=400)

    try:
        monto = Decimal(monto_str)
        if monto <= 0:
            raise ValueError()
    except Exception:
        return JsonResponse({'success': False, 'error': 'Monto invalido'}, status=400)

    try:
        usuario = User.objects.get(id=int(usuario_id), is_active=True)
        forma_pago = FormaPago.objects.get(id=int(forma_pago_id), activo=True)
    except (User.DoesNotExist, FormaPago.DoesNotExist):
        return JsonResponse({'success': False, 'error': 'No encontrado'}, status=404)

    try:
        from .utils import _aplicar_ingreso_a_fondo
        monto_neto, descontado = _aplicar_ingreso_a_fondo(
            cliente=usuario, gestor=user,
            forma_pago=forma_pago, monto=monto,
        )

        # Saldo actualizado
        from django.db.models import Sum as _Sum
        saldo_actual = Fondo.objects.filter(
            usuario=usuario, forma_pago=forma_pago, activo=True
        ).aggregate(t=_Sum('monto'))['t'] or 0

        # Notificacion al cliente
        msg = user.username + " te recargo $" + str(monto) + " en " + forma_pago.nombre
        if descontado > 0:
            msg += ". Postpago cubierto: $" + str(descontado)
        try:
            crear_notificacion(
                usuario=usuario, tipo='info', mensaje=msg,
                datos={'monto': float(monto), 'forma_pago': forma_pago.nombre},
                prioridad='alta', categoria='financiera',
            )
        except Exception:
            pass

        return JsonResponse({
            'success': True,
            'message': 'Recarga exitosa',
            'monto': float(monto),
            'postpago_descontado': float(descontado),
            'monto_neto': float(monto_neto),
            'saldo_actual': float(saldo_actual),
            'forma_pago_nombre': forma_pago.nombre,
        })
    except Exception as e:
        logger.exception(f'[api_recarga_rapida] Error: {e}')
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

'''

src = src + endpoint
p.write_text(src, encoding="utf-8")

import ast
ast.parse(src)
print("OK: endpoint api_recarga_rapida agregado")
