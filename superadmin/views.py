from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.db import transaction
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import timedelta
from django.core.paginator import Paginator
from django.http import JsonResponse
from decimal import Decimal

from jugadas.models import Jugada, FormaJuego
from sorteos.models import Sorteo
from pagos.models import FormaPago
from roles.models import (
    Rol, Fondo, MovimientoFondo,
    Notificacion, LimiteApuesta, DosisPago
)
from roles.utils import verificar_bono_referido_disponible
from sorteos.utils import get_hora_cierre

# ============================================================
# FUNCIÓN HELPER PARA NOTIFICACIONES (UNIFICADA)
# ============================================================
def crear_notificacion(usuario, tipo, mensaje, datos=None, prioridad='media', categoria='general'):
    if not usuario:
        return
    Notificacion.objects.create(
        usuario=usuario,
        tipo=tipo,
        mensaje=mensaje,
        datos=datos or {},
        prioridad=prioridad,
        categoria=categoria,
        leido=False
    )


# ============================================================
# DECORADOR PARA SUPERADMIN
# ============================================================
def superadmin_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('usuarios:login')
        es_super = request.user.is_superuser or request.user.roles.filter(tipo='superadmin', activo=True).exists()
        if not es_super:
            messages.error(request, "Acceso denegado. Se requieren permisos de superadministrador.")
            return redirect('publico:home')
        return view_func(request, *args, **kwargs)
    return wrapper


# ============================================================
# DASHBOARD PRINCIPAL
# ============================================================
@login_required
@superadmin_required
def dashboard(request):
    hoy = timezone.now().date()
    ahora = timezone.now()

    total_usuarios = User.objects.filter(is_active=True).count()
    total_sorteos = Sorteo.objects.filter(activo=True).count()
    total_jugadas_hoy = Jugada.objects.filter(fecha__date=hoy).count()
    ventas_hoy = Jugada.objects.filter(fecha__date=hoy, estado='confirmada').aggregate(total=Sum('monto'))['total'] or 0
    total_ventas = Jugada.objects.filter(estado='confirmada').aggregate(total=Sum('monto'))['total'] or 0
    total_jugadas = Jugada.objects.count()
    notificaciones_pendientes = Notificacion.objects.filter(usuario=request.user, leido=False).count()

    ventas_diarias = []
    for i in range(7):
        fecha = hoy - timedelta(days=i)
        total = Jugada.objects.filter(
            estado='confirmada',
            fecha__date=fecha
        ).aggregate(total=Sum('monto'))['total'] or 0
        ventas_diarias.append({
            'fecha': fecha.strftime('%d/%m'),
            'total': float(total)
        })
    ventas_diarias.reverse()

    sorteos_abiertos = []
    for s in Sorteo.objects.filter(activo=True):
        cierre = get_hora_cierre(s)
        if cierre and cierre > ahora:
            sorteos_abiertos.append(s)

    ultimas_jugadas = Jugada.objects.select_related(
        'usuario', 'destinatario', 'sorteo', 'forma_juego', 'forma_pago'
    ).order_by('-fecha')[:10]

    clientes = User.objects.filter(roles__tipo='cliente', roles__activo=True).count()
    comerciales = User.objects.filter(roles__tipo='comercial', roles__activo=True).count()
    bancos = User.objects.filter(roles__tipo='banco', roles__activo=True).count()
    superadmins = User.objects.filter(roles__tipo='superadmin', roles__activo=True).count()

    tipos_juego = Jugada.objects.values('forma_juego__nombre').annotate(
        total=Count('id')
    ).order_by('-total')[:5]

    movimientos = MovimientoFondo.objects.select_related('emisor', 'receptor', 'forma_pago').order_by('-creado_en')[:10]

    context = {
        'total_usuarios': total_usuarios,
        'total_sorteos': total_sorteos,
        'total_jugadas_hoy': total_jugadas_hoy,
        'ventas_hoy': ventas_hoy,
        'total_ventas': total_ventas,
        'total_jugadas': total_jugadas,
        'notificaciones_pendientes': notificaciones_pendientes,
        'ventas_diarias': ventas_diarias,
        'sorteos_abiertos': sorteos_abiertos,
        'ultimas_jugadas': ultimas_jugadas,
        'clientes': clientes,
        'comerciales': comerciales,
        'bancos': bancos,
        'superadmins': superadmins,
        'tipos_juego': tipos_juego,
        'movimientos': movimientos,
    }
    return render(request, 'superadmin/dashboard.html', context)


# ============================================================
# GESTIÓN DE USUARIOS (CON FILTRO Y ACCIÓN DE ASCENDER)
# ============================================================
@login_required
@superadmin_required
def usuarios_list(request):
    query = request.GET.get('q', '')
    rol_filter = request.GET.get('rol', '')
    solo_ascendibles = request.GET.get('ascendibles', '')

    usuarios = User.objects.all().order_by('username')

    if query:
        usuarios = usuarios.filter(
            Q(username__icontains=query) | Q(email__icontains=query) |
            Q(first_name__icontains=query) | Q(last_name__icontains=query)
        )

    if rol_filter:
        usuarios = usuarios.filter(roles__tipo=rol_filter, roles__activo=True)

    if solo_ascendibles:
        superadmin_ids = User.objects.filter(
            Q(is_superuser=True) | Q(roles__tipo='superadmin', roles__activo=True)
        ).values_list('id', flat=True).distinct()
        usuarios = usuarios.exclude(id__in=superadmin_ids)

    for u in usuarios:
        rol = Rol.objects.filter(usuario=u, activo=True).first()
        u.rol_actual = rol.tipo if rol else 'cliente'
        u.saldo = sum(f.monto for f in Fondo.objects.filter(usuario=u, activo=True))
        u.es_ascendible = (
            not u.is_superuser and
            not u.roles.filter(tipo='superadmin', activo=True).exists() and
            u.id != request.user.id
        )

    paginator = Paginator(usuarios, 20)
    page = request.GET.get('page')
    usuarios_page = paginator.get_page(page)

    context = {
        'usuarios': usuarios_page,
        'query': query,
        'rol_filter': rol_filter,
        'solo_ascendibles': solo_ascendibles,
        'roles_opciones': Rol.TIPOS_ROL,
    }
    return render(request, 'superadmin/usuarios_list.html', context)


# ============================================================
# ASCENDER USUARIO A SUPERADMIN
# ============================================================
@login_required
@superadmin_required
def usuario_ascender(request, usuario_id):
    usuario = get_object_or_404(User, id=usuario_id)

    if usuario.id == request.user.id:
        messages.error(request, "No puedes ascenderte a ti mismo.")
        return redirect('superadmin:usuarios_list')

    if usuario.is_superuser or usuario.roles.filter(tipo='superadmin', activo=True).exists():
        messages.warning(request, f"El usuario {usuario.username} ya es superadmin.")
        return redirect('superadmin:usuarios_list')

    with transaction.atomic():
        Rol.objects.filter(usuario=usuario, activo=True).update(activo=False)
        Rol.objects.create(usuario=usuario, tipo='superadmin', activo=True)
        usuario.is_superuser = True
        usuario.save()

        crear_notificacion(
            usuario=usuario,
            tipo='info',
            mensaje=f"🎉 ¡Felicidades! Has sido ascendido a Superadministrador por {request.user.username}.",
            datos={
                'ascendido_por': request.user.username,
                'ascendido_por_id': request.user.id,
                'nuevo_rol': 'superadmin',
                'fecha': timezone.now().isoformat(),
                'url_detalle': '/superadmin/dashboard/'
            },
            prioridad='alta',
            categoria='seguridad'
        )

        crear_notificacion(
            usuario=request.user,
            tipo='info',
            mensaje=f"✅ Has ascendido a {usuario.username} a Superadministrador.",
            datos={
                'usuario_ascendido': usuario.username,
                'usuario_ascendido_id': usuario.id,
                'fecha': timezone.now().isoformat()
            },
            prioridad='media',
            categoria='seguridad'
        )

    messages.success(request, f"✅ Usuario {usuario.username} ascendido a Superadministrador exitosamente.")
    return redirect('superadmin:usuarios_list')


@login_required
@superadmin_required
def usuario_editar(request, usuario_id):
    usuario = get_object_or_404(User, id=usuario_id)
    if request.method == 'POST':
        rol_tipo = request.POST.get('rol')
        activo = request.POST.get('activo') == 'on'
        if rol_tipo:
            Rol.objects.filter(usuario=usuario, activo=True).update(activo=False)
            Rol.objects.create(usuario=usuario, tipo=rol_tipo, activo=True)
        usuario.is_active = activo
        usuario.save()

        messages.success(request, f"Usuario {usuario.username} actualizado correctamente.")
        return redirect('superadmin:usuarios_list')

    roles = Rol.TIPOS_ROL
    rol_actual = Rol.objects.filter(usuario=usuario, activo=True).first()
    context = {
        'usuario': usuario,
        'roles': roles,
        'rol_actual': rol_actual.tipo if rol_actual else 'cliente',
    }
    return render(request, 'superadmin/editar_usuario.html', context)


# ============================================================
# GESTIÓN DE SORTEOS
# ============================================================
@login_required
@superadmin_required
def sorteos_list(request):
    sorteos = Sorteo.objects.all().order_by('nombre')
    paginator = Paginator(sorteos, 20)
    page = request.GET.get('page')
    sorteos_page = paginator.get_page(page)
    context = {'sorteos': sorteos_page}
    return render(request, 'superadmin/sorteos_list.html', context)


@login_required
@superadmin_required
def sorteo_crear(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        activo = request.POST.get('activo') == 'on'
        horarios = {
            'invierno': {
                'lunes': request.POST.get('invierno_lunes', ''),
                'martes': request.POST.get('invierno_martes', ''),
                'miercoles': request.POST.get('invierno_miercoles', ''),
                'jueves': request.POST.get('invierno_jueves', ''),
                'viernes': request.POST.get('invierno_viernes', ''),
                'sabado': request.POST.get('invierno_sabado', ''),
                'domingo': request.POST.get('invierno_domingo', ''),
            },
            'verano': {
                'lunes': request.POST.get('verano_lunes', ''),
                'martes': request.POST.get('verano_martes', ''),
                'miercoles': request.POST.get('verano_miercoles', ''),
                'jueves': request.POST.get('verano_jueves', ''),
                'viernes': request.POST.get('verano_viernes', ''),
                'sabado': request.POST.get('verano_sabado', ''),
                'domingo': request.POST.get('verano_domingo', ''),
            }
        }
        sorteo = Sorteo(nombre=nombre, activo=activo, horarios=horarios)
        sorteo.save()
        messages.success(request, f"Sorteo {nombre} creado correctamente.")
        return redirect('superadmin:sorteos_list')
    context = {}
    return render(request, 'superadmin/editar_sorteo.html', context)


@login_required
@superadmin_required
def sorteo_editar(request, sorteo_id):
    sorteo = get_object_or_404(Sorteo, id=sorteo_id)
    if request.method == 'POST':
        sorteo.nombre = request.POST.get('nombre')
        sorteo.activo = request.POST.get('activo') == 'on'
        sorteo.horarios = {
            'invierno': {
                'lunes': request.POST.get('invierno_lunes', ''),
                'martes': request.POST.get('invierno_martes', ''),
                'miercoles': request.POST.get('invierno_miercoles', ''),
                'jueves': request.POST.get('invierno_jueves', ''),
                'viernes': request.POST.get('invierno_viernes', ''),
                'sabado': request.POST.get('invierno_sabado', ''),
                'domingo': request.POST.get('invierno_domingo', ''),
            },
            'verano': {
                'lunes': request.POST.get('verano_lunes', ''),
                'martes': request.POST.get('verano_martes', ''),
                'miercoles': request.POST.get('verano_miercoles', ''),
                'jueves': request.POST.get('verano_jueves', ''),
                'viernes': request.POST.get('verano_viernes', ''),
                'sabado': request.POST.get('verano_sabado', ''),
                'domingo': request.POST.get('verano_domingo', ''),
            }
        }
        sorteo.save()
        messages.success(request, f"Sorteo {sorteo.nombre} actualizado correctamente.")
        return redirect('superadmin:sorteos_list')
    context = {'sorteo': sorteo}
    return render(request, 'superadmin/editar_sorteo.html', context)


# ============================================================
# GESTIÓN DE JUGADAS
# ============================================================
@login_required
@superadmin_required
def jugadas_list(request):
    jugadas = Jugada.objects.select_related(
        'usuario', 'destinatario', 'sorteo', 'forma_juego', 'forma_pago'
    ).order_by('-fecha')

    estado = request.GET.get('estado')
    if estado:
        jugadas = jugadas.filter(estado=estado)

    sorteo_id = request.GET.get('sorteo')
    if sorteo_id:
        jugadas = jugadas.filter(sorteo_id=sorteo_id)

    usuario_id = request.GET.get('usuario')
    if usuario_id:
        jugadas = jugadas.filter(usuario_id=usuario_id)

    fecha_desde = request.GET.get('fecha_desde')
    fecha_hasta = request.GET.get('fecha_hasta')
    if fecha_desde:
        jugadas = jugadas.filter(fecha__date__gte=fecha_desde)
    if fecha_hasta:
        jugadas = jugadas.filter(fecha__date__lte=fecha_hasta)

    paginator = Paginator(jugadas, 30)
    page = request.GET.get('page')
    jugadas_page = paginator.get_page(page)

    context = {
        'jugadas': jugadas_page,
        'sorteos': Sorteo.objects.filter(activo=True),
        'estados': Jugada.ESTADOS,
        'usuarios': User.objects.all().order_by('username')[:100],
        'estado_seleccionado': estado,
        'sorteo_seleccionado': sorteo_id,
        'usuario_seleccionado': usuario_id,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
    }
    return render(request, 'superadmin/jugadas_list.html', context)


# ============================================================
# REPORTES
# ============================================================
@login_required
@superadmin_required
def reporte_ventas(request):
    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin = request.GET.get('fecha_fin')
    sorteo_id = request.GET.get('sorteo')
    forma_juego_id = request.GET.get('forma_juego')

    jugadas = Jugada.objects.filter(estado__in=['confirmada', 'ganadora', 'perdedora'])

    if fecha_inicio:
        jugadas = jugadas.filter(fecha__date__gte=fecha_inicio)
    if fecha_fin:
        jugadas = jugadas.filter(fecha__date__lte=fecha_fin)
    if sorteo_id:
        jugadas = jugadas.filter(sorteo_id=sorteo_id)
    if forma_juego_id:
        jugadas = jugadas.filter(forma_juego_id=forma_juego_id)

    ventas_por_dia = jugadas.extra({'dia': "date(fecha)"}).values('dia').annotate(
        total=Sum('monto'),
        cantidad=Count('id')
    ).order_by('dia')

    ventas_por_sorteo = jugadas.values('sorteo__nombre').annotate(
        total=Sum('monto'),
        cantidad=Count('id')
    ).order_by('-total')

    total_ventas = jugadas.aggregate(total=Sum('monto'))['total'] or 0
    total_jugadas = jugadas.count()
    total_premios = jugadas.aggregate(total=Sum('monto_premio'))['total'] or 0

    context = {
        'ventas_por_dia': ventas_por_dia,
        'ventas_por_sorteo': ventas_por_sorteo,
        'total_ventas': total_ventas,
        'total_jugadas': total_jugadas,
        'total_premios': total_premios,
        'sorteos': Sorteo.objects.filter(activo=True),
        'formas_juego': FormaJuego.objects.filter(activo=True),
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
        'sorteo_seleccionado': sorteo_id,
        'forma_juego_seleccionada': forma_juego_id,
    }
    return render(request, 'superadmin/reporte_ventas.html', context)


@login_required
@superadmin_required
def reporte_comisiones(request):
    comerciales = User.objects.filter(roles__tipo='comercial', roles__activo=True)
    data = []
    for c in comerciales:
        ventas = Jugada.objects.filter(destinatario=c, estado__in=['confirmada', 'ganadora', 'perdedora'])
        total_ventas = ventas.aggregate(total=Sum('monto'))['total'] or 0
        total_premios = ventas.aggregate(total=Sum('monto_premio'))['total'] or 0
        ganancia = total_ventas - total_premios
        comision = ganancia * Decimal('0.05')
        data.append({
            'comercial': c,
            'total_ventas': total_ventas,
            'total_premios': total_premios,
            'ganancia': ganancia,
            'comision': comision,
        })
    context = {'data': data}
    return render(request, 'superadmin/reporte_comisiones.html', context)


# ============================================================
# GESTIÓN DE DOSIS Y LÍMITES
# ============================================================
@login_required
@superadmin_required
def gestion_dosis(request):
    dosis_list = DosisPago.objects.select_related('banco', 'comercial', 'sorteo', 'forma_juego', 'forma_pago').all().order_by('-creado_en')
    context = {'dosis_list': dosis_list}
    return render(request, 'superadmin/gestion_dosis.html', context)


@login_required
@superadmin_required
def gestion_limites(request):
    limites = LimiteApuesta.objects.select_related('banco', 'comercial', 'sorteo', 'forma_juego', 'forma_pago').all().order_by('-creado_en')
    context = {'limites': limites}
    return render(request, 'superadmin/gestion_limites.html', context)


# ============================================================
# RECARGA DE USUARIO
# ============================================================
@login_required
@superadmin_required
def recargar_usuario(request):
    if request.method == 'POST':
        usuario_id = request.POST.get('usuario')
        forma_pago_id = request.POST.get('forma_pago')
        monto = request.POST.get('monto')

        try:
            usuario = User.objects.get(id=usuario_id)
            forma_pago = FormaPago.objects.get(id=forma_pago_id, activo=True)
            monto = Decimal(monto)
            if monto <= 0:
                messages.error(request, "El monto debe ser mayor a 0.")
                return redirect('superadmin:recargar_usuario')
        except (User.DoesNotExist, FormaPago.DoesNotExist, ValueError):
            messages.error(request, "Datos inválidos.")
            return redirect('superadmin:recargar_usuario')

        with transaction.atomic():
            fondo, created = Fondo.objects.get_or_create(
                usuario=usuario,
                forma_pago=forma_pago,
                defaults={'monto': 0, 'activo': True, 'asignado_por': request.user}
            )
            
        # FIX_ANTI_DUP_60S (2026-10-18): Evitar doble clic o recargas duplicadas en menos de 60s
        from roles.utils import verificar_recarga_duplicada
        _emisor = request.user
        if verificar_recarga_duplicada(_emisor, usuario, forma_pago, monto, segundos=60):
            messages.error(request, "⚠️ El sistema reconoció una entrada doble de recarga y solo procesó una. Debes esperar 1 minuto para realizar otra recarga idéntica.")
            return redirect(request.path)

            fondo.monto += monto
            fondo.save()

            MovimientoFondo.objects.create(
                emisor=request.user,
                receptor=usuario,
                forma_pago=forma_pago,
                monto=monto,
                tipo='recarga',
                estado='confirmado',
                datos_transferencia=f"Recarga directa por {request.user.username}",
                nota=f"Recarga de ${monto} a {usuario.username}"
            )

            datos_recarga = {
                'monto': float(monto),
                'forma_pago': forma_pago.nombre,
                'emisor': request.user.username,
                'emisor_id': request.user.id,
                'receptor': usuario.username,
                'receptor_id': usuario.id,
                'saldo_nuevo': float(fondo.monto),
                'fecha': timezone.now().isoformat(),
                'url_detalle': '/usuarios/solicitudes-pendientes/'
            }

            crear_notificacion(
                usuario=usuario,
                tipo='recarga',
                mensaje=f"💰 Has recibido una recarga de ${monto} de {request.user.username}.",
                datos={**datos_recarga, 'rol': 'cliente'},
                prioridad='alta',
                categoria='financiera'
            )

            crear_notificacion(
                usuario=request.user,
                tipo='recarga',
                mensaje=f"✅ Has recargado ${monto} a {usuario.username}.",
                datos={**datos_recarga, 'rol': 'superadmin'},
                prioridad='alta',
                categoria='financiera'
            )

            messages.success(request, f"✅ Se recargaron ${monto} a {usuario.username} correctamente.")
            return redirect('superadmin:recargar_usuario')

    usuarios = User.objects.filter(is_active=True).exclude(id=request.user.id).order_by('username')
    formas_pago = FormaPago.objects.filter(activo=True)

    context = {
        'usuarios': usuarios,
        'formas_pago': formas_pago,
        'titulo': 'Recargar Usuario',
        'subtitulo': 'Selecciona el usuario, la forma de pago y el monto a recargar.',
    }
    return render(request, 'superadmin/recargar_usuario.html', context)


# ============================================================
# CONSUMIR BONO POR REFERIDO
# ============================================================
@login_required
@superadmin_required
def consumir_bono_referido(request, usuario_id):
    usuario = get_object_or_404(User, id=usuario_id)

    bono = verificar_bono_referido_disponible(usuario)

    if not bono:
        messages.error(request, "Este usuario no tiene un bono por referido activo disponible.")
        return redirect('superadmin:usuarios_list')

    fondos = Fondo.objects.filter(usuario=usuario, activo=True)
    saldo_total = sum(f.monto for f in fondos)
    if saldo_total > 0:
        messages.error(request, f"El usuario tiene saldo disponible (${saldo_total}). Solo puede consumir el bono si el saldo es 0.")
        return redirect('superadmin:usuarios_list')

    if request.method == 'POST':
        success, msg = bono.consumir(aprobado_por=request.user, forma_pago_nombre='Tarjeta')
        if success:
            messages.success(request, msg)
        else:
            messages.error(request, msg)
        return redirect('superadmin:usuarios_list')

    context = {
        'usuario': usuario,
        'bono': bono,
    }
    return render(request, 'superadmin/consumir_bono_referido.html', context)


# ============================================================
# NOTIFICACIONES DE SUPERADMIN (API)
# ============================================================
@login_required
@superadmin_required
def api_notificaciones_count(request):
    count = Notificacion.objects.filter(usuario=request.user, leido=False).count()
    return JsonResponse({'count': count})


@login_required
@superadmin_required
def api_notificaciones_recientes(request):
    notis = Notificacion.objects.filter(usuario=request.user).order_by('-creado_en')[:20]
    data = {
        'notificaciones': [
            {
                'id': n.id,
                'tipo': n.tipo,
                'mensaje': n.mensaje,
                'leido': n.leido,
                'creado_en': n.creado_en.isoformat(),
                'datos': n.datos,
                'fecha': n.creado_en.strftime('%d/%m/%Y %H:%M')
            }
            for n in notis
        ]
    }
    return JsonResponse(data, safe=False)