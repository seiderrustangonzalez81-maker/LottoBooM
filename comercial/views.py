from decimal import Decimal
from datetime import datetime, timedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.db.models import Sum, Count, Q
from django.utils import timezone

from jugadas.models import Jugada
from roles.models import Subordinacion, Comision, Fondo, MovimientoFondo, Notificacion
from pagos.models import FormaPago


# ============================================================
# DECORADOR PARA COMERCIAL
# ============================================================
def comercial_required(view_func):
    """
    Decorador que verifica que el usuario autenticado tenga rol de comercial.
    """
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('usuarios:login')
        es_comercial = request.user.roles.filter(tipo='comercial', activo=True).exists()
        if not es_comercial:
            messages.error(request, "Acceso denegado. Se requieren permisos de comercial.")
            return redirect('publico:home')
        return view_func(request, *args, **kwargs)
    return wrapper


# ============================================================
# DASHBOARD DEL COMERCIAL
# ============================================================
@login_required
@comercial_required
def dashboard_comercial(request):
    user = request.user
    hoy = timezone.now().date()

    # Ventas de hoy
    ventas_hoy = Jugada.objects.filter(
        destinatario=user,
        fecha__date=hoy,
        estado__in=['confirmada', 'ganadora', 'perdedora']
    ).aggregate(total=Sum('monto'))['total'] or Decimal('0.00')

    jugadas_hoy = Jugada.objects.filter(
        destinatario=user,
        fecha__date=hoy
    ).count()

    # Últimas jugadas recibidas
    ultimas_jugadas = Jugada.objects.filter(
        destinatario=user
    ).select_related('usuario', 'sorteo', 'forma_juego').order_by('-fecha')[:10]

    # Bonos activos (si aplica)
    bonos_activos = Comision.objects.filter(comercial=user, activo=True).count()

    context = {
        'ventas_hoy': ventas_hoy,
        'jugadas_hoy': jugadas_hoy,
        'ultimas_jugadas': ultimas_jugadas,
        'bonos_activos': bonos_activos,
    }
    return render(request, 'comercial/dashboard_comercial.html', context)


# ============================================================
# RESUMEN DE VENTAS DEL COMERCIAL
# ============================================================
@login_required
@comercial_required
def resumen_ventas_comercial(request):
    user = request.user
    periodo = request.GET.get('periodo', 'mes')
    fecha_referencia = request.GET.get('fecha')

    # Calcular fechas según periodo
    hoy = timezone.now().date()
    if periodo == 'dia':
        fecha_inicio = hoy
        fecha_fin = hoy
    elif periodo == 'semana':
        fecha_inicio = hoy - timedelta(days=7)
        fecha_fin = hoy
    elif periodo == 'mes':
        fecha_inicio = hoy.replace(day=1)
        fecha_fin = hoy
    elif periodo == 'anio':
        fecha_inicio = hoy.replace(month=1, day=1)
        fecha_fin = hoy
    else:
        fecha_inicio = None
        fecha_fin = None

    # Filtrar jugadas
    jugadas = Jugada.objects.filter(
        destinatario=user,
        estado__in=['confirmada', 'ganadora', 'perdedora']
    )

    if fecha_inicio and fecha_fin:
        jugadas = jugadas.filter(fecha__date__gte=fecha_inicio, fecha__date__lte=fecha_fin)

    ventas_por_sorteo = jugadas.values('sorteo__nombre').annotate(
        total_ventas=Sum('monto'),
        total_premios=Sum('monto_premio'),
        cantidad=Count('id')
    ).order_by('-total_ventas')

    total_ventas = jugadas.aggregate(total=Sum('monto'))['total'] or Decimal('0.00')
    total_premios = jugadas.aggregate(total=Sum('monto_premio'))['total'] or Decimal('0.00')
    ganancia_neta = total_ventas - total_premios

    context = {
        'ventas_por_sorteo': ventas_por_sorteo,
        'total_ventas': total_ventas,
        'total_premios': total_premios,
        'ganancia_neta': ganancia_neta,
        'periodo': periodo,
        'fecha_referencia': fecha_referencia,
    }
    return render(request, 'comercial/resumen_ventas.html', context)


# ============================================================
# RECARGAR USUARIO (CLIENTE) POR PARTE DEL COMERCIAL
# ============================================================
@login_required
@comercial_required
def recargar_usuario(request):
    """
    Vista para que el comercial recargue fondos a sus clientes.
    """
    user = request.user

    # Clientes que tienen fondos asignados por este comercial
    # (o que le han asignado a él) y que están activos
    usuarios = User.objects.filter(
        fondos__asignado_por=user,
        is_active=True
    ).exclude(id=user.id).distinct().order_by('username')

    if request.method == 'POST':
        usuario_id = request.POST.get('usuario')
        forma_pago_id = request.POST.get('forma_pago')
        monto_str = request.POST.get('monto')

        # Validaciones
        if not usuario_id or not forma_pago_id or not monto_str:
            messages.error(request, "Todos los campos son obligatorios.")
            return redirect('comercial:recargar_usuario')

        try:
            usuario = User.objects.get(id=usuario_id, is_active=True)
        except User.DoesNotExist:
            messages.error(request, "Usuario no válido.")
            return redirect('comercial:recargar_usuario')

        # Verificar que el usuario tenga fondos asignados por este comercial
        if not Fondo.objects.filter(usuario=usuario, asignado_por=user, activo=True).exists():
            messages.error(request, "No tienes permiso para recargar a este usuario.")
            return redirect('comercial:recargar_usuario')

        try:
            forma_pago = FormaPago.objects.get(id=forma_pago_id, activo=True)
        except FormaPago.DoesNotExist:
            messages.error(request, "Forma de pago no válida.")
            return redirect('comercial:recargar_usuario')

        try:
            monto = Decimal(monto_str)
            if monto <= 0:
                raise ValueError("El monto debe ser mayor a 0")
        except (ValueError, TypeError):
            messages.error(request, "Monto inválido.")
            return redirect('comercial:recargar_usuario')

        # Realizar la recarga
        fondo, created = Fondo.objects.get_or_create(
            usuario=usuario,
            forma_pago=forma_pago,
            defaults={'monto': Decimal('0.00'), 'activo': True, 'asignado_por': user}
        )
        
        # FIX_ANTI_DUP_60S (2026-10-18): Evitar doble clic o recargas duplicadas en menos de 60s
        from roles.utils import verificar_recarga_duplicada
        _emisor = request.user
        if verificar_recarga_duplicada(_emisor, usuario, forma_pago, monto, segundos=60):
            messages.error(request, "⚠️ El sistema reconoció una entrada doble de recarga y solo procesó una. Debes esperar 1 minuto para realizar otra recarga idéntica.")
            return redirect(request.path)

        fondo.monto += monto
        fondo.save()

        # Registrar movimiento
        MovimientoFondo.objects.create(
            emisor=user,
            receptor=usuario,
            forma_pago=forma_pago,
            monto=monto,
            tipo='recarga',
            estado='confirmado',
            datos_transferencia={'recarga_por': user.username},
            nota=f"Recarga directa por {user.username}"
        )

        # Notificar al cliente y al comercial
        Notificacion.objects.create(
            usuario=usuario,
            tipo='recarga',
            mensaje=f"💰 Has recibido una recarga de ${monto} de {user.username}.",
            datos={'monto': float(monto), 'emisor': user.id},
            leido=False,
            prioridad='alta',
            categoria='financiera'
        )
        Notificacion.objects.create(
            usuario=user,
            tipo='recarga',
            mensaje=f"✅ Has recargado ${monto} a {usuario.username}.",
            datos={'monto': float(monto), 'receptor': usuario.id},
            leido=False,
            prioridad='media',
            categoria='financiera'
        )

        messages.success(request, f"✅ Se recargaron ${monto} a {usuario.username} correctamente.")
        return redirect('comercial:recargar_usuario')

    # GET: mostrar formulario
    formas_pago = FormaPago.objects.filter(activo=True)
    context = {
        'usuarios': usuarios,
        'formas_pago': formas_pago,
        'titulo': 'Recargar Cliente',
        'subtitulo': 'Selecciona el cliente, la forma de pago y el monto a recargar.',
    }
    # Usamos el mismo template que para superadmin/banco (puedes cambiarlo si quieres)
    return render(request, 'superadmin/recargar_usuario.html', context)




# Agrega estas funciones al final de comercial/views.py

@login_required
@comercial_required
def lista_clientes(request):
    """Lista de clientes asignados al comercial."""
    clientes = User.objects.filter(
        fondos__asignado_por=request.user,
        is_active=True
    ).distinct().order_by('username')
    return render(request, 'comercial/lista_clientes.html', {'clientes': clientes})


@login_required
@comercial_required
def historial_recargas(request):
    """Historial de recargas realizadas por el comercial."""
    recargas = MovimientoFondo.objects.filter(
        emisor=request.user,
        tipo='recarga'
    ).select_related('receptor', 'forma_pago').order_by('-fecha')
    return render(request, 'comercial/historial_recargas.html', {'recargas': recargas})


@login_required
@comercial_required
def mis_comisiones(request):
    """Vista para ver las comisiones del comercial."""
    comisiones = Comision.objects.filter(comercial=request.user).order_by('-periodo')
    return render(request, 'comercial/mis_comisiones.html', {'comisiones': comisiones})


@login_required
@comercial_required
def resumen_financiero(request):
    """Resumen financiero del comercial (ventas, comisiones, etc.)."""
    # Lógica para calcular ingresos, gastos, etc.
    return render(request, 'comercial/resumen_financiero.html', {})


@login_required
@comercial_required
def perfil_comercial(request):
    """Perfil del comercial."""
    return render(request, 'comercial/perfil.html', {'user': request.user})


@login_required
@comercial_required
def configuracion_comercial(request):
    """Configuración del comercial."""
    return render(request, 'comercial/configuracion.html', {})