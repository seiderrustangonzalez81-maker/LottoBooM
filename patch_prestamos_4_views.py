from pathlib import Path
import ast

# ── 4a. Agregar helper en roles/utils.py ──
p_utils = Path("/home/LottoBooM/roles/utils.py")
src_utils = p_utils.read_text(encoding="utf-8")

if "_es_cliente_frecuente" not in src_utils:
    marcador = "def _aplicar_ingreso_a_fondo("
    helper = '''def _es_cliente_frecuente(user, gestor):
    """
    FIX_PRESTAMO_V1: >=10 boletas ACTIVAS creadas en los últimos 7 días
    con ese gestor específico.
    """
    from datetime import timedelta
    from django.utils import timezone as _tz
    from jugadas.models import Boleta
    if not user or not gestor:
        return False
    corte = _tz.now() - timedelta(days=7)
    return Boleta.objects.filter(
        usuario=user,
        destinatario=gestor,
        estado='activa',
        creado_en__gte=corte,
    ).count() >= 10


def _gestores_comunes_frecuentes(user, otro_cliente):
    """Devuelve lista de gestores con los que ambos son frecuentes."""
    from jugadas.models import Boleta
    from django.db.models import Count, Q
    from django.utils import timezone as _tz
    from datetime import timedelta

    corte = _tz.now() - timedelta(days=7)
    gestores_user = set(
        Boleta.objects.filter(usuario=user, estado='activa', creado_en__gte=corte)
        .values_list('destinatario_id', flat=True)
    )
    gestores_otro = set(
        Boleta.objects.filter(usuario=otro_cliente, estado='activa', creado_en__gte=corte)
        .values_list('destinatario_id', flat=True)
    )
    comunes = gestores_user & gestores_otro
    resultado = []
    for gid in comunes:
        if Boleta.objects.filter(usuario=user, destinatario_id=gid, estado='activa', creado_en__gte=corte).count() >= 10 \\
           and Boleta.objects.filter(usuario=otro_cliente, destinatario_id=gid, estado='activa', creado_en__gte=corte).count() >= 10:
            resultado.append(gid)
    return resultado


'''
    src_utils = src_utils.replace(marcador, helper + marcador, 1)
    try:
        ast.parse(src_utils)
        p_utils.write_text(src_utils, encoding="utf-8")
        print("OK: helpers _es_cliente_frecuente y _gestores_comunes_frecuentes agregados")
    except SyntaxError as e:
        print(f"ERROR sintaxis utils: {e}")
        raise SystemExit(1)
else:
    print("SKIP: helpers ya existen")

# ── 4b. Agregar vistas al final de roles/views.py ──
p_views = Path("/home/LottoBooM/roles/views.py")
src_views = p_views.read_text(encoding="utf-8")

if "def mis_prestamos_view" in src_views:
    print("SKIP: vistas ya existen")
else:
    nuevas_vistas = '''

# ═══════════════════════════════════════════════════════════════
# FIX_PRESTAMO_V1: VISTAS DE PRÉSTAMOS ENTRE CLIENTES
# ═══════════════════════════════════════════════════════════════
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from roles.utils import _es_cliente_frecuente, _gestores_comunes_frecuentes


@login_required
def mis_prestamos_view(request):
    """Lista préstamos del cliente (dados y recibidos)."""
    from roles.models import Prestamo
    from jugadas.models import Boleta

    user = request.user
    es_cliente = user.roles.filter(tipo='cliente', activo=True).exists()

    # Marcar badge como visto
    try:
        perfil = user.perfil
        if not perfil.prestamo_badge_visto:
            perfil.prestamo_badge_visto = True
            perfil.save(update_fields=['prestamo_badge_visto'])
    except Exception:
        pass

    dados = Prestamo.objects.filter(prestamista=user).select_related(
        'solicitante', 'gestor', 'forma_pago'
    ).order_by('-fecha_solicitud')
    recibidos = Prestamo.objects.filter(solicitante=user).select_related(
        'prestamista', 'gestor', 'forma_pago'
    ).order_by('-fecha_solicitud')

    context = {
        'dados': dados,
        'recibidos': recibidos,
        'es_cliente': es_cliente,
    }
    return render(request, 'roles/mis_prestamos.html', context)


@login_required
def crear_prestamo_view(request):
    """Cliente A solicita un préstamo a cliente B."""
    from roles.models import Prestamo, Fondo
    from jugadas.models import Boleta
    from pagos.models import FormaPago

    user = request.user

    if not user.roles.filter(tipo='cliente', activo=True).exists():
        messages.error(request, "Solo los clientes pueden solicitar préstamos.")
        return redirect('publico:home')

    # Validar que el usuario sea frecuente con al menos 1 gestor
    corte = timezone.now() - __import__('datetime').timedelta(days=7)
    gestores_user = list(
        Boleta.objects.filter(usuario=user, estado='activa', creado_en__gte=corte)
        .values_list('destinatario_id', flat=True).distinct()
    )
    gestores_frecuentes = []
    for gid in gestores_user:
        from django.contrib.auth.models import User as _U
        g = _U.objects.filter(id=gid).first()
        if g and _es_cliente_frecuente(user, g):
            gestores_frecuentes.append(g)

    if not gestores_frecuentes:
        messages.warning(request, "Necesitas al menos 10 boletas activas en la última semana con un gestor para solicitar préstamos.")
        return redirect('publico:home')

    # Clientes potenciales: frecuentes con los mismos gestores
    candidatos = []
    for g in gestores_frecuentes:
        corte = timezone.now() - __import__('datetime').timedelta(days=7)
        from django.db.models import Count
        clientes_ids = list(
            Boleta.objects.filter(destinatario=g, estado='activa', creado_en__gte=corte)
            .exclude(usuario=user)
            .values('usuario_id')
            .annotate(n=Count('id'))
            .filter(n__gte=10)
            .values_list('usuario_id', flat=True)
        )
        from django.contrib.auth.models import User as _U
        for c in _U.objects.filter(id__in=clientes_ids, is_active=True):
            candidatos.append({
                'cliente': c,
                'gestor': g,
                'formas_pago': list(FormaPago.objects.filter(activo=True)),
            })

    if request.method == 'POST':
        prestamista_id = request.POST.get('prestamista_id')
        gestor_id = request.POST.get('gestor_id')
        forma_pago_id = request.POST.get('forma_pago_id')
        monto_str = request.POST.get('monto', '0')
        motivo = request.POST.get('motivo', '')

        from decimal import Decimal, InvalidOperation
        try:
            monto = Decimal(monto_str)
            if monto <= 0:
                raise ValueError("Monto debe ser > 0")
        except (InvalidOperation, ValueError):
            messages.error(request, "Monto inválido.")
            return redirect('roles:crear_prestamo')

        from django.contrib.auth.models import User as _U
        from pagos.models import FormaPago
        try:
            prestamista = _U.objects.get(id=prestamista_id, is_active=True)
            gestor = _U.objects.get(id=gestor_id, is_active=True)
            forma_pago = FormaPago.objects.get(id=forma_pago_id, activo=True)
        except Exception:
            messages.error(request, "Datos inválidos.")
            return redirect('roles:crear_prestamo')

        # Re-validar frecuencia de ambos con ese gestor
        if not _es_cliente_frecuente(user, gestor) or not _es_cliente_frecuente(prestamista, gestor):
            messages.error(request, "Ambos clientes deben ser frecuentes con ese gestor (10 boletas activas en la última semana).")
            return redirect('roles:crear_prestamo')

        prestamo = Prestamo.objects.create(
            solicitante=user,
            prestamista=prestamista,
            gestor=gestor,
            forma_pago=forma_pago,
            monto=monto,
            saldo_pendiente=monto,
            interes=0,
            motivo=motivo,
            estado='solicitado',
        )

        from roles.utils import _crear_notificacion
        _crear_notificacion(
            usuario=prestamista,
            tipo='prestamo',
            mensaje=f"📩 {user.username} te solicita un préstamo de ${monto} en {forma_pago.nombre}.",
            datos={'prestamo_id': prestamo.id, 'solicitante': user.username, 'monto': float(monto), 'url_detalle': '/roles/mis-prestamos/'},
            prioridad='alta', categoria='financiera',
        )
        messages.success(request, f"✅ Solicitud enviada a {prestamista.username}.")
        return redirect('roles:mis_prestamos')

    context = {
        'candidatos': candidatos,
    }
    return render(request, 'roles/solicitar_prestamo.html', context)


@login_required
def responder_prestamo_view(request, prestamo_id):
    """Prestamista B aprueba o rechaza."""
    from roles.models import Prestamo

    prestamo = get_object_or_404(Prestamo, id=prestamo_id, prestamista=request.user)

    if request.method == 'POST':
        accion = request.POST.get('accion')

        if accion == 'rechazar':
            prestamo.estado = 'rechazado'
            prestamo.save(update_fields=['estado'])
            from roles.utils import _crear_notificacion
            _crear_notificacion(
                usuario=prestamo.solicitante,
                tipo='prestamo',
                mensaje=f"❌ {request.user.username} rechazó tu solicitud de préstamo.",
                datos={'prestamo_id': prestamo.id, 'url_detalle': '/roles/mis-prestamos/'},
                prioridad='media', categoria='financiera',
            )
            messages.info(request, "Solicitud rechazada.")
            return redirect('roles:mis_prestamos')

        if accion == 'aprobar':
            ok, msg = prestamo.aprobar(aprobado_por=request.user)
            if ok:
                messages.success(request, msg)
            else:
                messages.error(request, msg)
            return redirect('roles:mis_prestamos')

    return render(request, 'roles/responder_prestamo.html', {'prestamo': prestamo})
'''

    src_views = src_views.rstrip() + "\n" + nuevas_vistas
    try:
        ast.parse(src_views)
        p_views.write_text(src_views, encoding="utf-8")
        print("OK: vistas agregadas")
    except SyntaxError as e:
        print(f"ERROR sintaxis views: {e}")
        raise SystemExit(1)

# ── 4c. Agregar URLs ──
p_urls = Path("/home/LottoBooM/roles/urls.py")
src_urls = p_urls.read_text(encoding="utf-8")

if "mis-prestamos" in src_urls:
    print("SKIP: URLs ya existen")
else:
    if "urlpatterns = [" not in src_urls:
        print("ERROR: no encontré urlpatterns")
        raise SystemExit(1)

    nuevas_urls = '''    path('mis-prestamos/', views.mis_prestamos_view, name='mis_prestamos'),
    path('prestamos/crear/', views.crear_prestamo_view, name='crear_prestamo'),
    path('prestamos/<int:prestamo_id>/responder/', views.responder_prestamo_view, name='responder_prestamo'),
'''
    idx = src_urls.find("urlpatterns = [")
    idx_fin = src_urls.find("]", idx)
    src_urls = src_urls[:idx_fin] + nuevas_urls + src_urls[idx_fin:]
    try:
        ast.parse(src_urls)
        p_urls.write_text(src_urls, encoding="utf-8")
        print("OK: URLs agregadas")
    except SyntaxError as e:
        print(f"ERROR sintaxis urls: {e}")
        raise SystemExit(1)
