# usuarios/views.py
# -*- coding: utf-8 -*-
import logging
from datetime import timedelta
from decimal import Decimal

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout as auth_logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.db import transaction
from django.db.models import Sum, Q, Case, When
from django.http import JsonResponse
from django.utils import timezone
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

from jugadas.models import Jugada
from roles.models import (
    Fondo, Bono, MovimientoFondo, Notificacion, Subordinacion,
    Rol, Comision, SolicitudRecarga, RelacionClienteGestor,
)
from pagos.models import FormaPago
from resultados.models import Premio
from .forms import RegistroForm, LoginForm, EditarPerfilForm
from .models import Perfil
from .utils import (
    get_rol_usuario,
    calcular_fondo_comercial,
    validar_telefono_internacional,
)
from roles.utils import crear_notificacion

logger = logging.getLogger(__name__)


# ============================================================
# HELPERS: FECHAS
# ============================================================

def _parse_fecha(s):
    """Convierte 'YYYY-MM-DD' a date. Devuelve None si es inválido."""
    if not s:
        return None
    try:
        from datetime import datetime
        return datetime.strptime(s, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return None


# ============================================================
# HELPERS: GAMIFICACIÓN / STREAK
# ============================================================

def calcular_streak(user, dias=30):
    """
    Cuenta días consecutivos con actividad en los últimos `dias`.
    Usa la fecha de las últimas jugadas del usuario.
    """
    if not user or not user.is_authenticated:
        return 0

    hoy = timezone.now().date()
    limite = hoy - timedelta(days=dias)

    fechas = (
        Jugada.objects
        .filter(usuario=user, fecha__date__gte=limite)
        .dates('fecha', 'day')
    )
    set_fechas = set(fechas)

    if not set_fechas:
        return 0

    if hoy in set_fechas:
        cursor = hoy
    elif (hoy - timedelta(days=1)) in set_fechas:
        cursor = hoy - timedelta(days=1)
    else:
        return 0

    streak = 0
    while cursor in set_fechas:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def calcular_nivel(user):
    """50 jugadas = 1 nivel."""
    total = Jugada.objects.filter(usuario=user).count()
    nivel = max(1, total // 50 + 1)
    xp_en_nivel = total % 50
    puntos_siguiente = 50 - xp_en_nivel if xp_en_nivel > 0 else 50
    progreso = (xp_en_nivel / 50) * 100
    return {
        'nivel': nivel,
        'puntos_siguiente': puntos_siguiente,
        'progreso': round(progreso, 1),
    }


def calcular_sparkline(queryset, campo='monto', campo_fecha='creado_en', dias=7):
    """
    Genera la cadena SVG (0-100 ancho, 0-20 alto) para una sparkline.

    Args:
        queryset: QuerySet base (ej. Fondo.objects.filter(...))
        campo: nombre del campo numérico a sumar (default 'monto')
        campo_fecha: nombre del campo DateTimeField (default 'creado_en')
        dias: cuántos días mostrar
    """
    hoy = timezone.now().date()
    inicio = hoy - timedelta(days=dias - 1)

    filtro_fecha = f"{campo_fecha}__date__gte"
    agrupador = f"{campo_fecha}__date"

    try:
        mapa = (
            queryset
            .filter(**{filtro_fecha: inicio})
            .values(agrupador)
            .annotate(total=Sum(campo))
        )
    except Exception:
        return '0,10 100,10'

    por_dia = {row[agrupador]: float(row['total'] or 0) for row in mapa}

    valores = [por_dia.get(inicio + timedelta(days=i), 0) for i in range(dias)]
    maxv = max(valores) or 1

    puntos = []
    for i, v in enumerate(valores):
        x = (i / (dias - 1)) * 100
        y = 20 - (v / maxv) * 18
        puntos.append(f"{x:.0f},{y:.0f}")
    return ' '.join(puntos)


# ============================================================
# REDIRECCIÓN DASHBOARD
# ============================================================

@login_required
def redirect_dashboard(request):
    return redirect('publico:home')


# ============================================================
# AUTENTICACIÓN Y REGISTRO
# ============================================================

def registro_view(request):
    codigo_referido = request.GET.get('ref', None)
    referente = None
    if codigo_referido:
        try:
            referente = User.objects.get(username=codigo_referido)
        except User.DoesNotExist:
            messages.warning(request, "Código de referido no válido")

    if request.method == 'POST':
        form = RegistroForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    user = form.save(commit=False)
                    user.save()

                    perfil, _ = Perfil.objects.get_or_create(usuario=user)
                    perfil.telefono = form.cleaned_data.get('telefono', '')
                    if not perfil.codigo_referido:
                        perfil.codigo_referido = perfil.generar_codigo_referido()
                    if referente:
                        perfil.referido_por = referente
                    perfil.save()

                    Rol.objects.get_or_create(
                        usuario=user, tipo='cliente',
                        defaults={'fondo': 0, 'activo': True}
                    )

                    # FIX_REGISTRO_BONOS_V1: bono de registro con vencimiento 15d
                    _bono_reg = Bono.objects.create(
                        usuario=user, tipo='registro',
                        monto=50, saldo_restante=50, estado='activo',
                        metadata={'motivo': 'Bono de bienvenida'}
                    )
                    _bono_reg.activar(dias_vigencia=15)
                    crear_notificacion(
                        usuario=user, tipo='info',
                        mensaje=f"🎉 ¡Bienvenido {user.username}! Has recibido $50 de bono de bienvenida.",
                        datos={'usuario_id': user.id, 'bono_monto': 50}
                    )

                    if referente:
                        # FIX_REGISTRO_BONOS_V1: distinguir referente cliente vs gestor
                        _es_gestor = (
                            referente.is_superuser
                            or referente.roles.filter(
                                tipo__in=['superadmin','banco','comercial'],
                                activo=True
                            ).exists()
                        )
                        _tipo_bono = 'recomendacion_gestor' if _es_gestor else 'recomendacion_cliente'
                        _dias = None if _es_gestor else 15

                        _bono_rec = Bono.objects.create(
                            usuario=user, tipo=_tipo_bono,
                            monto=25, saldo_restante=25,
                            usuario_referente=referente, usuario_referido=user,
                            estado='pendiente',
                            apuestas_requeridas=20, monto_apostado_requerido=500,
                            metadata={'motivo': f'Recomendado por {referente.username}'}
                        )
                        if _dias is not None:
                            _bono_rec.activar(dias_vigencia=_dias)
                        crear_notificacion(
                            usuario=referente, tipo='info',
                            mensaje=f"🎁 {user.username} se registró usando tu código. Recibirás un bono cuando cumpla los requisitos.",
                            datos={'referido_id': user.id, 'referente': referente.username}
                        )
                        messages.success(
                            request,
                            f"🎉 ¡Bienvenido {user.username}! $50 de bienvenida + $25 por referido (condicionado)."
                        )
                    else:
                        messages.success(
                            request,
                            f"🎉 ¡Bienvenido {user.username}! Recibiste $50 de bono de bienvenida."
                        )

                    user.backend = 'django.contrib.auth.backends.ModelBackend'
                    login(request, user)
                    return redirect('publico:home')

            except Exception as e:
                logger.exception("Error en registro de usuario")
                messages.error(request, f"❌ Error al crear la cuenta: {str(e)}")
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"❌ {error}")
    else:
        form = RegistroForm()

    return render(request, 'usuarios/registro.html', {
        'form': form, 'referente': referente,
    })


def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            telefono = form.cleaned_data['telefono']
            password = form.cleaned_data['password']
            user = authenticate(request, username=username, password=password)
            if user is not None:
                perfil = getattr(user, 'perfil', None)
                if perfil:
                    tel_guardado = validar_telefono_internacional(perfil.telefono)
                    tel_ingresado = validar_telefono_internacional(telefono)
                    if tel_guardado == tel_ingresado:
                        user.backend = 'django.contrib.auth.backends.ModelBackend'
                        login(request, user)
                        messages.success(request, f"✅ ¡Bienvenido {user.username}!")
                        return redirect('publico:home')
                    messages.error(request, "❌ El teléfono no coincide con el usuario")
                else:
                    messages.error(request, "❌ No tienes un perfil asociado a tu cuenta")
            else:
                # FIX_LOGIN_SUSCRIPCION_V1: mensaje diferenciado para inactivos
                try:
                    from django.contrib.auth.models import User as _User
                    _u = _User.objects.get(username=username)
                    if not _u.is_active:
                        # Es banco? (tiene suscripción)
                        _es_banco = _u.roles.filter(tipo='banco').exists()
                        _es_comercial = _u.roles.filter(tipo='comercial').exists()
                        if _es_banco:
                            messages.error(
                                request,
                                "❌ Tu cuenta está inactiva por vencimiento de suscripción. "
                                "Contacta al Superadmin para reactivarla."
                            )
                        elif _es_comercial:
                            messages.error(
                                request,
                                "❌ Tu cuenta está inactiva. "
                                "Contacta con tu banco para conocer las razones."
                            )
                        else:
                            messages.error(
                                request,
                                "❌ Tu cuenta está inactiva. Contacta al soporte."
                            )
                    else:
                        messages.error(request, "❌ Usuario o contraseña incorrectos")
                except _User.DoesNotExist:
                    messages.error(request, "❌ Usuario o contraseña incorrectos")
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"❌ {error}")
    else:
        form = LoginForm()

    return render(request, 'usuarios/login.html', {'form': form})


def logout_view(request):
    auth_logout(request)
    messages.success(request, "✅ Has cerrado sesión exitosamente")
    return redirect('publico:home')


# ============================================================
# PERFIL Y EDICIÓN
# ============================================================

@login_required
def perfil_cliente(request):
    user = request.user
    user.refresh_from_db()

    rol_obj = user.roles.filter(activo=True).first()
    rol_usuario = rol_obj.tipo if rol_obj else ('superadmin' if user.is_superuser else 'cliente')
    es_gestor = rol_usuario in ['comercial', 'banco', 'superadmin'] or user.is_superuser
    es_auditor = user.roles.filter(tipo='auditor', activo=True).exists()

    codigo_referido = user.username
    link_referido = f"{request.build_absolute_uri('/usuarios/registro/')}?ref={codigo_referido}"

    bonos = Bono.objects.filter(usuario=user)
    total_bonos = sum(b.saldo_restante for b in bonos if b.estado == 'activo')

    fondos = Fondo.objects.filter(usuario=user, activo=True).select_related('forma_pago')
    saldo_total = sum(f.monto for f in fondos)

    jugadas_qs = Jugada.objects.filter(usuario=user)
    total_jugadas = jugadas_qs.count()
    ultimas_jugadas = jugadas_qs.select_related('sorteo').order_by('-fecha')[:5]

    # ---------- Estadísticas por rol ----------
    clientes_asignados = 0
    ventas_totales = 0
    comisiones = 0

    if es_gestor:
        if rol_usuario == 'comercial':
            clientes_ids = (
                Fondo.objects
                .filter(asignado_por=user, activo=True)
                .values_list('usuario_id', flat=True)
                .distinct()
            )
            clientes_asignados = clientes_ids.count()
            ventas_totales = (
                Jugada.objects
                .filter(usuario__in=clientes_ids,
                        estado__in=['confirmada', 'ganadora', 'perdedora'])
                .aggregate(total=Sum('monto'))['total'] or 0
            )
            comision_obj = Comision.objects.filter(comercial=user, activo=True).first()
            porcentaje_comision = comision_obj.porcentaje if comision_obj else 0
            comisiones = (ventas_totales * porcentaje_comision) / 100 if porcentaje_comision else 0

        elif rol_usuario == 'banco':
            comerciales_ids = (
                Subordinacion.objects
                .filter(jefe=user, activo=True)
                .values_list('subordinado_id', flat=True)
            )
            clientes_ids = (
                Fondo.objects
                .filter(asignado_por__in=comerciales_ids, activo=True)
                .values_list('usuario_id', flat=True)
                .distinct()
            )
            clientes_asignados = clientes_ids.count()
            ventas_totales = (
                Jugada.objects
                .filter(usuario__in=clientes_ids,
                        estado__in=['confirmada', 'ganadora', 'perdedora'])
                .aggregate(total=Sum('monto'))['total'] or 0
            )

        else:  # superadmin
            clientes_asignados = (
                User.objects
                .filter(roles__tipo='cliente', roles__activo=True)
                .count()
            )
            ventas_totales = (
                Jugada.objects
                .filter(estado__in=['confirmada', 'ganadora', 'perdedora'])
                .aggregate(total=Sum('monto'))['total'] or 0
            )

    # ---------- Estadísticas para AUDITOR ----------
    auditor_banco = None
    auditor_comerciales = []
    auditor_clientes = []
    auditor_total_boletas = 0
    auditor_total_movimientos = 0
    auditor_total_cuadres = 0

    if es_auditor:
        try:
            from roles.utils import get_red_del_auditor
            from jugadas.models import Boleta
            from roles.models import CuadreDiario

            red = get_red_del_auditor(user)
            auditor_banco = red['banco']
            auditor_comerciales = red['comerciales']
            auditor_clientes = red['clientes']
            ids_red = red['todos_ids']

            if ids_red:
                auditor_total_boletas = Boleta.objects.filter(
                    Q(usuario_id__in=ids_red) | Q(destinatario_id__in=ids_red)
                ).count()
                auditor_total_movimientos = MovimientoFondo.objects.filter(
                    Q(emisor_id__in=ids_red) | Q(receptor_id__in=ids_red)
                ).count()
                auditor_total_cuadres = CuadreDiario.objects.filter(
                    usuario_id__in=ids_red
                ).count()
                clientes_asignados = len(auditor_clientes)
                ventas_totales = Jugada.objects.filter(
                    Q(usuario_id__in=ids_red) | Q(destinatario_id__in=ids_red),
                    estado__in=['confirmada', 'ganadora', 'perdedora']
                ).aggregate(total=Sum('monto'))['total'] or 0
        except Exception:
            pass

    # ---------- Solicitudes pendientes ----------
    if es_gestor:
        if rol_usuario == 'superadmin':
            solicitudes_pendientes = MovimientoFondo.objects.filter(estado='pendiente').count()
        elif rol_usuario == 'banco':
            subordinados = Subordinacion.objects.filter(jefe=user, activo=True).values_list('subordinado_id', flat=True)
            clientes = Fondo.objects.filter(asignado_por=user, activo=True).values_list('usuario_id', flat=True)
            usuarios_ids = list(subordinados) + list(clientes) + [user.id]
            solicitudes_pendientes = MovimientoFondo.objects.filter(
                receptor__id__in=usuarios_ids, estado='pendiente'
            ).count()
        elif rol_usuario == 'comercial':
            clientes = Fondo.objects.filter(asignado_por=user, activo=True).values_list('usuario_id', flat=True)
            solicitudes_pendientes = MovimientoFondo.objects.filter(
                receptor__id__in=clientes, estado='pendiente'
            ).count()
        else:
            solicitudes_pendientes = 0
    else:
        solicitudes_pendientes = MovimientoFondo.objects.filter(
            receptor=user, estado='pendiente'
        ).count()

    notificaciones_no_leidas = Notificacion.objects.filter(usuario=user, leido=False).count()

    # ---------- Gamificación ----------
    streak = calcular_streak(user)
    nivel_data = calcular_nivel(user)

    # ---------- Sparklines ----------
    sparkline_saldo = calcular_sparkline(
        Fondo.objects.filter(usuario=user, activo=True),
        campo='monto', campo_fecha='creado_en',
    )
    sparkline_bonos = calcular_sparkline(
        Bono.objects.filter(usuario=user),
        campo='monto', campo_fecha='creado_en',
    )
    sparkline_jugadas = calcular_sparkline(
        jugadas_qs,
        campo='monto', campo_fecha='fecha',
    )
    sparkline_clientes = '0,15 25,10 50,12 75,8 100,6'

    # ---------- Perfil completado ----------
    campos_perfil = [
        bool(user.email),
        bool(user.first_name),
        bool(user.last_name),
        bool(getattr(user.perfil, 'telefono', None)) if hasattr(user, 'perfil') else False,
        bool(getattr(user.perfil, 'direccion', None)) if hasattr(user, 'perfil') else False,
        bool(getattr(user.perfil, 'foto_perfil', None)) if hasattr(user, 'perfil') else False,
    ]
    perfil_completado = int(sum(campos_perfil) / len(campos_perfil) * 100)
    perfil_completado_offset = round(94.2 * (1 - perfil_completado / 100), 2)

    # ---------- Progress rings (escala fija por stat) ----------
    ring_saldo    = round(94.2 * (1 - min(float(saldo_total) / 1000, 1.0)), 2)
    ring_bonos    = round(94.2 * (1 - min(float(total_bonos) / 500, 1.0)), 2)
    ring_jugadas  = round(94.2 * (1 - min(float(total_jugadas) / 100, 1.0)), 2)
    ring_clientes = round(94.2 * (1 - min(float(clientes_asignados) / 50, 1.0)), 2)

    # ---------- Heatmap (últimos 35 días) ----------
    try:
        hace_35 = timezone.localdate() - timedelta(days=34)
        por_dia_qs = (
            Jugada.objects
            .filter(usuario=user, fecha__date__gte=hace_35)
            .annotate(_d=TruncDate('fecha'))
            .values('_d')
            .annotate(_n=Count('id'))
        )
        mapa_dias = {r['_d']: r['_n'] for r in por_dia_qs}
        max_n = max(mapa_dias.values(), default=1) or 1
        heatmap_dias = []
        for i in range(35):
            d = hace_35 + timedelta(days=i)
            n = mapa_dias.get(d, 0)
            if n == 0:
                lvl = 0
            else:
                lvl = min(4, int(n / max_n * 4) + 1)
            heatmap_dias.append({'fecha': d, 'count': n, 'level': lvl})
    except Exception:
        heatmap_dias = []

    context = {
        'codigo_referido': codigo_referido,
        'link_referido': link_referido,
        'bonos': bonos,
        'total_bonos': total_bonos,
        'fondos': fondos,
        'saldo_total': saldo_total,
        'total_jugadas': total_jugadas,
        'ultimas_jugadas': ultimas_jugadas,
        'now': timezone.now(),
        'user': user,
        'rol_usuario': rol_usuario,
        'es_gestor': es_gestor,
        'clientes_asignados': clientes_asignados,
        'ventas_totales': ventas_totales,
        'es_auditor': es_auditor,
        'auditor_banco': auditor_banco,
        'auditor_comerciales': auditor_comerciales,
        'auditor_clientes': auditor_clientes,
        'auditor_total_boletas': auditor_total_boletas,
        'auditor_total_movimientos': auditor_total_movimientos,
        'auditor_total_cuadres': auditor_total_cuadres,
        'comisiones': comisiones,
        'solicitudes_pendientes': solicitudes_pendientes,
        'notificaciones_no_leidas': notificaciones_no_leidas,

        # Gamificación
        'streak_dias': streak,
        'nivel_usuario': nivel_data['nivel'],
        'puntos_siguiente_nivel': nivel_data['puntos_siguiente'],
        'progreso_nivel': nivel_data['progreso'],

        # Sparklines
        'sparkline_saldo': sparkline_saldo,
        'sparkline_bonos': sparkline_bonos,
        'sparkline_jugadas': sparkline_jugadas,
        'sparkline_clientes': sparkline_clientes,
        # Perfil completado
        'perfil_completado': perfil_completado,
        'perfil_completado_offset': perfil_completado_offset,
        # Rings de los stats
        'ring_saldo': ring_saldo,
        'ring_bonos': ring_bonos,
        'ring_jugadas': ring_jugadas,
        'ring_clientes': ring_clientes,
        # Heatmap semanal
        'heatmap_dias': heatmap_dias,
    }
    return render(request, 'usuarios/perfil_cliente.html', context)


@login_required
def editar_perfil(request):
    perfil, _ = Perfil.objects.get_or_create(usuario=request.user)
    if request.method == 'POST':
        form = EditarPerfilForm(request.POST, instance=request.user, perfil_instance=perfil)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ Perfil actualizado correctamente.")
            return redirect('usuarios:perfil_cliente')
    else:
        form = EditarPerfilForm(instance=request.user, perfil_instance=perfil)
    return render(request, 'usuarios/editar_perfil.html', {'form': form})


@login_required
def mis_vias_pago(request):
    user = request.user
    es_gestor = user.roles.filter(
        tipo__in=['comercial', 'banco', 'superadmin'], activo=True
    ).exists() or user.is_superuser
    if not es_gestor:
        messages.error(request, "No tienes permiso para gestionar vías de pago.")
        return redirect('usuarios:perfil_cliente')
    return redirect('roles:mis_vias_pago')


# ============================================================
# MIS FONDOS
# ============================================================

@login_required
def mis_fondos(request):
    user = request.user
    rol_usuario = get_rol_usuario(user)

    context = {'user': user, 'rol': rol_usuario}

    if rol_usuario == 'cliente':
        gestores_ids = (
            Fondo.objects
            .filter(usuario=user, activo=True)
            .exclude(asignado_por__isnull=True)
            .values_list('asignado_por_id', flat=True)
            .distinct()
        )
        gestores = User.objects.filter(id__in=gestores_ids, is_active=True)
        gestores_data = []
        total_general = Decimal('0.00')
        for gestor in gestores:
            fondos = Fondo.objects.filter(
                usuario=user, asignado_por=gestor, activo=True
            ).select_related('forma_pago')
            fondos_data = []
            total_gestor = Decimal('0.00')
            for f in fondos:
                monto = f.monto or Decimal('0.00')
                fondos_data.append({'forma_pago': f.forma_pago, 'monto': monto})
                total_gestor += monto
            gestores_data.append({
                'gestor': gestor, 'fondos': fondos_data, 'total_gestor': total_gestor,
            })
            total_general += total_gestor
        context.update({'gestores_data': gestores_data, 'total_general': total_general})

    elif rol_usuario == 'comercial':
        clientes_ids = (
            Fondo.objects
            .filter(asignado_por=user, activo=True)
            .values_list('usuario_id', flat=True)
            .distinct()
        )
        clientes = User.objects.filter(id__in=clientes_ids, is_active=True)
        clientes_data = []
        total_clientes = Decimal('0.00')
        for cliente in clientes:
            fondos = Fondo.objects.filter(
                usuario=cliente, asignado_por=user, activo=True
            ).select_related('forma_pago')
            fondos_data = []
            total_cliente = Decimal('0.00')
            for f in fondos:
                monto = f.monto or Decimal('0.00')
                fondos_data.append({'forma_pago': f.forma_pago, 'monto': monto})
                total_cliente += monto
            clientes_data.append({
                'cliente': cliente, 'fondos': fondos_data, 'total_cliente': total_cliente,
            })
            total_clientes += total_cliente

        banco_asignado = None
        rol_comercial = Rol.objects.filter(usuario=user, tipo='comercial', activo=True).first()
        if rol_comercial and rol_comercial.banco_asignado:
            banco_asignado = rol_comercial.banco_asignado

        fondo_banco_data = (
            calcular_fondo_comercial(user, banco_asignado) if banco_asignado else None
        )
        total_general = total_clientes + (
            fondo_banco_data['fondo_neto'] if fondo_banco_data else Decimal('0.00')
        )
        context.update({
            'clientes_data': clientes_data,
            'total_clientes': total_clientes,
            'banco_asignado': banco_asignado,
            'fondo_banco_data': fondo_banco_data,
            'total_general': total_general,
        })

    elif rol_usuario == 'banco':
        comerciales_ids = (
            Subordinacion.objects
            .filter(jefe=user, activo=True)
            .values_list('subordinado_id', flat=True)
        )
        comerciales = User.objects.filter(id__in=comerciales_ids, is_active=True)
        comerciales_data = []
        total_comerciales = Decimal('0.00')
        for comercial in comerciales:
            fondos = Fondo.objects.filter(
                usuario=comercial, asignado_por=user, activo=True
            ).select_related('forma_pago')
            fondos_data = []
            total_comercial = Decimal('0.00')
            for f in fondos:
                monto = f.monto or Decimal('0.00')
                fondos_data.append({'forma_pago': f.forma_pago, 'monto': monto})
                total_comercial += monto
            comerciales_data.append({
                'comercial': comercial, 'fondos': fondos_data, 'total_comercial': total_comercial,
            })
            total_comerciales += total_comercial

        clientes_directos_ids = (
            Fondo.objects
            .filter(asignado_por=user, activo=True)
            .exclude(usuario__in=comerciales_ids)
            .values_list('usuario_id', flat=True)
            .distinct()
        )
        clientes_directos = User.objects.filter(id__in=clientes_directos_ids, is_active=True)
        clientes_directos_data = []
        total_clientes_directos = Decimal('0.00')
        for cliente in clientes_directos:
            fondos = Fondo.objects.filter(
                usuario=cliente, asignado_por=user, activo=True
            ).select_related('forma_pago')
            fondos_data = []
            total_cliente = Decimal('0.00')
            for f in fondos:
                monto = f.monto or Decimal('0.00')
                fondos_data.append({'forma_pago': f.forma_pago, 'monto': monto})
                total_cliente += monto
            clientes_directos_data.append({
                'cliente': cliente, 'fondos': fondos_data, 'total_cliente': total_cliente,
            })
            total_clientes_directos += total_cliente

        fondos_propios = Fondo.objects.filter(
            usuario=user, activo=True
        ).select_related('forma_pago')
        fondos_propios_data = []
        total_fondos_propios = Decimal('0.00')
        for f in fondos_propios:
            monto = f.monto or Decimal('0.00')
            fondos_propios_data.append({'forma_pago': f.forma_pago, 'monto': monto})
            total_fondos_propios += monto

        total_general = total_comerciales + total_clientes_directos + total_fondos_propios
        context.update({
            'comerciales_data': comerciales_data,
            'total_comerciales': total_comerciales,
            'clientes_directos_data': clientes_directos_data,
            'total_clientes_directos': total_clientes_directos,
            'fondos_propios_data': fondos_propios_data,
            'total_fondos_propios': total_fondos_propios,
            'total_general': total_general,
        })

    elif rol_usuario == 'superadmin' or user.is_superuser:
        bancos_ids = Rol.objects.filter(tipo='banco', activo=True).values_list('usuario_id', flat=True)
        bancos = User.objects.filter(id__in=bancos_ids, is_active=True)
        bancos_data = []
        total_superadmin = Decimal('0.00')
        for banco in bancos:
            comerciales_ids = (
                Subordinacion.objects
                .filter(jefe=banco, activo=True)
                .values_list('subordinado_id', flat=True)
            )
            comerciales = User.objects.filter(id__in=comerciales_ids, is_active=True)
            comerciales_data = []
            total_comerciales_banco = Decimal('0.00')
            for comercial in comerciales:
                fondos = Fondo.objects.filter(
                    usuario=comercial, asignado_por=banco, activo=True
                ).select_related('forma_pago')
                fondos_data = []
                total_comercial = Decimal('0.00')
                for f in fondos:
                    monto = f.monto or Decimal('0.00')
                    fondos_data.append({'forma_pago': f.forma_pago, 'monto': monto})
                    total_comercial += monto
                comerciales_data.append({
                    'comercial': comercial, 'fondos': fondos_data,
                    'total_comercial': total_comercial,
                })
                total_comerciales_banco += total_comercial

            clientes_directos_ids = (
                Fondo.objects
                .filter(asignado_por=banco, activo=True)
                .exclude(usuario__in=comerciales_ids)
                .values_list('usuario_id', flat=True)
                .distinct()
            )
            clientes_directos = User.objects.filter(id__in=clientes_directos_ids, is_active=True)
            clientes_directos_data = []
            total_clientes_directos_banco = Decimal('0.00')
            for cliente in clientes_directos:
                fondos = Fondo.objects.filter(
                    usuario=cliente, asignado_por=banco, activo=True
                ).select_related('forma_pago')
                fondos_data = []
                total_cliente = Decimal('0.00')
                for f in fondos:
                    monto = f.monto or Decimal('0.00')
                    fondos_data.append({'forma_pago': f.forma_pago, 'monto': monto})
                    total_cliente += monto
                clientes_directos_data.append({
                    'cliente': cliente, 'fondos': fondos_data,
                    'total_cliente': total_cliente,
                })
                total_clientes_directos_banco += total_cliente

            fondos_propios = Fondo.objects.filter(
                usuario=banco, activo=True
            ).select_related('forma_pago')
            fondos_propios_data = []
            total_fondos_propios_banco = Decimal('0.00')
            for f in fondos_propios:
                monto = f.monto or Decimal('0.00')
                fondos_propios_data.append({'forma_pago': f.forma_pago, 'monto': monto})
                total_fondos_propios_banco += monto

            total_banco = (
                total_comerciales_banco
                + total_clientes_directos_banco
                + total_fondos_propios_banco
            )
            total_superadmin += total_banco
            bancos_data.append({
                'banco': banco,
                'comerciales_data': comerciales_data,
                'total_comerciales': total_comerciales_banco,
                'clientes_directos_data': clientes_directos_data,
                'total_clientes_directos': total_clientes_directos_banco,
                'fondos_propios_data': fondos_propios_data,
                'total_fondos_propios': total_fondos_propios_banco,
                'total_banco': total_banco,
            })

        context.update({'bancos_data': bancos_data, 'total_superadmin': total_superadmin})

    return render(request, 'usuarios/mis_fondos.html', context)


# ============================================================
# RECARGAS Y RETIROS
# ============================================================

@login_required
def solicitar_recarga(request):
    """
    Redirige al flujo unificado roles.solicitar('recarga').
    Se mantiene por compatibilidad con URLs antiguas.
    """
    return redirect('roles:solicitar', tipo='recarga')


@login_required
def recargar_usuario(request):
    """
    Redirige a la vista unificada en roles.recarga_directa.
    Se mantiene por compatibilidad con URLs antiguas.
    """
    return redirect('roles:recarga_directa')


@login_required
def solicitar_retiro(request):
    """
    Redirige al flujo unificado roles.solicitar('cobro').
    Se mantiene por compatibilidad con URLs antiguas.
    """
    return redirect('roles:solicitar', tipo='cobro')


@login_required
def confirmar_recarga(request, movimiento_id):
    user = request.user
    es_autorizado = user.is_superuser or user.roles.filter(
        tipo__in=['superadmin', 'banco', 'comercial'], activo=True
    ).exists()
    if not es_autorizado:
        messages.error(request, "No tienes permisos para confirmar recargas.")
        return redirect('usuarios:perfil_cliente')

    movimiento = get_object_or_404(MovimientoFondo, id=movimiento_id, estado='pendiente')

    if request.method == 'POST':
        try:
            with transaction.atomic():
                movimiento.estado = 'confirmado'
                movimiento.confirmado_en = timezone.now()
                movimiento.save(update_fields=['estado', 'confirmado_en'])

                # FASE1_POSTPAGO_V1: ingreso → primero paga postpago, resto al fondo
                from roles.utils import _aplicar_ingreso_a_fondo
                _aplicar_ingreso_a_fondo(
                    cliente=movimiento.receptor,
                    gestor=user,
                    forma_pago=movimiento.forma_pago,
                    monto=movimiento.monto,
                )

                crear_notificacion(
                    usuario=movimiento.receptor, tipo='info',
                    mensaje=f"✅ Recarga de ${movimiento.monto} confirmada por {user.username}.",
                    datos={'movimiento_id': movimiento.id, 'monto': float(movimiento.monto)},
                )
                messages.success(request, f"✅ Recarga de ${movimiento.monto} confirmada.")
                return redirect('usuarios:solicitudes_pendientes')
        except Exception as e:
            logger.exception("Error al confirmar recarga")
            messages.error(request, f"❌ Error al confirmar recarga: {str(e)}")

    return render(request, 'usuarios/confirmar_recarga.html', {'movimiento': movimiento})


@login_required
def rechazar_recarga(request, movimiento_id):
    user = request.user
    es_autorizado = user.is_superuser or user.roles.filter(
        tipo__in=['superadmin', 'banco', 'comercial'], activo=True
    ).exists()
    if not es_autorizado:
        messages.error(request, "No tienes permisos para rechazar recargas.")
        return redirect('usuarios:perfil_cliente')

    movimiento = get_object_or_404(MovimientoFondo, id=movimiento_id, estado='pendiente')

    if request.method == 'POST':
        motivo = request.POST.get('motivo', 'Sin especificar')
        metadata = movimiento.datos_transferencia or {}
        metadata['motivo_rechazo'] = motivo
        movimiento.datos_transferencia = metadata
        movimiento.estado = 'rechazado'
        movimiento.save(update_fields=['datos_transferencia', 'estado'])

        crear_notificacion(
            usuario=movimiento.receptor, tipo='info',
            mensaje=f"❌ Tu recarga de ${movimiento.monto} fue rechazada. Motivo: {motivo}",
            datos={'movimiento_id': movimiento.id, 'monto': float(movimiento.monto)},
        )
        messages.success(request, f"✅ Recarga de ${movimiento.monto} rechazada.")
        return redirect('usuarios:solicitudes_pendientes')

    return render(request, 'usuarios/rechazar_recarga.html', {'movimiento': movimiento})


# ============================================================
# SOLICITUDES Y MOVIMIENTOS
# ============================================================

@login_required
def solicitudes_pendientes(request):
    user = request.user
    es_superadmin = user.is_superuser or user.roles.filter(tipo='superadmin', activo=True).exists()
    es_banco = user.roles.filter(tipo='banco', activo=True).exists()
    es_comercial = user.roles.filter(tipo='comercial', activo=True).exists()

    if es_superadmin:
        solicitudes = MovimientoFondo.objects.filter(estado='pendiente')
    elif es_banco:
        subordinados = Subordinacion.objects.filter(jefe=user, activo=True).values_list('subordinado_id', flat=True)
        clientes = Fondo.objects.filter(asignado_por=user, activo=True).values_list('usuario_id', flat=True)
        usuarios_ids = list(subordinados) + list(clientes) + [user.id]
        solicitudes = MovimientoFondo.objects.filter(
            receptor__id__in=usuarios_ids, estado='pendiente'
        )
    elif es_comercial:
        clientes = Fondo.objects.filter(asignado_por=user, activo=True).values_list('usuario_id', flat=True)
        solicitudes = MovimientoFondo.objects.filter(
            receptor__id__in=clientes, estado='pendiente'
        )
    else:
        solicitudes = MovimientoFondo.objects.filter(receptor=user, estado='pendiente')

    solicitudes = (
        solicitudes
        .select_related('emisor', 'receptor', 'forma_pago')
        .order_by('-creado_en')
    )

    paginator = Paginator(solicitudes, 20)
    page = request.GET.get('page')
    try:
        solicitudes_page = paginator.page(page)
    except (PageNotAnInteger, EmptyPage):
        solicitudes_page = paginator.page(1)

    return render(request, 'usuarios/solicitudes_pendientes.html', {
        'solicitudes': solicitudes_page,
        'total_solicitudes': solicitudes.count(),
    })


@login_required
def historial_movimientos(request):
    """
    Historial de movimientos del usuario con filtros.
    Por defecto muestra los últimos 30 días.
    """
    user = request.user
    hoy = timezone.now().date()

    # ─── Filtros ─────────────────────────────────────────────
    fecha_desde_str = request.GET.get('fecha_desde', '').strip()
    fecha_hasta_str = request.GET.get('fecha_hasta', '').strip()
    tipo_filtro = request.GET.get('tipo', '').strip()
    estado_filtro = request.GET.get('estado', '').strip()

    fecha_desde = _parse_fecha(fecha_desde_str)
    fecha_hasta = _parse_fecha(fecha_hasta_str)

    # Default: últimos 30 días
    if not fecha_desde and not fecha_hasta:
        fecha_hasta = hoy
        fecha_desde = hoy - timedelta(days=29)
    else:
        if not fecha_desde:
            fecha_desde = fecha_hasta
        if not fecha_hasta:
            fecha_hasta = fecha_desde

    # ═══════════════════════════════════════════════════════════════
    # Si es auditor, ver movimientos de su red (banco + comerciales + clientes)
    # ═══════════════════════════════════════════════════════════════
    if user.roles.filter(tipo='auditor', activo=True).exists():
        from roles.utils import get_red_del_auditor
        red = get_red_del_auditor(user)
        if red['banco']:
            movimientos = (
                MovimientoFondo.objects
                .filter(
                    Q(emisor_id__in=red['todos_ids']) |
                    Q(receptor_id__in=red['todos_ids'])
                )
                .select_related('emisor', 'receptor', 'forma_pago')
                .order_by('-creado_en')
            )
        else:
            movimientos = MovimientoFondo.objects.none()
    else:
        movimientos = (
            MovimientoFondo.objects
            .filter(Q(emisor=user) | Q(receptor=user))
            .select_related('emisor', 'receptor', 'forma_pago')
            .order_by('-creado_en')
        )

    movimientos = movimientos.filter(creado_en__date__gte=fecha_desde)
    movimientos = movimientos.filter(creado_en__date__lte=fecha_hasta)

    if tipo_filtro:
        movimientos = movimientos.filter(tipo=tipo_filtro)

    if estado_filtro:
        movimientos = movimientos.filter(estado=estado_filtro)

    # ─── Totales (reflejan SOLO lo filtrado) ─────────────────
    resumen = movimientos.aggregate(
        total_creditos=Sum('monto', filter=Q(receptor=user, estado='confirmado')),
        total_debitos=Sum('monto', filter=Q(emisor=user, estado='confirmado')),
    )

    # ─── Paginación ──────────────────────────────────────────
    paginator = Paginator(movimientos, 20)
    page = request.GET.get('page')
    try:
        movimientos_page = paginator.page(page)
    except (PageNotAnInteger, EmptyPage):
        movimientos_page = paginator.page(1)

    return render(request, 'usuarios/historial_movimientos.html', {
        'movimientos': movimientos_page,
        'tipos': MovimientoFondo.TIPOS,
        'estados': MovimientoFondo.ESTADOS,

        # Filtros aplicados
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        'tipo_seleccionado': tipo_filtro,
        'estado_seleccionado': estado_filtro,

        # Totales
        'total_creditos': resumen.get('total_creditos') or Decimal('0.00'),
        'total_debitos': resumen.get('total_debitos') or Decimal('0.00'),

        'hoy': hoy,
    })


# ============================================================
# ESTADÍSTICAS Y REFERIDOS
# ============================================================

@login_required
def estadisticas_cliente(request):
    user = request.user
    total_apostado = (
        Jugada.objects
        .filter(usuario=user, estado='confirmada')
        .aggregate(total=Sum('monto'))['total'] or Decimal('0.00')
    )
    total_jugadas = Jugada.objects.filter(usuario=user).count()

    premios_qs = Premio.objects.filter(jugada__usuario=user).select_related('jugada')
    total_premios = (
        premios_qs
        .aggregate(total=Sum('monto_premio'))['total'] or Decimal('0.00')
    )
    premios_cobrados = premios_qs.filter(cobrado=True).count()

    bonos = Bono.objects.filter(usuario=user)
    bonos_activos = bonos.filter(estado='activo').count()

    return render(request, 'usuarios/estadisticas.html', {
        'total_apostado': total_apostado,
        'total_jugadas': total_jugadas,
        'total_premios': total_premios,
        'premios_cobrados': premios_cobrados,
        'bonos_activos': bonos_activos,
        'bonos': bonos,
    })


@login_required
def referidos_cliente(request):
    user = request.user
    perfil, _ = Perfil.objects.get_or_create(usuario=user)

    codigo_referido = perfil.codigo_referido or user.username
    link_referido = f"{request.build_absolute_uri('/usuarios/registro/')}?ref={codigo_referido}"

    referidos = User.objects.filter(perfil__referido_por=user).order_by('-date_joined')
    bonos_referidos = (
        Bono.objects
        .filter(usuario_referente=user, tipo='recomendacion')
        .order_by('-creado_en')
    )

    total_bonos_activos = (
        Bono.objects
        .filter(usuario=user, estado='activo')
        .aggregate(total=Sum('saldo_restante'))['total'] or Decimal('0.00')
    )

    total_movimientos = MovimientoFondo.objects.filter(
        Q(emisor=user) | Q(receptor=user)
    ).count()

    ultimas_notificaciones = (
        Notificacion.objects
        .filter(usuario=user)
        .order_by('-creado_en')[:3]
    )

    total_bonos = sum(b.monto for b in bonos_referidos)

    return render(request, 'usuarios/referidos_cliente.html', {
        'referidos': referidos,
        'bonos_referidos': bonos_referidos,
        'total_referidos': referidos.count(),
        'bonos_pendientes': bonos_referidos.filter(estado='pendiente').count(),
        'bonos_activos': bonos_referidos.filter(estado='activo').count(),
        'codigo_referido': codigo_referido,
        'link_referido': link_referido,
        'total_bonos': total_bonos,
        'total_bonos_activos': total_bonos_activos,
        'total_movimientos': total_movimientos,
        'ultimas_notificaciones': ultimas_notificaciones,
    })


@login_required
def promociones_cliente(request):
    user = request.user
    bonos_usuario = Bono.objects.filter(usuario=user).order_by('-creado_en')

    total_bonos_activos = (
        bonos_usuario.filter(estado='activo')
        .aggregate(total=Sum('saldo_restante'))['total'] or Decimal('0.00')
    )
    total_bonos_pendientes = (
        bonos_usuario.filter(estado='pendiente')
        .aggregate(total=Sum('saldo_restante'))['total'] or Decimal('0.00')
    )
    total_bonos_agotados = (
        bonos_usuario.filter(estado='agotado')
        .aggregate(total=Sum('saldo_restante'))['total'] or Decimal('0.00')
    )

    recargas_recientes = (
        SolicitudRecarga.objects
        .filter(cliente=user)
        .order_by('-fecha_solicitud')[:3]
    )

    return render(request, 'usuarios/promociones.html', {
        'bonos_usuario': bonos_usuario,
        'total_bonos_activos': total_bonos_activos,
        'total_bonos_pendientes': total_bonos_pendientes,
        'total_bonos_agotados': total_bonos_agotados,
        'recargas_recientes': recargas_recientes,
    })


# ============================================================
# APIS PARA BÚSQUEDA
# ============================================================

@login_required
def api_buscar_bancos_comerciales(request):
    termino = request.GET.get('q', '')
    if not termino:
        return JsonResponse([], safe=False)
    usuarios = User.objects.filter(
        Q(username__icontains=termino)
        | Q(first_name__icontains=termino)
        | Q(last_name__icontains=termino),
        roles__tipo__in=['banco', 'comercial'],
        roles__activo=True,
        is_active=True,
    ).distinct()[:20]
    data = [{'id': u.id, 'username': u.username, 'nombre': u.get_full_name()} for u in usuarios]
    return JsonResponse(data, safe=False)


@login_required
def api_buscar_destinatarios(request):
    termino = request.GET.get('q', '')
    if not termino:
        return JsonResponse([], safe=False)
    usuarios = User.objects.filter(
        Q(username__icontains=termino)
        | Q(first_name__icontains=termino)
        | Q(last_name__icontains=termino),
        is_active=True,
    ).exclude(id=request.user.id).distinct()[:20]
    data = [{'id': u.id, 'username': u.username, 'nombre': u.get_full_name()} for u in usuarios]
    return JsonResponse(data, safe=False)

# ============================================================
# MIS LÍMITES, SOBRE LÍMITES Y DOSIS
# ============================================================
@login_required
def mis_limites(request):
    """
    Página de consulta de límites, sobre límites y dosis.
    Solo para clientes. Los datos se cargan vía AJAX al seleccionar los filtros.
    """
    from roles.models import Fondo
    from jugadas.models import FormaJuego
    from pagos.models import FormaPago
    from sorteos.utils import get_sorteos_abiertos

    user = request.user
    es_cliente = user.roles.filter(tipo='cliente', activo=True).exists()
    if not es_cliente:
        messages.error(request, "Esta sección es solo para clientes.")
        return redirect('publico:home')

    # Gestores del cliente (por Fondo activo)
    gestores_ids = set()
    for f in Fondo.objects.filter(usuario=user, activo=True).select_related('asignado_por'):
        if f.asignado_por_id:
            gestores_ids.add(f.asignado_por_id)

    gestores = User.objects.filter(id__in=gestores_ids).order_by('username')

    # Sorteos abiertos (con su estado ya calculado)
    sorteos = get_sorteos_abiertos(timezone.localdate())

    formas_juego = FormaJuego.objects.filter(activo=True).order_by('nombre')
    formas_pago  = FormaPago.objects.filter(activo=True).order_by('nombre')

    context = {
        'gestores': gestores,
        'sorteos': sorteos,
        'formas_juego': formas_juego,
        'formas_pago': formas_pago,
    }
    return render(request, 'usuarios/mis_limites.html', context)


@login_required
def api_mis_limites_data(request):
    """
    API: devuelve los datos filtrados de límites, sobre límites y dosis
    para un gestor + sorteo + forma de juego + forma de pago.
    """
    from django.db.models import Sum
    from decimal import Decimal as _Dec
    from roles.models import Fondo
    from roles.utils import get_pool_gestor, get_dosis_gestor
    from jugadas.models import Jugada, FormaJuego
    from pagos.models import FormaPago
    from sorteos.models import Sorteo

    user = request.user

    gestor_id      = request.GET.get('gestor')
    sorteo_id      = request.GET.get('sorteo')
    forma_juego_id = request.GET.get('forma_juego')
    forma_pago_id  = request.GET.get('forma_pago')

    if not all([gestor_id, sorteo_id, forma_juego_id, forma_pago_id]):
        return JsonResponse({'success': False, 'error': 'Faltan filtros obligatorios'}, status=400)

    try:
        gestor      = User.objects.get(id=gestor_id)
        sorteo      = Sorteo.objects.get(id=sorteo_id)
        forma_juego = FormaJuego.objects.get(id=forma_juego_id)
        forma_pago  = FormaPago.objects.get(id=forma_pago_id)
    except (User.DoesNotExist, Sorteo.DoesNotExist, FormaJuego.DoesNotExist, FormaPago.DoesNotExist):
        return JsonResponse({'success': False, 'error': 'Filtros inválidos'}, status=400)

    # El cliente debe tener fondos con ese gestor
    if not Fondo.objects.filter(usuario=user, asignado_por=gestor, activo=True).exists():
        return JsonResponse({'success': False, 'error': 'No tienes fondos con este gestor'}, status=403)

    # Pool (límite + sobrelímite) y dosis efectiva del gestor
    try:
        pool_total = get_pool_gestor(gestor, sorteo, forma_juego, forma_pago)
    except Exception:
        pool_total = _Dec('0')

    try:
        dosis = get_dosis_gestor(gestor, sorteo, forma_juego, forma_pago)
    except Exception:
        dosis = _Dec('0')

    # Suma de apuestas por número (de TODOS los clientes del gestor)
    consumido_qs = (
        Jugada.objects
        .filter(
            destinatario=gestor,
            sorteo=sorteo,
            forma_juego=forma_juego,
            forma_pago=forma_pago,
            estado__in=['confirmada', 'pendiente'],
        )
        .values('numero')
        .annotate(total=Sum('monto'))
    )

    pool_f = float(pool_total or 0)
    numeros_data = []
    for item in consumido_qs:
        numero    = item['numero']
        apostado  = float(item['total'] or 0)
        disponible = max(0.0, pool_f - apostado)
        numeros_data.append({
            'numero': numero,
            'apostado': apostado,
            'disponible': disponible,
            'lleno': disponible <= 0,
            'porcentaje': round((disponible / pool_f * 100) if pool_f > 0 else 0, 1),
        })

    # Orden: llenos primero, luego alfabético por número
    numeros_data.sort(key=lambda x: (not x['lleno'], x['numero']))

    return JsonResponse({
        'success': True,
        'pool_total': pool_f,
        'dosis': float(dosis or 0),
        'gestor': gestor.username,
        'sorteo': sorteo.nombre,
        'forma_juego': forma_juego.nombre,
        'forma_pago': forma_pago.nombre,
        'numeros': numeros_data,
        'total_numeros': len(numeros_data),
    })

# FIX_LOGIN_SUSCRIPCION_V1: mensajes diferenciados para usuarios inactivos


@login_required
def mis_movimientos(request):
    from django.core.paginator import Paginator
    qs = MovimientoFondo.objects.filter(
        Q(receptor=request.user) | Q(emisor=request.user)
    ).select_related('emisor', 'receptor', 'forma_pago').order_by('-creado_en')
    tipo = (request.GET.get('tipo') or '').strip()
    if tipo: qs = qs.filter(tipo=tipo)
    fp_id = (request.GET.get('forma_pago') or '').strip()
    if fp_id.isdigit(): qs = qs.filter(forma_pago_id=fp_id)
    fd = (request.GET.get('fecha_desde') or '').strip()
    if fd: qs = qs.filter(creado_en__date__gte=fd)
    fh = (request.GET.get('fecha_hasta') or '').strip()
    if fh: qs = qs.filter(creado_en__date__lte=fh)
    agg = qs.aggregate(
        creditos=Sum(Case(When(monto__gt=0, then='monto'), default=0)),
        debitos=Sum(Case(When(monto__lt=0, then='monto'), default=0)),
    )
    total_creditos = agg['creditos'] or Decimal('0.00')
    total_debitos  = agg['debitos']  or Decimal('0.00')
    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'usuarios/mis_movimientos.html', {
        'page_obj': page_obj,
        'total_creditos': total_creditos, 'total_debitos': total_debitos,
        'neto': total_creditos + total_debitos,
        'clientes_sel': User.objects.none(), 'comerciales_sel': User.objects.none(),
        'formas_pago': FormaPago.objects.filter(activo=True).order_by('nombre'),
        'tipos': MovimientoFondo.TIPOS,
        'es_superadmin': False, 'es_banco': False, 'es_comercial': False,
        'filtros': {'tipo': tipo, 'forma_pago': fp_id, 'fecha_desde': fd, 'fecha_hasta': fh,
                    'cliente': '', 'comercial': '', 'q': ''},
    })
