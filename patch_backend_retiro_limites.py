from pathlib import Path
import ast

p = Path("/home/LottoBooM/roles/views.py")
src = p.read_text(encoding="utf-8")

if "def api_retiro_rapido" in src:
    print("SKIP: retiro ya existe")
else:
    endpoint_retiro = '''

# ═══════════════════════════════════════════════════════════════
# API · Retiro rápido (el gestor descuenta del fondo del cliente)
# Motivos: cobro de premios, donacion, ajuste, retiro presencial
# ═══════════════════════════════════════════════════════════════
@login_required
@require_POST
def api_retiro_rapido(request):
    """Descuenta del fondo del cliente. Crea MovimientoFondo(tipo='retiro')."""
    from decimal import Decimal, InvalidOperation
    from django.db.models import Sum as _Sum

    user = request.user
    es_superadmin = user.is_superuser or user.roles.filter(tipo='superadmin', activo=True).exists()
    es_banco = user.roles.filter(tipo='banco', activo=True).exists()
    es_comercial = user.roles.filter(tipo='comercial', activo=True).exists()
    if not (es_superadmin or es_banco or es_comercial):
        return JsonResponse({'success': False, 'error': 'Sin permisos'}, status=403)

    usuario_id = (request.POST.get('usuario_id') or '').strip()
    forma_pago_id = (request.POST.get('forma_pago_id') or '').strip()
    monto_str = (request.POST.get('monto') or '').strip()
    motivo_tipo = (request.POST.get('motivo_tipo') or 'cobro_premios').strip()
    motivo_detalle = (request.POST.get('motivo_detalle') or '').strip()[:200]

    if not usuario_id.isdigit() or not forma_pago_id.isdigit():
        return JsonResponse({'success': False, 'error': 'Datos invalidos'}, status=400)

    try:
        monto = Decimal(monto_str)
        if monto <= 0:
            raise ValueError()
    except Exception:
        return JsonResponse({'success': False, 'error': 'Monto invalido'}, status=400)

    try:
        cliente = User.objects.get(id=int(usuario_id), is_active=True)
        forma_pago = FormaPago.objects.get(id=int(forma_pago_id), activo=True)
    except (User.DoesNotExist, FormaPago.DoesNotExist):
        return JsonResponse({'success': False, 'error': 'No encontrado'}, status=404)

    # Motivo legible
    motivos_map = {
        'cobro_premios': 'Cobro de premios',
        'donacion_banco': 'Donacion al banco',
        'donacion_comercial': 'Donacion al comercial',
        'donacion_gestor': 'Donacion al gestor',
        'ajuste': 'Ajuste de fondo',
        'retiro_presencial': 'Retiro presencial',
        'otro': motivo_detalle or 'Otro',
    }
    motivo_legible = motivos_map.get(motivo_tipo, motivo_detalle or motivo_tipo)

    # Buscar fondo
    fondo = Fondo.objects.select_for_update().filter(
        usuario=cliente, forma_pago=forma_pago, activo=True
    ).first()
    if not es_superadmin:
        # Solo el gestor dueño del fondo
        if not fondo or fondo.asignado_por_id != user.id:
            return JsonResponse({'success': False, 'error': 'No tienes permiso sobre este fondo'}, status=403)

    if not fondo:
        return JsonResponse({'success': False, 'error': 'El cliente no tiene fondo en esa FP'}, status=400)
    if fondo.monto < monto:
        return JsonResponse({
            'success': False,
            'error': 'Saldo insuficiente. Disponible: $' + str(fondo.monto)
        }, status=400)

    from django.db import transaction
    with transaction.atomic():
        saldo_antes = fondo.monto
        fondo.monto -= monto
        fondo.save(update_fields=['monto', 'actualizado_en'])
        saldo_despues = fondo.monto

        MovimientoFondo.objects.create(
            emisor=user,
            receptor=cliente,
            forma_pago=forma_pago,
            monto=-monto,
            tipo='retiro',
            estado='confirmado',
            motivo=motivo_legible,
            nota='Retiro por ' + user.username,
            saldo_antes=saldo_antes,
            saldo_despues=saldo_despues,
            datos_transferencia={
                'retiro_rapido': True,
                'motivo_tipo': motivo_tipo,
                'motivo_detalle': motivo_detalle,
                'gestor': user.username,
                'gestor_id': user.id,
            },
        )

    try:
        crear_notificacion(
            usuario=cliente, tipo='pago',
            mensaje='Retiro de $' + str(monto) + ' en ' + forma_pago.nombre + '. Motivo: ' + motivo_legible,
            datos={
                'monto': float(monto),
                'forma_pago': forma_pago.nombre,
                'motivo': motivo_legible,
                'gestor': user.username,
                'saldo_antes': float(saldo_antes),
                'saldo_despues': float(saldo_despues),
            },
            prioridad='alta', categoria='financiera',
        )
    except Exception:
        pass

    return JsonResponse({
        'success': True,
        'message': 'Retiro de $' + str(monto) + ' realizado',
        'monto': float(monto),
        'motivo': motivo_legible,
        'saldo_antes': float(saldo_antes),
        'saldo_despues': float(saldo_despues),
        'forma_pago_nombre': forma_pago.nombre,
    })

'''

    # Insertar al final del archivo
    src += endpoint_retiro
    p.write_text(src, encoding="utf-8")
    print("OK: endpoint api_retiro_rapido agregado")


# ═══════════════════════════════════════════════════════════════
# Endpoint: límites y dosis del gestor por sorteo
# ═══════════════════════════════════════════════════════════════
if "def api_limites_gestor" in src:
    print("SKIP: limites ya existe")
else:
    endpoint_limites = '''

# ═══════════════════════════════════════════════════════════════
# API · Limites y dosis del gestor para un sorteo (read-only)
# ═══════════════════════════════════════════════════════════════
@login_required
def api_limites_gestor(request):
    """Devuelve limites + dosis + sobrelimites del gestor para un sorteo."""
    from roles.utils import get_pool_gestor, get_dosis_gestor, get_sobrelimite_gestor
    from jugadas.models import FormaJuego

    gestor_id = (request.GET.get('gestor_id') or '').strip()
    sorteo_id = (request.GET.get('sorteo_id') or '').strip()

    if not gestor_id.isdigit() or not sorteo_id.isdigit():
        return JsonResponse({'success': False, 'error': 'Faltan parametros'}, status=400)

    try:
        gestor = User.objects.get(id=int(gestor_id))
        sorteo = Sorteo.objects.get(id=int(sorteo_id))
    except (User.DoesNotExist, Sorteo.DoesNotExist):
        return JsonResponse({'success': False, 'error': 'No encontrado'}, status=404)

    # Formas de juego del sorteo
    formas_sorteo_nombres = [f.lower() for f in (sorteo.formas_juego or [])]
    formas = []
    for fj in FormaJuego.objects.filter(activo=True):
        if fj.nombre.lower() in formas_sorteo_nombres:
            formas.append(fj)

    resultado_formas = []
    for fj in formas:
        fila = {
            'forma': fj.nombre,
            'dosis': 0.0,
            'limite': 0.0,
            'sobrelimite': 0.0,
        }
        try:
            fila['dosis'] = float(get_dosis_gestor(gestor, sorteo, fj, None) or 0)
        except Exception:
            pass
        try:
            fila['sobrelimite'] = float(get_sobrelimite_gestor(gestor, sorteo, fj, None) or 0)
        except Exception:
            pass
        try:
            fila['limite'] = float(get_pool_gestor(gestor, sorteo, fj, None) or 0)
        except Exception:
            pass
        resultado_formas.append(fila)

    return JsonResponse({
        'success': True,
        'gestor': gestor.username,
        'sorteo': sorteo.nombre,
        'formas': resultado_formas,
    })

'''

    src += endpoint_limites
    p.write_text(src, encoding="utf-8")
    print("OK: endpoint api_limites_gestor agregado")

# Verificar sintaxis
try:
    ast.parse(src)
    print("OK: sintaxis views.py correcta")
except SyntaxError as e:
    print("ERROR sintaxis:", e)
    raise SystemExit(1)


# ═══════════════════════════════════════════════════════════════
# URLs
# ═══════════════════════════════════════════════════════════════
pu = Path("/home/LottoBooM/roles/urls.py")
srcurls = pu.read_text(encoding="utf-8")
import re

if "api_retiro_rapido" not in srcurls:
    m = re.search(r"urlpatterns\s*=\s*\[", srcurls)
    srcurls = srcurls[:m.end()] + "\n    path('api/retiro-rapido/', views.api_retiro_rapido, name='api_retiro_rapido')," + srcurls[m.end():]
    print("OK: URL api_retiro_rapido agregada")

if "api_limites_gestor" not in srcurls:
    m = re.search(r"urlpatterns\s*=\s*\[", srcurls)
    srcurls = srcurls[:m.end()] + "\n    path('api/limites-gestor/', views.api_limites_gestor, name='api_limites_gestor')," + srcurls[m.end():]
    print("OK: URL api_limites_gestor agregada")

pu.write_text(srcurls, encoding="utf-8")

try:
    ast.parse(srcurls)
    print("OK: sintaxis urls.py correcta")
except SyntaxError as e:
    print("ERROR sintaxis urls.py:", e)
    raise SystemExit(1)

print("\n✅ Script 1 completo")
