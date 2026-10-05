# -*- coding: utf-8 -*-
import json
import logging
import re
from datetime import date, datetime, timedelta
from decimal import Decimal

# Django
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db import transaction
from django.db.models import (
    Case,
    CharField,
    Count,
    F,
    IntegerField,
    Q,
    Sum,
    Value,
    When,
    DecimalField,
)
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

# Apps propias
from jugadas.models import FormaJuego, Jugada
from pagos.models import FormaPago
from sorteos.models import DosisBase, Sorteo

from .forms import ViaPagoForm
from .models import (
    Bono,
    Comision,
    ComisionFormaPago,
    ConfiguracionComision,
    CuadreDiario,
    Deuda,
    DosisPago,
    Fondo,
    MovimientoFondo,
    LimiteApuesta,
    Notificacion,
    NumeroRestringido,
    Postpago,
    PostpagoCliente,
    PostpagoDescuento,
    Prestamo,
    RecursoAsignado,
    RelacionClienteGestor,
    RelacionComercialBanco,
    Rol,
    Sobrelimite,
    SolicitudCobroPremio,
    SolicitudRecarga,
    Subordinacion,
    SuscripcionBanco,
    ViaPago,
    SolicitudRetiro
)
from .utils import crear_notificacion
from roles.services import CuadreService

logger = logging.getLogger(__name__)

# ============================================================
# FUNCIÓN AUXILIAR PARA ORDENAR SORTEOS POR HORA
# ============================================================
def extraer_hora(nombre_sorteo):
    patron = r'(\d{1,2})(?::(\d{2}))?\s*(AM|PM)'
    match = re.search(patron, nombre_sorteo)
    if match:
        hora = int(match.group(1))
        minutos = int(match.group(2)) if match.group(2) else 0
        ampm = match.group(3)
        if ampm == 'PM' and hora != 12:
            hora += 12
        elif ampm == 'AM' and hora == 12:
            hora = 0
        return hora * 60 + minutos
    return 9999

# ============================================================
# FUNCIONES AUXILIARES
# ============================================================
def parse_date(fecha_str):
    if not fecha_str:
        return None
    try:
        return datetime.strptime(fecha_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return None

def get_rol_usuario(usuario):
    if not usuario or not usuario.is_authenticated:
        return None
    rol = Rol.objects.filter(usuario=usuario, activo=True).first()
    return rol.tipo if rol else None

def get_usuarios_visibles(request):
    user = request.user
    if user.is_superuser or user.roles.filter(tipo='superadmin', activo=True).exists():
        return User.objects.all().order_by('username')
    subordinados_ids = Subordinacion.objects.filter(jefe=user, activo=True).values_list('subordinado_id', flat=True)
    ids = list(subordinados_ids) + [user.id]
    return User.objects.filter(id__in=ids, is_active=True).order_by('username')

def descontar_monto(cliente, monto, bonos_disponibles=None, motivo='', emisor=None):
    """
    Descuenta del fondo (y bonos si hace falta) del cliente.
    Registra MovimientoFondo por cada descuento (auditoria).
    """
    if monto <= 0:
        return True, ""
    with transaction.atomic():
        fondos = list(Fondo.objects.filter(usuario=cliente, activo=True).select_for_update())
        if bonos_disponibles is None:
            bonos = list(Bono.objects.filter(usuario=cliente, estado='activo').select_for_update())
        else:
            bonos = bonos_disponibles
        monto_restante = monto
        for fondo in fondos:
            if monto_restante <= 0:
                break
            if fondo.monto > 0:
                descuento = min(fondo.monto, monto_restante)
                saldo_antes = fondo.monto
                fondo.monto -= descuento
                fondo.save()
                monto_restante -= descuento
                try:
                    MovimientoFondo.objects.create(
                        emisor=emisor,
                        receptor=cliente,
                        forma_pago=fondo.forma_pago,
                        monto=-descuento,
                        tipo='ajuste',
                        estado='confirmado',
                        motivo=motivo or 'Descuento de fondo',
                        saldo_antes=saldo_antes,
                        saldo_despues=fondo.monto,
                        datos_transferencia={'helper': 'descontar_monto'},
                    )
                except Exception:
                    pass
        if monto_restante > 0:
            for bono in bonos:
                if monto_restante <= 0:
                    break
                if bono.saldo_restante > 0:
                    descuento = min(bono.saldo_restante, monto_restante)
                    bono.saldo_restante -= descuento
                    if bono.saldo_restante <= 0:
                        bono.estado = 'agotado'
                    bono.save()
                    monto_restante -= descuento
        if monto_restante > 0:
            return False, f"No hay suficiente saldo para descontar ${monto:.2f}. Faltan ${monto_restante:.2f}."
        return True, ""

def ajustar_fondos_al_descender(usuario):
    """Convierte los fondos de un usuario a negativos (modulares) al ser descendido a cliente.
    Registra MovimientoFondo por cada fondo ajustado."""
    fondos = Fondo.objects.filter(usuario=usuario, activo=True)
    for fondo in fondos:
        if fondo.monto > 0:
            saldo_antes = fondo.monto
            fondo.monto = -fondo.monto
            fondo.save()
            delta = fondo.monto - saldo_antes
            try:
                MovimientoFondo.objects.create(
                    emisor=None,
                    receptor=usuario,
                    forma_pago=fondo.forma_pago,
                    monto=delta,
                    tipo='ajuste',
                    estado='confirmado',
                    motivo='Descenso de gestor a cliente - fondo convertido a negativo',
                    nota='Ajuste por cambio de rol',
                    saldo_antes=saldo_antes,
                    saldo_despues=fondo.monto,
                    datos_transferencia={'tipo_cambio': 'descenso', 'ajuste_rol': True},
                )
            except Exception:
                pass
    crear_notificacion(
        usuario=usuario, tipo='info',
        mensaje='Has sido descendido a cliente. Tus fondos son modulares (negativos) y se anularan con recargas.',
        datos={'tipo_cambio': 'descenso', 'fecha': timezone.now().isoformat(), 'url_detalle': '/usuarios/mis-fondos/'},
        prioridad='alta', categoria='sistema'
    )


def anular_bonos_usuario(usuario):
    """Anula todos los bonos activos de un usuario al ser ascendido."""
    bonos_activos = Bono.objects.filter(
        usuario=usuario, estado='activo'
    ).filter(
        Q(fecha_vencimiento__isnull=True) | 
        Q(fecha_vencimiento__gte=timezone.now())
    ).order_by(
        F('fecha_vencimiento').asc(nulls_last=True), 'creado_en'
    )
    for bono in bonos_activos:
        bono.estado = 'agotado'
        bono.saldo_restante = 0
        bono.save()
    if bonos_activos.exists():
        crear_notificacion(
            usuario=usuario,
            tipo='sistema',
            mensaje="⚠️ Tus bonos activos han sido anulados debido a un cambio de rol.",
            prioridad='media',
            categoria='sistema'
        )

def asignar_limites_dosis_predeterminados(usuario, recursos_sorteos, recursos_formas_juego, recursos_formas_pago, banco_origen=None):
    """
    Asigna limites, sobrelimites y dosis por defecto a un usuario (banco o comercial).
    VERSION OPTIMIZADA: bulk_create para evitar timeout con miles de combinaciones.
    """
    from .dosis_default import get_dosis_global, get_limite_por_forma, get_sobre_por_forma
    es_banco = usuario.roles.filter(tipo='banco', activo=True).exists()
    es_comercial = usuario.roles.filter(tipo='comercial', activo=True).exists()
    banco_field = usuario if es_banco else None
    comercial_field = usuario if es_comercial else None

    # Cargar objetos en lote
    sorteos = list(Sorteo.objects.filter(id__in=recursos_sorteos))
    formas_juego = list(FormaJuego.objects.filter(id__in=recursos_formas_juego))
    formas_pago = list(FormaPago.objects.filter(id__in=recursos_formas_pago))

    if not (sorteos and formas_juego and formas_pago):
        return 0

    # Construir listas en memoria (sin tocar la BD)
    limites_bulk = []
    dosis_bulk = []
    for sorteo in sorteos:
        for fj in formas_juego:
            limite_val = get_limite_por_forma(fj.nombre)
            sobre_val = get_sobre_por_forma(fj.nombre)
            dosis_val = get_dosis_global(fj.nombre) or 1
            for fp in formas_pago:
                limites_bulk.append(LimiteApuesta(
                    banco=banco_field,
                    comercial=comercial_field,
                    sorteo=sorteo,
                    forma_juego=fj,
                    forma_pago=fp,
                    monto_maximo=limite_val,
                    monto_sobrelimite=sobre_val,
                    activo=True
                ))
                dosis_bulk.append(DosisPago(
                    banco=banco_field,
                    comercial=comercial_field,
                    sorteo=sorteo,
                    forma_juego=fj,
                    forma_pago=fp,
                    monto_por_peso=dosis_val,
                    activo=True
                ))

    with transaction.atomic():
        # Borrar existentes del usuario (evita duplicados)
        if es_banco:
            LimiteApuesta.objects.filter(banco=usuario, comercial__isnull=True).delete()
            DosisPago.objects.filter(banco=usuario, comercial__isnull=True).delete()
        elif es_comercial:
            LimiteApuesta.objects.filter(comercial=usuario).delete()
            DosisPago.objects.filter(comercial=usuario).delete()

        # Bulk create en 2 queries
        if limites_bulk:
            LimiteApuesta.objects.bulk_create(limites_bulk, batch_size=1000)
        if dosis_bulk:
            DosisPago.objects.bulk_create(dosis_bulk, batch_size=1000)

    return len(limites_bulk)

def reasignar_comerciales_al_descender_banco(banco):
    """Reasigna comerciales cuando un banco es degradado."""
    comerciales = Subordinacion.objects.filter(jefe=banco, activo=True).select_related('subordinado')
    for sub in comerciales:
        sub.delete()
        Rol.objects.filter(
            usuario=sub.subordinado,
            tipo='comercial',
            activo=True
        ).update(banco_asignado=None)
        crear_notificacion(
            usuario=sub.subordinado,
            tipo='warning',
            mensaje=f"⚠️ Tu banco {banco.username} ha sido degradado. Has quedado sin banco asignado.",
            prioridad='alta',
            categoria='administracion'
        )
    if comerciales.exists():
        crear_notificacion(
            usuario=banco,
            tipo='info',
            mensaje=f"⚠️ Al degradar a {banco.username} de banco, sus {comerciales.count()} comerciales han quedado sin asignar.",
            prioridad='alta',
            categoria='administracion'
        )

# ============================================================
# VISTAS DE CUADRES
# ============================================================
@login_required
def historial_cuadres(request):
    user = request.user
    es_superadmin = user.is_superuser or user.roles.filter(tipo='superadmin', activo=True).exists()
    es_banco = user.roles.filter(tipo='banco', activo=True).exists()
    es_comercial = user.roles.filter(tipo='comercial', activo=True).exists()
    es_auditor_user = user.roles.filter(tipo='auditor', activo=True).exists()
    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin = request.GET.get('fecha_fin')
    tipo = request.GET.get('tipo', 'comercial')

    if es_superadmin:
        cuadres = CuadreDiario.objects.all()
    elif es_banco:
        comerciales_ids = Subordinacion.objects.filter(jefe=user, activo=True).values_list('subordinado_id', flat=True)
        cuadres = CuadreDiario.objects.filter(Q(usuario__in=comerciales_ids) | Q(usuario=user))
    elif es_comercial:
        cuadres = CuadreDiario.objects.filter(usuario=user)
    elif es_auditor_user:
        from roles.utils import get_red_del_auditor, crear_notificacion
        red = get_red_del_auditor(user)
        if red['banco']:
            cuadres = CuadreDiario.objects.filter(usuario_id__in=red['todos_ids'])
        else:
            cuadres = CuadreDiario.objects.none()
    else:
        cuadres = CuadreDiario.objects.none()

    if fecha_inicio:
        cuadres = cuadres.filter(fecha__gte=fecha_inicio)
    if fecha_fin:
        cuadres = cuadres.filter(fecha__lte=fecha_fin)

    cuadres = cuadres.order_by('-fecha', '-id')

    stats = {
        'total_deuda': cuadres.aggregate(total=Sum('deuda_total'))['total'] or 0,
        'total_pagado': cuadres.aggregate(total=Sum('pagado'))['total'] or 0,
        'total_ajuste': cuadres.aggregate(total=Sum('ajuste_cash') + Sum('ajuste_saldo') + Sum('ajuste_tarjeta'))['total'] or 0,
        'total_envie': cuadres.aggregate(total=Sum('envie_cash') + Sum('envie_saldo') + Sum('envie_tarjeta'))['total'] or 0,
        'total_recibi': cuadres.aggregate(total=Sum('recibi_cash') + Sum('recibi_saldo') + Sum('recibi_tarjeta'))['total'] or 0,
        'total_inicial': cuadres.aggregate(total=Sum('inicial_cash') + Sum('inicial_saldo') + Sum('inicial_tarjeta'))['total'] or 0,
        'total_cerrados': cuadres.filter(cerrado=True).count(),
    }

    context = {
        'cuadres': cuadres,
        'stats': stats,
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
        'tipo': tipo,
        'es_superadmin': es_superadmin,
        'es_banco': es_banco,
        'es_comercial': es_comercial,
        'es_auditor': es_auditor_user,
    }
    return render(request, 'roles/historial_cuadres.html', context)

@login_required
def detalle_cuadre(request, cuadre_id):
    cuadre = get_object_or_404(CuadreDiario, id=cuadre_id)
    user = request.user
    es_superadmin = user.is_superuser or user.roles.filter(tipo='superadmin', activo=True).exists()
    es_banco = user.roles.filter(tipo='banco', activo=True).exists()
    if not es_superadmin and cuadre.usuario != user:
        if es_banco:
            es_subordinado = Subordinacion.objects.filter(jefe=user, subordinado=cuadre.usuario, activo=True).exists()
            if not es_subordinado:
                messages.error(request, "No tienes permisos para ver este cuadre.")
                return redirect('roles:historial_cuadres')
        else:
            messages.error(request, "No tienes permisos para ver este cuadre.")
            return redirect('roles:historial_cuadres')
    jugadas = Jugada.objects.filter(destinatario=cuadre.usuario, fecha_sorteo=cuadre.fecha).select_related('sorteo', 'forma_juego', 'forma_pago', 'usuario')
    context = {'cuadre': cuadre, 'jugadas': jugadas}
    return render(request, 'roles/detalle_cuadre.html', context)

@login_required
def historial_ventas(request):
    user = request.user
    es_superadmin = user.is_superuser or user.roles.filter(tipo='superadmin', activo=True).exists()
    es_banco = user.roles.filter(tipo='banco', activo=True).exists()
    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin = request.GET.get('fecha_fin')
    sorteo_id = request.GET.get('sorteo')
    forma_juego_id = request.GET.get('forma_juego')
    jugadas = Jugada.objects.filter(estado__in=['confirmada', 'ganadora', 'perdedora'])
    if es_superadmin:
        pass
    elif es_banco:
        comerciales_ids = Subordinacion.objects.filter(jefe=user, activo=True).values_list('subordinado_id', flat=True)
        jugadas = jugadas.filter(Q(destinatario__in=comerciales_ids) | Q(destinatario=user))
    else:
        jugadas = jugadas.filter(destinatario=user)
    if fecha_inicio:
        jugadas = jugadas.filter(fecha_sorteo__gte=fecha_inicio)
    if fecha_fin:
        jugadas = jugadas.filter(fecha_sorteo__lte=fecha_fin)
    if sorteo_id:
        jugadas = jugadas.filter(sorteo_id=sorteo_id)
    if forma_juego_id:
        jugadas = jugadas.filter(forma_juego_id=forma_juego_id)
    ventas_agrupadas = jugadas.values('sorteo__nombre', 'forma_juego__nombre', 'fecha_sorteo').annotate(
        total_monto=Sum('monto'), total_jugadas=Count('id'), total_premios=Sum('monto_premio')
    ).order_by('-fecha_sorteo', '-total_monto')
    total_ventas = jugadas.aggregate(total=Sum('monto'))['total'] or 0
    total_jugadas = jugadas.count()
    total_premios = jugadas.aggregate(total=Sum('monto_premio'))['total'] or 0
    context = {
        'ventas': ventas_agrupadas, 'total_ventas': total_ventas,
        'total_jugadas': total_jugadas, 'total_premios': total_premios,
        'sorteos': Sorteo.objects.filter(activo=True), 'formas_juego': FormaJuego.objects.filter(activo=True),
        'fecha_inicio': fecha_inicio, 'fecha_fin': fecha_fin,
        'sorteo_seleccionado': sorteo_id, 'forma_juego_seleccionada': forma_juego_id,
    }
    return render(request, 'roles/historial_ventas.html', context)

@login_required
def analisis_rendimiento(request):
    user = request.user
    es_superadmin = user.is_superuser or user.roles.filter(tipo='superadmin', activo=True).exists()
    es_banco = user.roles.filter(tipo='banco', activo=True).exists()
    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin = request.GET.get('fecha_fin')
    sorteo_id = request.GET.get('sorteo')
    jugadas = Jugada.objects.filter(estado__in=['confirmada', 'ganadora', 'perdedora'])
    if fecha_inicio:
        jugadas = jugadas.filter(fecha_sorteo__gte=fecha_inicio)
    if fecha_fin:
        jugadas = jugadas.filter(fecha_sorteo__lte=fecha_fin)
    if es_superadmin:
        pass
    elif es_banco:
        comerciales_ids = Subordinacion.objects.filter(jefe=user, activo=True).values_list('subordinado_id', flat=True)
        jugadas = jugadas.filter(Q(destinatario__in=comerciales_ids) | Q(destinatario=user))
    else:
        jugadas = jugadas.filter(destinatario=user)
    if sorteo_id:
        jugadas = jugadas.filter(sorteo_id=sorteo_id)

    rendimiento_qs = jugadas.values('sorteo__id', 'sorteo__nombre').annotate(
        total_apuestas=Count('id'), total_monto=Sum('monto'), total_premios=Sum('monto_premio'),
        total_ganadoras=Count(Case(When(monto_premio__gt=0, then=1), output_field=IntegerField())),
        total_perdedoras=Count(Case(When(monto_premio=0, then=1), output_field=IntegerField()))
    ).order_by('-total_monto')
    rendimiento_ordenado = []
    for data in rendimiento_qs:
        data['ganancia_neta'] = (data['total_monto'] or 0) - (data['total_premios'] or 0)
        data['porcentaje_ganancia'] = 0
        if data['total_monto'] and data['total_monto'] > 0:
            data['porcentaje_ganancia'] = (data['ganancia_neta'] / data['total_monto']) * 100
        rendimiento_ordenado.append(data)
    top_mejores = rendimiento_ordenado[:5]
    top_peores = rendimiento_ordenado[-5:] if len(rendimiento_ordenado) > 5 else []
    context = {
        'rendimiento': rendimiento_ordenado, 'top_mejores': top_mejores, 'top_peores': top_peores,
        'sorteos': Sorteo.objects.filter(activo=True), 'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin, 'sorteo_seleccionado': sorteo_id,
    }
    return render(request, 'roles/analisis_rendimiento.html', context)

@login_required
def resumen_diario(request, cuadre_id):
    cuadre = get_object_or_404(CuadreDiario, id=cuadre_id)
    user = request.user
    es_propietario = cuadre.usuario == user
    es_banco = user.roles.filter(tipo='banco', activo=True).exists()
    es_superadmin = user.is_superuser or user.roles.filter(tipo='superadmin', activo=True).exists()
    if not (es_propietario or es_banco or es_superadmin):
        messages.error(request, "No tienes permiso para ver este cuadre.")
        return redirect('roles:historial_cuadres')
    formas_pago = FormaPago.objects.filter(activo=True)
    def sum_json_field(field_name):
        total = 0
        data = getattr(cuadre, field_name, {}) or {}
        for fp in formas_pago:
            total += data.get(fp.nombre, 0) or 0
        return total
    total_fondo_inicial = sum_json_field('fondo_inicial')
    total_limpio = sum_json_field('limpio')
    total_enviado_banco = sum_json_field('enviado_banco')
    total_recibido_banco = sum_json_field('recibido_banco')
    total_fondo_final = sum_json_field('fondo_final')
    context = {
        'cuadre': cuadre, 'formas_pago': formas_pago, 'total_fondo_inicial': total_fondo_inicial,
        'total_limpio': total_limpio, 'total_enviado_banco': total_enviado_banco,
        'total_recibido_banco': total_recibido_banco, 'total_fondo_final': total_fondo_final,
    }
    return render(request, 'roles/resumen_diario.html', context)

@login_required
def editar_cuadre(request, cuadre_id):
    cuadre = get_object_or_404(CuadreDiario, id=cuadre_id)
    user = request.user
    es_banco = user.roles.filter(tipo='banco', activo=True).exists()
    es_superadmin = user.is_superuser or user.roles.filter(tipo='superadmin', activo=True).exists()
    if es_banco:
        es_subordinado = Subordinacion.objects.filter(jefe=user, subordinado=cuadre.usuario, activo=True).exists()
        if not es_subordinado:
            messages.error(request, "No tienes permiso para editar el cuadre de este comercial.")
            return redirect('roles:historial_cuadres')
    if not (es_banco or es_superadmin):
        messages.error(request, "Solo los bancos o superadmin pueden editar este cuadre.")
        return redirect('roles:historial_cuadres')
    if cuadre.cerrado:
        messages.error(request, "Este cuadre está cerrado y no se puede modificar.")
        return redirect('roles:resumen_diario', cuadre_id=cuadre.id)
    formas_pago = FormaPago.objects.filter(activo=True)
    if request.method == 'POST':
        enviado_data = {}
        recibido_data = {}
        for fp in formas_pago:
            enviado_key = f'enviado_{fp.id}'
            recibido_key = f'recibido_{fp.id}'
            try:
                enviado_val = float(request.POST.get(enviado_key, 0))
                recibido_val = float(request.POST.get(recibido_key, 0))
                enviado_data[fp.nombre] = enviado_val
                recibido_data[fp.nombre] = recibido_val
            except ValueError:
                messages.error(request, f"Valor inválido para {fp.nombre}.")
                return redirect('roles:editar_cuadre', cuadre_id=cuadre.id)
        cuadre.enviado_banco = enviado_data
        cuadre.recibido_banco = recibido_data
        cuadre.editado_por = user
        cuadre.editado_en = timezone.now()
        cuadre.save()
        messages.success(request, "✅ Cuadre actualizado correctamente.")
        return redirect('roles:resumen_diario', cuadre_id=cuadre.id)
    context = {'cuadre': cuadre, 'formas_pago': formas_pago}
    return render(request, 'roles/editar_cuadre.html', context)

# ============================================================
# VISTAS DE NOTIFICACIONES
# ============================================================
@login_required
def mis_notificaciones(request):
    user = request.user
    if request.GET.get('marcar_todas'):
        now = timezone.now()
        count = Notificacion.objects.filter(usuario=user, leido=False).update(leido=True, leido_en=now)
        messages.success(request, f"✅ {count} notificaciones marcadas como leídas.")
        return redirect('roles:notificaciones')
    if request.GET.get('marcar'):
        try:
            notif_id = int(request.GET.get('marcar'))
            notif = Notificacion.objects.get(id=notif_id, usuario=user)
            if not notif.leido:
                notif.marcar_como_leida()
            messages.success(request, "✅ Notificación marcada como leída.")
        except (Notificacion.DoesNotExist, ValueError):
            messages.error(request, "❌ Notificación no encontrada.")
        return redirect('roles:notificaciones')
    notificaciones = Notificacion.objects.filter(usuario=user).order_by('-creado_en')
    estado = request.GET.get('estado')
    if estado == 'no_leidas':
        notificaciones = notificaciones.filter(leido=False)
    elif estado == 'leidas':
        notificaciones = notificaciones.filter(leido=True)
    prioridad = request.GET.get('prioridad')
    if prioridad and prioridad in ['urgente', 'alta', 'media', 'baja']:
        notificaciones = notificaciones.filter(prioridad=prioridad)
    categoria = request.GET.get('categoria')
    if categoria:
        notificaciones = notificaciones.filter(categoria__iexact=categoria)
    no_leidas = Notificacion.objects.filter(usuario=user, leido=False).count()
    paginator = Paginator(notificaciones, 10)
    page = request.GET.get('page')
    try:
        page_obj = paginator.page(page)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)
    context = {
        'page_obj': page_obj, 'no_leidas': no_leidas, 'total': notificaciones.count(),
        'filtros': {'estado': estado, 'prioridad': prioridad, 'categoria': categoria},
    }
    return render(request, 'roles/notificaciones.html', context)

@login_required
def marcar_notificacion_leida(request, notificacion_id):
    if request.method == 'POST':
        try:
            notif = Notificacion.objects.get(id=notificacion_id, usuario=request.user)
            notif.marcar_como_leida()
            return JsonResponse({'success': True})
        except Notificacion.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Notificación no encontrada'}, status=404)
    return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=400)

@login_required
def marcar_todas_leidas(request):
    if request.method == 'POST':
        now = timezone.now()
        count = Notificacion.objects.filter(usuario=request.user, leido=False).update(leido=True, leido_en=now)
        return JsonResponse({'success': True, 'marcadas': count})
    return JsonResponse({'success': False}, status=400)

@login_required
def marcar_seleccionadas(request):
    if request.method != 'POST':
        messages.error(request, "Método no permitido.")
        return redirect('roles:notificaciones')
    notificaciones_ids = request.POST.getlist('notificaciones')
    if not notificaciones_ids:
        messages.warning(request, "No seleccionaste ninguna notificación.")
        return redirect('roles:notificaciones')
    now = timezone.now()
    count = Notificacion.objects.filter(id__in=notificaciones_ids, usuario=request.user, leido=False).update(leido=True, leido_en=now)
    messages.success(request, f"✅ {count} notificaciones marcadas como leídas.")
    return redirect('roles:notificaciones')

def contar_notificaciones_no_leidas(request):
    count = 0
    if request.user.is_authenticated:
        try:
            count = Notificacion.objects.filter(usuario=request.user, leido=False).count()
        except Exception:
            count = 0
    return JsonResponse({'count': count})

@login_required
def api_notificaciones_recientes(request):
    notis = Notificacion.objects.filter(usuario=request.user, leido=False).order_by('-creado_en')[:20]
    data = {'notificaciones': []}
    for n in notis:
        data['notificaciones'].append({
            'id': n.id, 'tipo': n.tipo, 'mensaje': n.mensaje, 'leido': n.leido,
            'leido_en': n.leido_en.isoformat() if n.leido_en else None,
            'prioridad': n.prioridad, 'categoria': n.categoria, 'con_sonido': n.con_sonido,
            'creado_en': n.creado_en.isoformat(), 'datos': n.datos,
            'fecha': n.creado_en.strftime('%d/%m/%Y %H:%M')
        })
    return JsonResponse(data, safe=False)

@login_required
def api_notificaciones(request):
    return api_notificaciones_recientes(request)

@login_required
def api_notificaciones_nuevas(request):
    ultimo_id = request.GET.get('ultimo_id', 0)
    try:
        ultimo_id = int(ultimo_id)
    except ValueError:
        ultimo_id = 0
    notificaciones = Notificacion.objects.filter(
        usuario=request.user,
        id__gt=ultimo_id
    ).order_by('id')[:20]
    data = []
    for n in notificaciones:
        data.append({
            'id': n.id,
            'tipo': n.tipo,
            'mensaje': n.mensaje,
            'con_sonido': n.con_sonido,
            'fecha': n.creado_en.strftime('%d/%m/%Y %H:%M'),
        })
    return JsonResponse({'notificaciones': data})

@login_required
def api_notificaciones_ultimo_id(request):
    ultima = Notificacion.objects.filter(usuario=request.user).order_by('-id').first()
    return JsonResponse({'ultimo_id': ultima.id if ultima else 0})

# ============================================================
# VISTAS DE GESTIÓN DE BANCOS Y SUSCRIPCIONES
# ============================================================
@login_required
def panel_bancos(request):
    if not (request.user.is_superuser or request.user.roles.filter(tipo='superadmin', activo=True).exists()):
        messages.error(request, "No tienes permisos para acceder a esta sección.")
        return redirect('publico:home')
    bancos = User.objects.filter(roles__tipo='banco', roles__activo=True).distinct()
    suscripciones = SuscripcionBanco.objects.filter(banco__in=bancos).select_related('banco')
    ahora = timezone.now()
    total_bancos = bancos.count()
    activos = suscripciones.filter(activo=True, fecha_vencimiento__gt=ahora).count()
    vencidos = suscripciones.filter(activo=True, fecha_vencimiento__lte=ahora).count()
    inactivos = suscripciones.filter(activo=False).count()
    context = {'suscripciones': suscripciones, 'total_bancos': total_bancos, 'activos': activos, 'vencidos': vencidos, 'inactivos': inactivos}
    return render(request, 'roles/panel_bancos.html', context)

@login_required
def editar_suscripcion(request, suscripcion_id):
    if not (request.user.is_superuser or request.user.roles.filter(tipo='superadmin', activo=True).exists()):
        messages.error(request, "No tienes permisos.")
        return redirect('publico:home')
    suscripcion = get_object_or_404(SuscripcionBanco, id=suscripcion_id)
    if request.method == 'POST':
        tipo_pago = request.POST.get('tipo_pago')
        cuota_fija = request.POST.get('cuota_fija')
        porcentaje = request.POST.get('porcentaje_ganancia')
        activo = request.POST.get('activo') == 'on'
        periodo_dias = request.POST.get('periodo_dias')
        try:
            if cuota_fija:
                suscripcion.cuota_fija = Decimal(cuota_fija)
            if porcentaje:
                suscripcion.porcentaje_ganancia = Decimal(porcentaje)
            if tipo_pago:
                suscripcion.tipo_pago = tipo_pago
            if periodo_dias:
                suscripcion.periodo = timedelta(days=int(periodo_dias))
            suscripcion.activo = activo
            suscripcion.save()
            messages.success(request, "✅ Suscripción actualizada correctamente.")
        except Exception as e:
            messages.error(request, f"❌ Error al actualizar: {str(e)}")
        return redirect('roles:panel_bancos')
    context = {'suscripcion': suscripcion, 'tipos_pago': SuscripcionBanco.TIPO_PAGO_CHOICES}
    return render(request, 'roles/editar_suscripcion.html', context)

@login_required
def solicitar_cambios_suscripcion(request):
    banco = request.user
    if not banco.roles.filter(tipo='banco', activo=True).exists():
        messages.error(request, "No eres un banco.")
        return redirect('publico:home')
    suscripcion = get_object_or_404(SuscripcionBanco, banco=banco, activo=True)
    if suscripcion.solicitud_pendiente:
        messages.warning(request, "Ya tienes una solicitud pendiente. Espera a que sea atendida.")
        return redirect('roles:panel_suscripcion_banco')
    recursos_actuales = suscripcion.recursos_activos()
    recursos_actuales_ids = list(recursos_actuales.values_list('id', flat=True))
    recursos_disponibles = RecursoAsignado.objects.filter(banco=None, comercial=None, activo=True).exclude(id__in=recursos_actuales_ids)
    if request.method == 'POST':
        tipo = request.POST.get('tipo')
        detalle = {}
        if tipo in ('recursos', 'ambos'):
            nuevos_recursos_ids = request.POST.getlist('recursos_solicitados')
            if nuevos_recursos_ids:
                recursos_validos = recursos_disponibles.filter(id__in=nuevos_recursos_ids)
                if recursos_validos.count() != len(nuevos_recursos_ids):
                    messages.error(request, "Algunos recursos seleccionados no están disponibles.")
                    return redirect('roles:solicitar_cambios_suscripcion')
                detalle['recursos_ids'] = [int(id) for id in nuevos_recursos_ids]
            else:
                messages.error(request, "Debes seleccionar al menos un recurso.")
                return redirect('roles:solicitar_cambios_suscripcion')
        if tipo in ('comerciales', 'ambos'):
            cantidad_str = request.POST.get('cantidad_comerciales')
            try:
                cantidad = int(cantidad_str)
                if cantidad <= suscripcion.comerciales_permitidos:
                    messages.error(request, f"El nuevo límite debe ser mayor al actual ({suscripcion.comerciales_permitidos}).")
                    return redirect('roles:solicitar_cambios_suscripcion')
                detalle['comerciales_solicitados'] = cantidad
            except (ValueError, TypeError):
                messages.error(request, "Cantidad de comerciales no válida.")
                return redirect('roles:solicitar_cambios_suscripcion')
        suscripcion.solicitud_pendiente = True
        suscripcion.solicitud_tipo = tipo
        suscripcion.solicitud_detalle = detalle
        suscripcion.save()
        superadmins = User.objects.filter(roles__tipo='superadmin', roles__activo=True)
        for admin in superadmins:
            crear_notificacion(usuario=admin, tipo='suscripcion', mensaje=f"📩 {banco.username} ha solicitado cambios en su suscripción.",
                datos={'banco': banco.username, 'banco_id': banco.id, 'tipo': tipo, 'detalle': detalle, 'url_detalle': '/roles/gestionar-solicitudes-suscripcion/'},
                prioridad='alta', categoria='financiera')
        crear_notificacion(usuario=banco, tipo='suscripcion', mensaje="✅ Tu solicitud de cambios ha sido enviada. Espera la respuesta del administrador.",
            datos={'tipo': tipo, 'detalle': detalle, 'url_detalle': '/roles/panel-suscripcion-banco/'}, prioridad='media', categoria='financiera')
        messages.success(request, "✅ Solicitud enviada. Espera la aprobación del administrador.")
        return redirect('roles:panel_suscripcion_banco')
    context = {
        'suscripcion': suscripcion, 'recursos_disponibles': recursos_disponibles,
        'recursos_actuales': recursos_actuales, 'comerciales_actuales': suscripcion.comerciales_activos(),
        'comerciales_permitidos': suscripcion.comerciales_permitidos, 'costo_mensual': suscripcion.costo_mensual(),
    }
    return render(request, 'roles/solicitar_cambios_suscripcion.html', context)

@login_required
def gestionar_comisiones(request):
    """
    Superadmin → él mismo + sus comerciales directos
    Banco      → él mismo + sus comerciales
    Comercial  → solo lectura (ve su propia config)
    """
    rol = request.user.roles.filter(activo=True).first()
    if not rol:
        messages.error(request, 'No tienes un rol activo.')
        return redirect('home')

    if rol.tipo == 'comercial':
        # Los comerciales solo ven su propia configuración (read-only)
        objetivos = Rol.objects.filter(
            usuario=request.user, activo=True
        ).select_related('usuario')
        puede_editar = False

    elif rol.tipo in ['superadmin', 'banco']:
        # Yo mismo + mis subordinados directos
        sub_ids = Subordinacion.objects.filter(
            jefe=request.user, activo=True
        ).values_list('subordinado_id', flat=True)

        objetivos = Rol.objects.filter(
            Q(usuario=request.user) | Q(usuario_id__in=sub_ids),
            activo=True
        ).select_related('usuario').distinct()
        puede_editar = True

    else:
        messages.error(request, 'No tienes permiso para gestionar comisiones.')
        return redirect('home')

    configs = {
        c.usuario_id: c
        for c in ConfiguracionComision.objects.filter(
            usuario__in=[o.usuario for o in objetivos]
        ).prefetch_related('comisiones_fp__forma_pago')
    }

    return render(request, 'roles/gestionar_comisiones.html', {
        'objetivos': objetivos,
        'configs': configs,
        'formas_pago': FormaPago.objects.filter(activo=True),
        'es_superadmin': rol.tipo == 'superadmin',
        'es_banco': rol.tipo == 'banco',
        'es_comercial': rol.tipo == 'comercial',
        'puede_editar': puede_editar,
        'usuario_actual': request.user,
    })


@login_required
def guardar_comision(request, usuario_id):
    """
    Guarda o actualiza la config de un usuario.
    Permisos:
      - Puedes editar TU PROPIA comisión
      - Puedes editar la de tus SUBORDINADOS DIRECTOS
    """
    if request.method != 'POST':
        return redirect('roles:gestionar_comisiones')

    rol = request.user.roles.filter(activo=True).first()
    if not rol or rol.tipo not in ['superadmin', 'banco']:
        messages.error(request, 'No tienes permiso para modificar comisiones.')
        return redirect('roles:gestionar_comisiones')

    objetivo_rol = get_object_or_404(Rol, usuario_id=usuario_id, activo=True)

    # ── Validar permiso ────────────────────────────────────────
    es_si_mismo = (objetivo_rol.usuario_id == request.user.id)
    es_subordinado = Subordinacion.objects.filter(
        jefe=request.user, subordinado_id=usuario_id, activo=True
    ).exists()

    if not (es_si_mismo or es_subordinado):
        messages.error(
            request,
            'Solo puedes configurar tu propia comisión o la de tus subordinados directos.'
        )
        return redirect('roles:gestionar_comisiones')

    # ── Guardar ────────────────────────────────────────────────
    modalidad = request.POST.get('modalidad', 'general')
    porcentaje = request.POST.get('porcentaje_general', '0')

    try:
        porcentaje_dec = Decimal(porcentaje or '0')
    except (InvalidOperation, TypeError, ValueError):
        messages.error(request, 'Porcentaje inválido.')
        return redirect('roles:gestionar_comisiones')

    config, _ = ConfiguracionComision.objects.update_or_create(
        usuario_id=usuario_id,
        defaults={
            'modalidad': modalidad,
            'porcentaje_general': porcentaje_dec,
            'activo': True,
        }
    )

    # Desglose por forma de pago
    config.comisiones_fp.all().delete()
    if modalidad == 'por_grupo':
        for fp in FormaPago.objects.filter(activo=True):
            val = request.POST.get(f'fp_{fp.id}', '').strip()
            if val:
                try:
                    ComisionFormaPago.objects.create(
                        configuracion=config,
                        forma_pago=fp,
                        porcentaje=Decimal(val)
                    )
                except (InvalidOperation, TypeError, ValueError):
                    continue

    messages.success(
        request,
        f'✅ Comisión actualizada para {objetivo_rol.usuario.username}.'
    )
    return redirect('roles:gestionar_comisiones')
@login_required
def panel_suscripcion_banco(request):
    user = request.user
    if not user.roles.filter(tipo='banco', activo=True).exists():
        messages.error(request, "No eres un banco registrado.")
        return redirect('publico:home')
    suscripcion = get_object_or_404(SuscripcionBanco, banco=user)
    ahora = timezone.now()
    dias_restantes = (suscripcion.fecha_vencimiento - ahora).days
    recursos = suscripcion.recursos_activos()
    comerciales_activos = suscripcion.comerciales_activos()
    comerciales_permitidos = suscripcion.comerciales_permitidos
    costo_mensual = suscripcion.costo_mensual()
    monto_pendiente = suscripcion.calcular_monto_pendiente()
    comerciales = Subordinacion.objects.filter(jefe=user, activo=True).select_related('subordinado')
    context = {
        'suscripcion': suscripcion, 'dias_restantes': dias_restantes, 'monto_pendiente': monto_pendiente,
        'costo_mensual': costo_mensual, 'comerciales': comerciales, 'comerciales_activos': comerciales_activos,
        'comerciales_permitidos': comerciales_permitidos, 'recursos': recursos,
        'recursos_por_tipo': {'sorteo': recursos.filter(tipo='sorteo'), 'forma_juego': recursos.filter(tipo='forma_juego'), 'forma_pago': recursos.filter(tipo='forma_pago')},
        'puede_solicitar': True, 'now': ahora,
    }
    return render(request, 'roles/panel_suscripcion_banco.html', context)

@login_required
def cambiar_tipo_pago_banco(request):
    user = request.user
    suscripcion = get_object_or_404(SuscripcionBanco, banco=user)
    if request.method == 'POST':
        nuevo_tipo = request.POST.get('tipo_pago')
        if not nuevo_tipo or nuevo_tipo not in dict(SuscripcionBanco.TIPO_PAGO_CHOICES):
            messages.error(request, "Tipo de pago inválido.")
            return redirect('roles:panel_suscripcion_banco')
        if suscripcion.cambiar_tipo_pago(nuevo_tipo, timezone.now()):
            messages.success(request, f"✅ Solicitud de cambio a {nuevo_tipo} registrada.")
            superadmins = User.objects.filter(roles__tipo='superadmin', roles__activo=True)
            for admin in superadmins:
                crear_notificacion(usuario=admin, tipo='suscripcion', mensaje=f"📩 {user.username} ha solicitado cambiar su tipo de pago a {nuevo_tipo}.",
                    datos={'banco': user.username, 'banco_id': user.id, 'nuevo_tipo': nuevo_tipo}, prioridad='media', categoria='financiera')
            return redirect('roles:panel_suscripcion_banco')
        else:
            messages.warning(request, "❌ Solo puedes solicitar cambio el día anterior al vencimiento.")
            return redirect('roles:panel_suscripcion_banco')
    context = {'suscripcion': suscripcion, 'tipos_pago': SuscripcionBanco.TIPO_PAGO_CHOICES}
    return render(request, 'roles/cambiar_tipo_pago.html', context)

# ============================================================
# VISTA PRINCIPAL DE ASCENSO/DESCENSO DE USUARIOS
# ============================================================
@login_required
def ascender_usuario(request):
    user = request.user
    es_superadmin = user.is_superuser or user.roles.filter(tipo='superadmin', activo=True).exists()
    es_banco = user.roles.filter(tipo='banco', activo=True).exists()

    if not (es_superadmin or es_banco):
        messages.error(request, "No tienes permisos para gestionar usuarios.")
        return redirect('publico:home')

    q = request.GET.get('q', '').strip()
    usuarios_base = User.objects.filter(is_active=True).exclude(id=user.id)

    if es_superadmin:
        usuarios = usuarios_base
        bancos_disponibles = User.objects.filter(roles__tipo='banco', roles__activo=True).distinct()
    elif es_banco:
        comerciales_subordinados_ids = Subordinacion.objects.filter(jefe=user, activo=True).values_list('subordinado_id', flat=True)
        comerciales_subordinados = User.objects.filter(id__in=comerciales_subordinados_ids)
        clientes_sin_gestor = User.objects.filter(roles__tipo='cliente', roles__activo=True).exclude(
            id__in=Subordinacion.objects.filter(activo=True).values_list('subordinado_id', flat=True)
        )
        usuarios = (comerciales_subordinados | clientes_sin_gestor).distinct()
        bancos_disponibles = User.objects.filter(roles__tipo='banco', roles__activo=True).exclude(id=user.id)
    else:
        usuarios = User.objects.none()
        bancos_disponibles = User.objects.none()

    if q:
        usuarios = usuarios.filter(
            Q(username__icontains=q) |
            Q(email__icontains=q) |
            Q(first_name__icontains=q) |
            Q(last_name__icontains=q)
        )

    usuarios = usuarios.order_by('username')

    usuario_seleccionado = None
    rol_actual = None
    acciones_disponibles = []
    recursos_asignados_banco = []
    bancos_asignados = []

    usuario_id = request.GET.get('usuario_id') or request.POST.get('usuario_id')
    if usuario_id and usuario_id.isdigit():
        try:
            usuario_seleccionado = User.objects.get(id=usuario_id)
            if not usuarios.filter(id=usuario_seleccionado.id).exists():
                messages.warning(request, "El usuario seleccionado no está disponible.")
                usuario_seleccionado = None
            else:
                rol_actual = get_rol_usuario(usuario_seleccionado)
                if es_superadmin:
                    if rol_actual == 'cliente':
                        acciones_disponibles = [
                            {'valor': 'comercial', 'label': 'Ascender a Comercial'},
                            {'valor': 'banco', 'label': 'Ascender a Banco'}
                        ]
                    elif rol_actual == 'comercial':
                        acciones_disponibles = [
                            {'valor': 'banco', 'label': 'Ascender a Banco'},
                            {'valor': 'cliente', 'label': 'Descender a Cliente'}
                        ]
                    elif rol_actual == 'banco':
                        acciones_disponibles = [
                            {'valor': 'comercial', 'label': 'Descender a Comercial'},
                            {'valor': 'cliente', 'label': 'Descender a Cliente'}
                        ]
                elif es_banco:
                    if rol_actual == 'cliente':
                        if not Subordinacion.objects.filter(subordinado=usuario_seleccionado, activo=True).exists():
                            acciones_disponibles = [
                                {'valor': 'comercial', 'label': 'Ascender a Comercial'}
                            ]
                        else:
                            messages.warning(request, "Este cliente ya tiene un gestor asignado.")
                    elif rol_actual == 'comercial':
                        if Subordinacion.objects.filter(jefe=user, subordinado=usuario_seleccionado, activo=True).exists():
                            acciones_disponibles = [
                                {'valor': 'cliente', 'label': 'Descender a Cliente'}
                            ]
                        else:
                            messages.warning(request, "Este comercial no es tu subordinado.")

                if rol_actual == 'banco':
                    recursos_asignados_banco = RecursoAsignado.objects.filter(banco=usuario_seleccionado, activo=True)

                if rol_actual == 'comercial':
                    rol_obj = Rol.objects.filter(usuario=usuario_seleccionado, tipo='comercial', activo=True).first()
                    if rol_obj and rol_obj.banco_asignado:
                        bancos_asignados = [rol_obj.banco_asignado]
        except (User.DoesNotExist, ValueError):
            messages.error(request, "Usuario no encontrado.")
            usuario_seleccionado = None

    if request.method == 'POST':
        usuario_id = request.POST.get('usuario_id')
        nuevo_rol = request.POST.get('nuevo_rol')
        banco_asignado_id = request.POST.get('banco_asignado')
        comercial_asignado_id = request.POST.get('comercial_asignado')
        sorteos_seleccionados = request.POST.getlist('sorteos')
        formas_juego_seleccionadas = request.POST.getlist('formas_juego')
        formas_pago_seleccionadas = request.POST.getlist('formas_pago')
        comerciales_permitidos_str = request.POST.get('comerciales_permitidos', '5')

        try:
            usuario = User.objects.get(id=usuario_id)
        except User.DoesNotExist:
            messages.error(request, "Usuario no encontrado.")
            return redirect('roles:ascender_usuario')

        if not usuarios.filter(id=usuario.id).exists():
            messages.error(request, "No tienes permiso para gestionar a este usuario.")
            return redirect('roles:ascender_usuario')

        rol_actual_usuario = get_rol_usuario(usuario)

        if es_banco:
            if usuario.id == user.id:
                messages.error(request, "No puedes cambiar tu propio rol. Contacta a un superadmin.")
                return redirect('roles:ascender_usuario')

            if nuevo_rol == 'comercial':
                if rol_actual_usuario != 'cliente':
                    messages.error(request, "Solo puedes ascender a clientes a comerciales.")
                    return redirect('roles:ascender_usuario')
                if Subordinacion.objects.filter(subordinado=usuario, activo=True).exists():
                    messages.error(request, "Este cliente ya tiene un gestor asignado.")
                    return redirect('roles:ascender_usuario')
                suscripcion = SuscripcionBanco.objects.filter(banco=user, activo=True).first()
                if suscripcion and not suscripcion.puede_ascender_comercial():
                    messages.error(
                        request,
                        f"Has alcanzado el límite de {suscripcion.comerciales_permitidos} comerciales. "
                        "Solicita más cupo al superadmin."
                    )
                    return redirect('roles:ascender_usuario')
            elif nuevo_rol == 'cliente':
                if rol_actual_usuario != 'comercial':
                    messages.error(request, "Solo puedes descender a comerciales a clientes.")
                    return redirect('roles:ascender_usuario')
                if not Subordinacion.objects.filter(jefe=user, subordinado=usuario, activo=True).exists():
                    messages.error(request, "Este comercial no es tu subordinado.")
                    return redirect('roles:ascender_usuario')
            else:
                messages.error(request, "Como banco, solo puedes ascender a comercial o descender a cliente.")
                return redirect('roles:ascender_usuario')

        elif es_superadmin:
            if nuevo_rol not in ['superadmin', 'banco', 'comercial', 'cliente']:
                messages.error(request, "Rol no válido.")
                return redirect('roles:ascender_usuario')
            if nuevo_rol == 'superadmin' and usuario.id == user.id:
                messages.warning(request, "Ya eres superadmin.")
                return redirect('roles:ascender_usuario')
            if banco_asignado_id:
                try:
                    banco = User.objects.get(id=banco_asignado_id)
                    if not banco.roles.filter(tipo='banco', activo=True).exists():
                        messages.error(request, "El usuario seleccionado como banco no tiene ese rol.")
                        return redirect('roles:ascender_usuario')
                except User.DoesNotExist:
                    messages.error(request, "Banco asignado no encontrado.")
                    return redirect('roles:ascender_usuario')

        with transaction.atomic():
            if nuevo_rol == 'banco':
                if rol_actual_usuario == 'comercial':
                    Subordinacion.objects.filter(subordinado=usuario, activo=True).delete()
                    Rol.objects.filter(usuario=usuario, tipo='comercial', activo=True).update(banco_asignado=None)

                Rol.objects.filter(usuario=usuario, activo=True).exclude(tipo='banco').update(activo=False)
                rol_obj, created = Rol.objects.update_or_create(
                    usuario=usuario,
                    tipo='banco',
                    defaults={'activo': True, 'fondo': 0, 'banco_asignado': None}
                )
                logger.info(f"Usuario {usuario.username} ascendido a banco. Rol: {rol_obj}, creado={created}")

                try:
                    comerciales_permitidos = int(comerciales_permitidos_str)
                    if comerciales_permitidos < 0:
                        comerciales_permitidos = 0
                except (ValueError, TypeError):
                    comerciales_permitidos = 5

                suscripcion, created = SuscripcionBanco.objects.get_or_create(
                    banco=usuario,
                    defaults={
                        'fecha_vencimiento': timezone.now() + timedelta(days=30),
                        'activo': True,
                        'tipo_pago': 'mensual',
                        'cuota_fija': 0,
                        'comerciales_permitidos': comerciales_permitidos
                    }
                )
                if not created:
                    suscripcion.comerciales_permitidos = comerciales_permitidos
                    suscripcion.fecha_vencimiento = timezone.now() + timedelta(days=30)
                    suscripcion.activo = True
                    suscripcion.save()
                logger.info(f"Suscripción para {usuario.username}: {suscripcion}")

                # NO auto-asignar recursos. Redirigir para elegirlos manualmente.
                RecursoAsignado.objects.filter(banco=usuario).delete()
                LimiteApuesta.objects.filter(banco=usuario).delete()
                DosisPago.objects.filter(banco=usuario).delete()

                crear_notificacion(
                    usuario=usuario,
                    tipo='info',
                    mensaje=(
                        f"Has sido ascendido a Banco con {comerciales_permitidos} "
                        f"comerciales permitidos. Configura tus sorteos, formas de juego, "
                        f"formas de pago, dosis, limites y sobrelimites."
                    ),
                    datos={
                        'tipo_cambio': 'ascenso_banco',
                        'comerciales_permitidos': comerciales_permitidos,
                        'fecha': timezone.now().isoformat(),
                        'url_detalle': '/roles/gestion-limites-dosis/'
                    },
                    prioridad='alta',
                    categoria='sistema'
                )
                messages.success(
                    request,
                    f"{usuario.username} ascendido a Banco. Ahora configura sus recursos."
                )
                anular_bonos_usuario(usuario)
                logger.info("Redirigiendo a gestion_limites_dosis con banco=" + str(usuario.id))
                return redirect(
                    reverse('roles:gestion_limites_dosis') + "?banco=" + str(usuario.id)
                )

            elif nuevo_rol == 'comercial':
                if rol_actual_usuario == 'banco':
                    SuscripcionBanco.objects.filter(banco=usuario).delete()
                    RecursoAsignado.objects.filter(banco=usuario).delete()
                    reasignar_comerciales_al_descender_banco(usuario)

                Subordinacion.objects.filter(subordinado=usuario, activo=True).delete()

                banco_asignado = None
                if banco_asignado_id:
                    try:
                        banco_asignado = User.objects.get(id=banco_asignado_id)
                        if not banco_asignado.roles.filter(tipo='banco', activo=True).exists():
                            messages.error(request, "El usuario seleccionado como banco no tiene ese rol.")
                            return redirect(f"{reverse('roles:ascender_usuario')}?usuario_id={usuario.id}")
                    except User.DoesNotExist:
                        messages.error(request, "Banco asignado no encontrado.")
                        return redirect(f"{reverse('roles:ascender_usuario')}?usuario_id={usuario.id}")
                elif es_banco:
                    banco_asignado = user

                if banco_asignado:
                    suscripcion = SuscripcionBanco.objects.filter(banco=banco_asignado, activo=True).first()
                    if suscripcion and not suscripcion.puede_ascender_comercial():
                        messages.error(
                            request,
                            f"El banco {banco_asignado.username} ha alcanzado su límite de "
                            f"{suscripcion.comerciales_permitidos} comerciales. "
                            "Debe solicitar más cupo al superadmin."
                        )
                        return redirect(f"{reverse('roles:ascender_usuario')}?usuario_id={usuario.id}")

                Rol.objects.filter(usuario=usuario, activo=True).exclude(tipo='comercial').update(activo=False)
                rol_obj, created = Rol.objects.update_or_create(
                    usuario=usuario,
                    tipo='comercial',
                    defaults={
                        'activo': True,
                        'fondo': 0,
                        'banco_asignado': banco_asignado,
                        'comercial_asignado': None
                    }
                )
                logger.info(f"Usuario {usuario.username} ascendido a comercial. Rol: {rol_obj}, creado={created}")

                if banco_asignado:
                    Subordinacion.objects.get_or_create(
                        jefe=banco_asignado,
                        subordinado=usuario,
                        defaults={'activo': True}
                    )
                    recursos_banco = RecursoAsignado.objects.filter(banco=banco_asignado, activo=True)
                    recursos_comercial_creados = 0
                    for recurso in recursos_banco:
                        RecursoAsignado.objects.get_or_create(
                            banco=None,
                            comercial=usuario,
                            tipo=recurso.tipo,
                            sorteo=recurso.sorteo,
                            forma_juego=recurso.forma_juego,
                            forma_pago=recurso.forma_pago,
                            defaults={'activo': True, 'creado_por': request.user}
                        )
                        recursos_comercial_creados += 1
                    sorteos_ids = recursos_banco.filter(tipo='sorteo').values_list('sorteo_id', flat=True)
                    formas_juego_ids = recursos_banco.filter(tipo='forma_juego').values_list('forma_juego_id', flat=True)
                    formas_pago_ids = recursos_banco.filter(tipo='forma_pago').values_list('forma_pago_id', flat=True)
                    asignar_limites_dosis_predeterminados(
                        usuario=usuario,
                        recursos_sorteos=sorteos_ids,
                        recursos_formas_juego=formas_juego_ids,
                        recursos_formas_pago=formas_pago_ids,
                        banco_origen=banco_asignado
                    )
                    mensaje_recursos = f" con {recursos_comercial_creados} recursos copiados y límites/dosis heredados"
                else:
                    recursos_comercial_creados = 0
                    for sorteo in Sorteo.objects.filter(activo=True):
                        RecursoAsignado.objects.get_or_create(
                            banco=None,
                            comercial=usuario,
                            tipo='sorteo',
                            sorteo=sorteo,
                            defaults={'activo': True, 'creado_por': request.user}
                        )
                        recursos_comercial_creados += 1
                    for forma_juego in FormaJuego.objects.filter(activo=True):
                        RecursoAsignado.objects.get_or_create(
                            banco=None,
                            comercial=usuario,
                            tipo='forma_juego',
                            forma_juego=forma_juego,
                            defaults={'activo': True, 'creado_por': request.user}
                        )
                        recursos_comercial_creados += 1
                    for forma_pago in FormaPago.objects.filter(activo=True):
                        RecursoAsignado.objects.get_or_create(
                            banco=None,
                            comercial=usuario,
                            tipo='forma_pago',
                            forma_pago=forma_pago,
                            defaults={'activo': True, 'creado_por': request.user}
                        )
                        recursos_comercial_creados += 1
                    asignar_limites_dosis_predeterminados(
                        usuario=usuario,
                        recursos_sorteos=Sorteo.objects.filter(activo=True).values_list('id', flat=True),
                        recursos_formas_juego=FormaJuego.objects.filter(activo=True).values_list('id', flat=True),
                        recursos_formas_pago=FormaPago.objects.filter(activo=True).values_list('id', flat=True),
                        banco_origen=None
                    )
                    mensaje_recursos = f" con {recursos_comercial_creados} recursos globales y límites/dosis por defecto"

                crear_notificacion(
                    usuario=usuario,
                    tipo='info',
                    mensaje=(
                        f"✅ Has sido ascendido a Comercial bajo el banco "
                        f"{banco_asignado.username if banco_asignado else 'Superadmin'}{mensaje_recursos}."
                    ),
                    datos={
                        'tipo_cambio': 'ascenso_comercial',
                        'banco_asignado': banco_asignado.username if banco_asignado else 'Superadmin',
                        'fecha': timezone.now().isoformat(),
                        'url_detalle': '/comercial/panel/'
                    },
                    prioridad='alta',
                    categoria='sistema'
                )
                messages.success(
                    request,
                    f"✅ {usuario.username} ascendido a Comercial bajo el banco "
                    f"{banco_asignado.username if banco_asignado else 'Superadmin'}{mensaje_recursos}."
                )

                anular_bonos_usuario(usuario)

                logger.info(f"Redirigiendo a ascender_usuario con usuario_id={usuario.id}")
                return redirect(f"{reverse('roles:ascender_usuario')}?usuario_id={usuario.id}")

            elif nuevo_rol == 'cliente':
                if rol_actual_usuario == 'banco':
                    SuscripcionBanco.objects.filter(banco=usuario).delete()
                    RecursoAsignado.objects.filter(banco=usuario).delete()
                    reasignar_comerciales_al_descender_banco(usuario)
                elif rol_actual_usuario == 'comercial':
                    Subordinacion.objects.filter(subordinado=usuario, activo=True).delete()
                    Rol.objects.filter(usuario=usuario, tipo='comercial', activo=True).update(banco_asignado=None)

                ajustar_fondos_al_descender(usuario)
                Rol.objects.filter(usuario=usuario, activo=True).exclude(tipo='cliente').update(activo=False)
                rol_obj, created = Rol.objects.update_or_create(
                    usuario=usuario,
                    tipo='cliente',
                    defaults={'activo': True, 'fondo': 0, 'banco_asignado': None}
                )
                logger.info(f"Usuario {usuario.username} descendido a cliente. Rol: {rol_obj}, creado={created}")

                crear_notificacion(
                    usuario=usuario,
                    tipo='info',
                    mensaje="⚠️ Has sido descendido a Cliente. Tus fondos son modulares (negativos) y se anularán con recargas.",
                    datos={
                        'tipo_cambio': 'descenso_cliente',
                        'fecha': timezone.now().isoformat(),
                        'url_detalle': '/usuarios/mis-fondos/'
                    },
                    prioridad='alta',
                    categoria='sistema'
                )
                messages.success(
                    request,
                    f"✅ {usuario.username} descendido a Cliente. Fondos ajustados a modulares (negativos)."
                )
                logger.info(f"Redirigiendo a ascender_usuario con usuario_id={usuario.id}")
                return redirect(f"{reverse('roles:ascender_usuario')}?usuario_id={usuario.id}")

    bancos = User.objects.filter(roles__tipo='banco', roles__activo=True).distinct()
    sorteos = Sorteo.objects.filter(activo=True).order_by('nombre')
    formas_juego = FormaJuego.objects.filter(activo=True).order_by('nombre')
    formas_pago = FormaPago.objects.filter(activo=True)

    context = {
        'usuarios': usuarios,
        'q': q,
        'bancos': bancos,
        'sorteos': sorteos,
        'formas_juego': formas_juego,
        'formas_pago': formas_pago,
        'usuario_seleccionado': usuario_seleccionado,
        'rol_actual': rol_actual,
        'acciones_disponibles': acciones_disponibles,
        'recursos_asignados_banco': recursos_asignados_banco,
        'bancos_asignados': bancos_asignados,
        'es_superadmin': es_superadmin,
        'es_banco': es_banco,
    }
    return render(request, 'roles/ascender_usuario.html', context)

@login_required
def descender_a_cliente(request, user_id):
    usuario_a_descender = get_object_or_404(User, id=user_id)
    usuario_actual = request.user
    es_superadmin = usuario_actual.is_superuser or usuario_actual.roles.filter(tipo='superadmin', activo=True).exists()
    es_banco = usuario_actual.roles.filter(tipo='banco', activo=True).exists()
    if not (es_superadmin or es_banco):
        messages.error(request, "No tienes permiso para descender usuarios.")
        return redirect('roles:lista_clientes')
    if es_banco and not es_superadmin:
        if not Subordinacion.objects.filter(jefe=usuario_actual, subordinado=usuario_a_descender, activo=True).exists():
            messages.error(request, "No puedes descender a este usuario porque no está bajo tu supervisión directa.")
            return redirect('roles:lista_clientes')
    rol_comercial = Rol.objects.filter(usuario=usuario_a_descender, tipo='comercial', activo=True).first()
    if not rol_comercial:
        messages.warning(request, f"El usuario {usuario_a_descender.username} no es un comercial activo.")
        return redirect('roles:lista_clientes')
    with transaction.atomic():
        Subordinacion.objects.filter(subordinado=usuario_a_descender, activo=True).delete()
        rol_comercial.banco_asignado = None
        rol_comercial.save(update_fields=['banco_asignado'])
        RecursoAsignado.objects.filter(comercial=usuario_a_descender).delete()
        LimiteApuesta.objects.filter(comercial=usuario_a_descender).delete()
        DosisPago.objects.filter(comercial=usuario_a_descender).delete()
        Rol.objects.filter(usuario=usuario_a_descender, activo=True).exclude(tipo='cliente').update(activo=False)
        Rol.objects.update_or_create(usuario=usuario_a_descender, tipo='cliente', defaults={'activo': True, 'fondo': 0})
        ajustar_fondos_al_descender(usuario_a_descender)
        crear_notificacion(
            usuario=usuario_a_descender,
            tipo='info',
            mensaje=f"⚠️ Has sido descendido a Cliente por {usuario_actual.username}. Tus fondos son modulares (negativos).",
            datos={'tipo_cambio': 'descenso_cliente', 'fecha': timezone.now().isoformat()},
            prioridad='alta',
            categoria='sistema'
        )
        if es_banco:
            crear_notificacion(
                usuario=usuario_actual,
                tipo='info',
                mensaje=f"✅ Has descendido a {usuario_a_descender.username} a Cliente.",
                datos={'usuario': usuario_a_descender.username},
                prioridad='media',
                categoria='sistema'
            )
    messages.success(request, f"✅ {usuario_a_descender.username} ha sido descendido a Cliente.")
    return redirect('roles:estructura_global')

@login_required
def estructura_global(request):
    user = request.user
    es_superadmin = user.is_superuser or user.roles.filter(tipo='superadmin', activo=True).exists()
    es_banco = user.roles.filter(tipo='banco', activo=True).exists()
    es_comercial = user.roles.filter(tipo='comercial', activo=True).exists()
    if not (es_superadmin or es_banco or es_comercial):
        messages.info(request, "No tienes permiso para ver la estructura organizacional.")
        return redirect('usuarios:perfil_cliente')

    estructura = []
    if es_superadmin:
        bancos = User.objects.filter(roles__tipo='banco', roles__activo=True).distinct()
        for banco in bancos:
            comerciales_ids = Subordinacion.objects.filter(jefe=banco, activo=True).values_list('subordinado_id', flat=True)
            comerciales = User.objects.filter(id__in=comerciales_ids, is_active=True)
            comerciales_data = []
            for comercial in comerciales:
                clientes_ids = Fondo.objects.filter(asignado_por=comercial, activo=True).values_list('usuario_id', flat=True).distinct()
                clientes = User.objects.filter(id__in=clientes_ids, is_active=True)
                total_fondos = Fondo.objects.filter(usuario__in=clientes_ids, activo=True).aggregate(total=Sum('monto'))['total'] or 0
                comerciales_data.append({'usuario': comercial, 'clientes': clientes, 'total_fondos': total_fondos})
            clientes_directos_ids = Fondo.objects.filter(asignado_por=banco, activo=True).values_list('usuario_id', flat=True).distinct()
            clientes_directos = User.objects.filter(id__in=clientes_directos_ids, is_active=True)
            total_fondos_banco = Fondo.objects.filter(usuario__in=clientes_directos_ids, activo=True).aggregate(total=Sum('monto'))['total'] or 0
            estructura.append({'tipo': 'banco', 'usuario': banco, 'comerciales': comerciales_data, 'clientes_directos': clientes_directos, 'total_fondos': total_fondos_banco})
    elif es_banco:
        comerciales_ids = Subordinacion.objects.filter(jefe=user, activo=True).values_list('subordinado_id', flat=True)
        comerciales = User.objects.filter(id__in=comerciales_ids, is_active=True)
        comerciales_data = []
        for comercial in comerciales:
            clientes_ids = Fondo.objects.filter(asignado_por=comercial, activo=True).values_list('usuario_id', flat=True).distinct()
            clientes = User.objects.filter(id__in=clientes_ids, is_active=True)
            total_fondos = Fondo.objects.filter(usuario__in=clientes_ids, activo=True).aggregate(total=Sum('monto'))['total'] or 0
            comerciales_data.append({'usuario': comercial, 'clientes': clientes, 'total_fondos': total_fondos})
        clientes_directos_ids = Fondo.objects.filter(asignado_por=user, activo=True).values_list('usuario_id', flat=True).distinct()
        clientes_directos = User.objects.filter(id__in=clientes_directos_ids, is_active=True)
        total_fondos_banco = Fondo.objects.filter(usuario__in=clientes_directos_ids, activo=True).aggregate(total=Sum('monto'))['total'] or 0
        estructura.append({'tipo': 'banco', 'usuario': user, 'comerciales': comerciales_data, 'clientes_directos': clientes_directos, 'total_fondos': total_fondos_banco})
    elif es_comercial:
        clientes_ids = Fondo.objects.filter(asignado_por=user, activo=True).values_list('usuario_id', flat=True).distinct()
        clientes = User.objects.filter(id__in=clientes_ids, is_active=True)
        total_fondos = Fondo.objects.filter(usuario__in=clientes_ids, activo=True).aggregate(total=Sum('monto'))['total'] or 0
        estructura.append({'tipo': 'comercial', 'usuario': user, 'clientes': clientes, 'total_fondos': total_fondos})

    context = {
        'estructura': estructura,
        'es_superadmin': es_superadmin,
        'es_banco': es_banco,
        'es_comercial': es_comercial,
    }
    return render(request, 'roles/estructura_global.html', context)

# ============================================================
# ASIGNAR RECURSOS (BANCO)
# ============================================================
@login_required
def asignar_recursos_banco(request):
    user = request.user
    if not user.roles.filter(tipo='banco', activo=True).exists():
        messages.error(request, "No eres un banco.")
        return redirect('publico:home')

    comerciales_ids = Subordinacion.objects.filter(jefe=user, activo=True).values_list('subordinado_id', flat=True)
    comerciales = User.objects.filter(id__in=comerciales_ids, roles__tipo='comercial', roles__activo=True).distinct()

    recursos_sorteo_qs = get_recursos_visibles(user, 'sorteo').filter(sorteo__isnull=False).select_related('sorteo')
    recursos_forma_juego_qs = get_recursos_visibles(user, 'forma_juego').filter(forma_juego__isnull=False).select_related('forma_juego')
    recursos_forma_pago_qs = get_recursos_visibles(user, 'forma_pago').filter(forma_pago__isnull=False).select_related('forma_pago')

    sorteos = [r.sorteo for r in recursos_sorteo_qs]
    formas_juego = [r.forma_juego for r in recursos_forma_juego_qs]
    formas_pago = [r.forma_pago for r in recursos_forma_pago_qs]

    if request.method == 'POST':
        # Aquí iría la lógica de asignación de recursos (si se necesita)
        pass

    comercial_id = request.GET.get('comercial')
    recursos_asignados = RecursoAsignado.objects.none()
    if comercial_id:
        comercial = get_object_or_404(User, id=comercial_id)
        recursos_asignados = RecursoAsignado.objects.filter(comercial=comercial, activo=True)

    context = {
        'comerciales': comerciales,
        'sorteos': sorteos,
        'formas_juego': formas_juego,
        'formas_pago': formas_pago,
        'recursos_asignados': recursos_asignados,
        'comercial_seleccionado': comercial_id,
    }
    return render(request, 'roles/asignar_recursos.html', context)

@login_required
def lista_clientes(request):
    """FIX_LISTA_CLIENTES_V2: lista con fondos por FP, online/offline, KPIs y filtros."""
    user = request.user
    rol = get_rol_usuario(user)
    es_superadmin = user.is_superuser or rol == 'superadmin'
    es_banco = rol == 'banco'
    es_comercial = rol == 'comercial'

    if not (es_superadmin or es_banco or es_comercial):
        messages.info(request, "Los clientes no tienen acceso a la lista de clientes.")
        return redirect('jugadas:mis_apuestas')

    # ─── Base de clientes ───
    if es_superadmin:
        clientes = User.objects.filter(is_active=True).order_by('username')
    elif es_banco:
        comerciales_ids = Subordinacion.objects.filter(jefe=user, activo=True).values_list('subordinado_id', flat=True)
        clientes_ids = Fondo.objects.filter(asignado_por__in=comerciales_ids, activo=True).values_list('usuario_id', flat=True).distinct()
        clientes_directos = Fondo.objects.filter(asignado_por=user, activo=True).values_list('usuario_id', flat=True).distinct()
        clientes = User.objects.filter(
            Q(id__in=clientes_ids) | Q(id__in=clientes_directos) | Q(id__in=comerciales_ids),
            is_active=True
        ).order_by('username')
    else:  # comercial
        clientes_ids = Fondo.objects.filter(asignado_por=user, activo=True).values_list('usuario_id', flat=True).distinct()
        clientes = User.objects.filter(id__in=clientes_ids, is_active=True).order_by('username')

    # ─── Filtros ───
    q = (request.GET.get('q') or '').strip()
    if q:
        clientes = clientes.filter(
            Q(username__icontains=q) | Q(email__icontains=q) |
            Q(first_name__icontains=q) | Q(last_name__icontains=q) |
            Q(perfil__telefono__icontains=q)
        ).distinct()

    rol_filtro = (request.GET.get('rol') or '').strip()
    if rol_filtro:
        clientes = clientes.filter(roles__tipo=rol_filtro, roles__activo=True)

    estado_filtro = (request.GET.get('estado') or '').strip()

    # ─── Paginación ───
    paginator = Paginator(clientes, 20)
    clientes_page = paginator.get_page(request.GET.get('page'))

    # ─── Enriquecer con fondos, online, rol ───
    UMBRAL_ONLINE = timezone.now() - timedelta(minutes=1)
    clientes_data = []

    for cliente in clientes_page:
        rol_obj = cliente.roles.filter(activo=True).first()
        tipo = rol_obj.tipo if rol_obj else ('superadmin' if cliente.is_superuser else 'cliente')

        # Filtro por estado (después de calcular)
        online = bool(cliente.last_login and cliente.last_login >= UMBRAL_ONLINE)
        if estado_filtro == 'online' and not online:
            continue
        if estado_filtro == 'offline' and online:
            continue

        # Fondos según rol del que mira
        if es_superadmin:
            fondos_qs = Fondo.objects.filter(usuario=cliente, activo=True).select_related('forma_pago')
        elif tipo in ('comercial', 'banco'):
            fondos_qs = Fondo.objects.none()  # no se muestran fondos de gestores
        else:
            fondos_qs = Fondo.objects.filter(
                usuario=cliente, asignado_por=user, activo=True
            ).select_related('forma_pago')

        fondos_dict = {}
        total_fondos = 0.0
        for f in fondos_qs:
            fp_nombre = f.forma_pago.nombre if f.forma_pago else 'Sin FP'
            monto = float(f.monto or 0)
            fondos_dict[fp_nombre] = fondos_dict.get(fp_nombre, 0) + monto
            total_fondos += monto

        clientes_data.append({
            'cliente': cliente,
            'tipo': tipo,
            'telefono': getattr(getattr(cliente, 'perfil', None), 'telefono', '') or '',
            'online': online,
            'fondos': fondos_dict,
            'total_fondos': total_fondos,
            'mostrar_fondos': tipo == 'cliente',
        })

    # ─── KPIs (sobre el total sin paginar) ───
    todos_los_ids = list(clientes.values_list('id', flat=True))
    todos = User.objects.filter(id__in=todos_los_ids)
    total_clientes = todos.count()
    total_online = todos.filter(last_login__gte=UMBRAL_ONLINE).count()
    total_offline = total_clientes - total_online

    # Fondo total asignado (solo de clientes, según rol)
    if es_superadmin:
        fondos_totales = Fondo.objects.filter(usuario__in=todos_los_ids, activo=True)
    else:
        fondos_totales = Fondo.objects.filter(usuario__in=todos_los_ids, asignado_por=user, activo=True)
    monto_total_asignado = fondos_totales.aggregate(t=Sum('monto'))['t'] or 0

    context = {
        'clientes': clientes_page,
        'clientes_data': clientes_data,
        'total_clientes': total_clientes,
        'total_online': total_online,
        'total_offline': total_offline,
        'monto_total_asignado': float(monto_total_asignado),
        'rol': rol,
        'es_superadmin': es_superadmin,
        'es_banco': es_banco,
        'es_comercial': es_comercial,
        'filtros': {
            'q': q,
            'rol': rol_filtro,
            'estado': estado_filtro,
        },
        'now': timezone.now(),
    }
    return render(request, 'roles/lista_clientes.html', context)


# ============================================================
# SOBRE LÍMITES – PANEL Y GESTIÓN
# ============================================================
@login_required
def panel_sobrelimites(request):
    user = request.user
    es_comercial = user.roles.filter(tipo='comercial', activo=True).exists()
    es_banco = user.roles.filter(tipo='banco', activo=True).exists()
    es_superadmin = user.is_superuser or user.roles.filter(tipo='superadmin', activo=True).exists()
    if es_superadmin:
        sobrelimites = Sobrelimite.objects.all().select_related('jugada', 'comercial', 'banco')
    elif es_banco:
        comerciales_ids = Subordinacion.objects.filter(jefe=user, activo=True).values_list('subordinado_id', flat=True)
        sobrelimites = Sobrelimite.objects.filter(Q(comercial__in=comerciales_ids) | Q(banco_solicitado=user)).select_related('jugada', 'comercial', 'banco')
    elif es_comercial:
        sobrelimites = Sobrelimite.objects.filter(comercial=user).select_related('jugada', 'banco')
    else:
        messages.error(request, "No tienes permisos para ver este panel.")
        return redirect('publico:home')
    estado = request.GET.get('estado')
    if estado:
        sobrelimites = sobrelimites.filter(estado_compensacion=estado)
    sobrelimites = sobrelimites.order_by('-fecha')
    paginator = Paginator(sobrelimites, 15)
    page = request.GET.get('page')
    sobrelimites_page = paginator.get_page(page)
    bancos_disponibles = []
    if es_banco or es_superadmin:
        bancos_disponibles = User.objects.filter(roles__tipo='banco', roles__activo=True).distinct().exclude(id=user.id)
    context = {'sobrelimites': sobrelimites_page, 'es_comercial': es_comercial, 'es_banco': es_banco, 'es_superadmin': es_superadmin, 'bancos_disponibles': bancos_disponibles, 'estado_seleccionado': estado}
    return render(request, 'roles/panel_sobrelimites.html', context)

@login_required
def gestionar_sobrelimite(request, sobrelimite_id, accion):
    messages.warning(request, "Función gestionar_sobrelimite deshabilitada temporalmente.")
    return redirect('publico:home')

@login_required
def solicitar_compensacion_sobrelimite(request, sobrelimite_id):
    if request.method != 'POST':
        messages.error(request, "Método no permitido.")
        return redirect('roles:panel_sobrelimites')
    sobrelimite = get_object_or_404(Sobrelimite, id=sobrelimite_id)
    user = request.user
    banco_id = request.POST.get('banco_id')
    if not banco_id:
        messages.error(request, "Debes seleccionar un banco para solicitar compensación.")
        return redirect('roles:panel_sobrelimites')
    es_superadmin = user.is_superuser or user.roles.filter(tipo='superadmin', activo=True).exists()
    es_banco = user.roles.filter(tipo='banco', activo=True).exists()
    if not (es_banco or es_superadmin):
        messages.error(request, "No tienes permisos para solicitar compensación.")
        return redirect('roles:panel_sobrelimites')
    if sobrelimite.estado_compensacion != 'pendiente':
        messages.warning(request, f"Este sobrelímite ya está {sobrelimite.get_estado_compensacion_display()}.")
        return redirect('roles:panel_sobrelimites')
    try:
        banco = User.objects.get(id=int(banco_id))
        if banco == user:
            messages.error(request, "No puedes solicitar compensación a ti mismo.")
            return redirect('roles:panel_sobrelimites')
        if not banco.roles.filter(tipo='banco', activo=True).exists() and not banco.is_superuser:
            messages.error(request, "El usuario seleccionado no es un banco válido.")
            return redirect('roles:panel_sobrelimites')
    except (ValueError, User.DoesNotExist):
        messages.error(request, "Banco no encontrado.")
        return redirect('roles:panel_sobrelimites')
    sobrelimite.banco_solicitado = banco
    sobrelimite.estado_compensacion = 'pendiente'
    sobrelimite.save()
    crear_notificacion(usuario=banco, tipo='sobrelimite', mensaje=f"📩 {user.username} te ha solicitado compensación para el sobrelímite de {sobrelimite.jugada.usuario.username} en {sobrelimite.jugada.sorteo.nombre}. Exceso: ${sobrelimite.monto_excedido:.2f}.",
        datos={'sobrelimite_id': sobrelimite.id, 'solicitante': user.username, 'solicitante_id': user.id, 'cliente': sobrelimite.jugada.usuario.username, 'sorteo': sobrelimite.jugada.sorteo.nombre, 'monto_excedido': float(sobrelimite.monto_excedido), 'url_detalle': '/roles/panel-sobrelimites/'},
        prioridad='urgente', categoria='sobrelimite')
    crear_notificacion(usuario=user, tipo='sobrelimite', mensaje=f"📩 Has solicitado compensación a {banco.username}.", datos={'sobrelimite_id': sobrelimite.id, 'banco_solicitado': banco.username}, prioridad='media', categoria='sobrelimite')
    messages.success(request, f"✅ Solicitud de compensación enviada a {banco.username}.")
    return redirect('roles:panel_sobrelimites')

@login_required
def responder_compensacion_sobrelimite(request, sobrelimite_id, accion):
    if accion not in ['aceptar', 'rechazar']:
        messages.error(request, "Acción no válida.")
        return redirect('roles:panel_sobrelimites')

    sobrelimite = get_object_or_404(Sobrelimite, id=sobrelimite_id)
    user = request.user
    es_superadmin = user.is_superuser or user.roles.filter(tipo='superadmin', activo=True).exists()

    if not es_superadmin and sobrelimite.banco_solicitado != user:
        messages.error(request, "No tienes permiso para responder a esta solicitud.")
        return redirect('roles:panel_sobrelimites')

    if sobrelimite.estado_compensacion != 'pendiente':
        messages.warning(request, f"Esta solicitud ya está {sobrelimite.get_estado_compensacion_display()}.")
        return redirect('roles:panel_sobrelimites')

    jugada = sobrelimite.jugada
    monto_original = jugada.monto

    if accion == 'aceptar':
        with transaction.atomic():
            fondos_banco = Fondo.objects.filter(usuario=user, activo=True)
            saldo_banco = sum(f.monto for f in fondos_banco)
            if saldo_banco < monto_original:
                Deuda.objects.create(
                    usuario=sobrelimite.banco_solicitado,
                    acreedor=user,
                    forma_pago=jugada.forma_pago,
                    monto_original=monto_original,
                    saldo_pendiente=monto_original,
                    origen=f"Compensación sobrelímite - Jugada #{jugada.id}",
                    creado_por=user,
                    metadata={'sobrelimite_id': sobrelimite.id, 'jugada_id': jugada.id}
                )
                messages.warning(request, f"El banco {user.username} no tiene saldo suficiente.")

            success, msg = descontar_monto(jugada.usuario, monto_original)
            if not success:
                Deuda.objects.create(
                    usuario=jugada.usuario,
                    acreedor=sobrelimite.comercial or user,
                    forma_pago=jugada.forma_pago,
                    monto_original=monto_original,
                    saldo_pendiente=monto_original,
                    origen=f"Sobrelímite compensado - Jugada #{jugada.id}",
                    creado_por=user,
                    metadata={'sobrelimite_id': sobrelimite.id, 'jugada_id': jugada.id}
                )

            jugada.estado = 'confirmada'
            jugada.autorizada_por = user
            jugada.sobrelimite = True
            jugada.save()

            sobrelimite.estado_compensacion = 'aceptado'
            sobrelimite.fecha_compensacion = timezone.now()
            sobrelimite.monto_compensado = monto_original
            sobrelimite.save()

            crear_notificacion(
                usuario=jugada.usuario,
                tipo='sobrelimite',
                mensaje=f"✅ Tu jugada en {jugada.sorteo.nombre} por ${monto_original:.2f} ha sido autorizada por compensación del banco {user.username}.",
                datos={'jugada_id': jugada.id, 'monto': float(monto_original), 'sorteo': jugada.sorteo.nombre},
                prioridad='alta',
                categoria='sobrelimite'
            )

            if sobrelimite.banco_solicitado:
                crear_notificacion(
                    usuario=sobrelimite.banco_solicitado,
                    tipo='sobrelimite',
                    mensaje=f"✅ {user.username} ha aceptado la compensación.",
                    datos={'sobrelimite_id': sobrelimite.id, 'banco': user.username},
                    prioridad='alta',
                    categoria='sobrelimite'
                )

            messages.success(request, f"✅ Compensación aceptada. Jugada #{jugada.id} confirmada.")

    else:  # accion == 'rechazar'
        sobrelimite.estado_compensacion = 'rechazado'
        sobrelimite.fecha_compensacion = timezone.now()
        sobrelimite.save()

        crear_notificacion(
            usuario=sobrelimite.banco_solicitado,
            tipo='sobrelimite',
            mensaje=f"❌ {user.username} ha rechazado la compensación.",
            datos={'sobrelimite_id': sobrelimite.id, 'banco': user.username},
            prioridad='alta',
            categoria='sobrelimite'
        )

        messages.warning(request, f"❌ Compensación rechazada por {user.username}.")

    return redirect('roles:panel_sobrelimites')

# ============================================================
# VISTAS DE VÍAS DE PAGO (GESTORES)
# ============================================================
@login_required
def mis_vias_pago(request):
    user = request.user
    es_gestor = user.roles.filter(tipo__in=['comercial', 'banco', 'superadmin'], activo=True).exists() or user.is_superuser
    if not es_gestor:
        messages.error(request, "No tienes permiso para gestionar vías de pago.")
        return redirect('publico:home')

    vias = ViaPago.objects.filter(gestor=user).select_related('forma_pago').order_by('forma_pago__nombre', 'nombre')
    vias_por_forma = {}
    for via in vias:
        key = via.forma_pago.id
        if key not in vias_por_forma:
            vias_por_forma[key] = {'forma_pago': via.forma_pago, 'vias': []}
        vias_por_forma[key]['vias'].append(via)

    context = {
        'vias_por_forma': vias_por_forma.values(),
        'vias_activas': vias.filter(activo=True).count(),
        'total_vias': vias.count(),
    }
    return render(request, 'roles/mis_vias_pago.html', context)

@login_required
def agregar_via_pago(request):
    user = request.user
    es_gestor = user.roles.filter(tipo__in=['comercial', 'banco', 'superadmin'], activo=True).exists() or user.is_superuser
    if not es_gestor:
        messages.error(request, "No tienes permiso para agregar vías de pago.")
        return redirect('publico:home')

    if request.method == 'POST':
        form = ViaPagoForm(request.POST, gestor=user)
        if form.is_valid():
            via = form.save()
            messages.success(request, f"✅ Vía de pago '{via.nombre}' agregada correctamente.")
            return redirect('roles:mis_vias_pago')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"❌ {field}: {error}")
    else:
        form = ViaPagoForm(gestor=user)

    context = {'form': form}
    return render(request, 'roles/agregar_via_pago.html', context)

@login_required
def editar_via_pago(request, via_id):
    user = request.user
    via = get_object_or_404(ViaPago, id=via_id, gestor=user)

    if request.method == 'POST':
        form = ViaPagoForm(request.POST, instance=via, gestor=user)
        if form.is_valid():
            via = form.save()
            messages.success(request, f"✅ Vía de pago '{via.nombre}' actualizada correctamente.")
            return redirect('roles:mis_vias_pago')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"❌ {field}: {error}")
    else:
        form = ViaPagoForm(instance=via, gestor=user)

    context = {
        'form': form,
        'via': via,
        'tipos': ViaPago.TIPO_CHOICES,
        'direcciones': ViaPago.DIRECCION_CHOICES,
    }
    return render(request, 'roles/editar_via_pago.html', context)

@login_required
def eliminar_via_pago(request, via_id):
    user = request.user
    via = get_object_or_404(ViaPago, id=via_id, gestor=user)

    if request.method == 'POST':
        via.activo = False
        via.save()
        messages.success(request, f"✅ Vía de pago '{via.nombre}' desactivada correctamente.")
        return redirect('roles:mis_vias_pago')

    context = {'via': via}
    return render(request, 'roles/eliminar_via_pago.html', context)

# ============================================================
# VISTAS UNIFICADAS DE SOLICITUDES
# ============================================================
@login_required
def _solicitar_retiro_view(request, user):
    """
    Vista helper para el flujo de retiro de saldo.
    El cliente indica: gestor, forma de pago, monto, y datos de SU vía (a dónde recibir).
    """
    from django.db.models import Sum

    # Cargar gestores con los que el cliente tiene fondos
    gestores_ids = (
        Fondo.objects.filter(usuario=user, activo=True)
        .exclude(asignado_por__isnull=True)
        .values_list('asignado_por_id', flat=True)
        .distinct()
    )
    gestores = User.objects.filter(id__in=gestores_ids, is_active=True).distinct()

    # Cargar formas de pago donde el cliente tiene saldo
    formas_pago_saldo = []
    for fp in FormaPago.objects.filter(activo=True).order_by('nombre'):
        total = Fondo.objects.filter(
            usuario=user, forma_pago=fp, activo=True
        ).aggregate(t=Sum('monto'))['t'] or 0
        if total > 0:
            formas_pago_saldo.append({
                'forma_pago': fp,
                'saldo': float(total),
            })

    if not gestores.exists():
        messages.warning(request, "No tienes gestores con fondos asignados para retirar.")
        return redirect('publico:home')

    if not formas_pago_saldo:
        messages.warning(request, "No tienes saldo en ninguna forma de pago para retirar.")
        return redirect('publico:home')

    if request.method == 'POST':
        gestor_id = request.POST.get('gestor')
        forma_pago_id = request.POST.get('forma_pago')
        monto_str = request.POST.get('monto')
        mensaje = request.POST.get('mensaje', '')

        try:
            gestor = User.objects.get(id=gestor_id, is_active=True)
        except User.DoesNotExist:
            messages.error(request, "Gestor no encontrado.")
            return redirect('roles:solicitar', tipo='retiro')

        try:
            forma_pago = FormaPago.objects.get(id=forma_pago_id, activo=True)
        except FormaPago.DoesNotExist:
            messages.error(request, "Forma de pago no válida.")
            return redirect('roles:solicitar', tipo='retiro')

        try:
            monto = Decimal(monto_str)
            if monto <= 0:
                raise ValueError()
        except Exception:
            messages.error(request, "Monto inválido.")
            return redirect('roles:solicitar', tipo='retiro')

        # Validar saldo con ese gestor + forma de pago
        total_fondos = Fondo.objects.filter(
            usuario=user, asignado_por=gestor,
            forma_pago=forma_pago, activo=True
        ).aggregate(t=Sum('monto'))['t'] or Decimal('0')

        if total_fondos <= 0:
            messages.error(request, f"No tienes saldo con {gestor.username} en {forma_pago.nombre}.")
            return redirect('roles:solicitar', tipo='retiro')

        if total_fondos < monto:
            messages.error(request, f"Saldo insuficiente. Disponible: ${total_fondos} en {forma_pago.nombre}.")
            return redirect('roles:solicitar', tipo='retiro')

        # Recoger datos de la vía del cliente
        datos_via = {}
        nombre_fp = forma_pago.nombre.lower()

        if nombre_fp in ('tarjeta', 'clásica', 'clasica', 'mlc'):
            num_tarjeta = (request.POST.get('numero_tarjeta') or '').strip()
            telefono_via = (request.POST.get('telefono_via') or '').strip()
            if not num_tarjeta or not telefono_via:
                messages.error(request, "Para esta forma de pago debes indicar número de tarjeta y teléfono.")
                return redirect('roles:solicitar', tipo='retiro')
            digitos = num_tarjeta.replace(' ', '').replace('-', '')
            if not digitos.isdigit() or len(digitos) != 16:
                messages.error(request, "El número de tarjeta debe tener 16 dígitos.")
                return redirect('roles:solicitar', tipo='retiro')
            datos_via = {
                'numero_tarjeta': ' '.join(digitos[i:i+4] for i in range(0, 16, 4)),
                'telefono': telefono_via,
            }
        elif nombre_fp in ('saldo móvil', 'saldo movil', 'monedero', 'zelle'):
            telefono_via = (request.POST.get('telefono_via') or '').strip()
            if not telefono_via:
                messages.error(request, "Para esta forma de pago debes indicar un teléfono.")
                return redirect('roles:solicitar', tipo='retiro')
            datos_via = {'telefono': telefono_via}

        solicitud = SolicitudRetiro.objects.create(
            cliente=user,
            gestor=gestor,
            forma_pago=forma_pago,
            monto=monto,
            estado='pendiente',
            mensaje_cliente=mensaje,
            datos_via_cliente=datos_via,
            motivo_tipo=request.POST.get('motivo_tipo', 'cobro_premios'),
            motivo_detalle=request.POST.get('motivo_detalle', '').strip(),
        )
        try:
            from .utils import crear_notificacion as _cn
            _cn(
                usuario=gestor,
                tipo='pago',
                mensaje=f"📩 {user.username} ha solicitado un retiro de ${monto} en {forma_pago.nombre}.",
                datos={
                    'solicitud_id': solicitud.id,
                    'cliente': user.username,
                    'cliente_id': user.id,
                    'monto': float(monto),
                    'forma_pago': forma_pago.nombre,
                    'datos_via': datos_via,
                    'url_detalle': '/roles/gestionar-solicitudes/retiro/',
                },
                prioridad='alta',
                categoria='financiera'
            )
        except Exception:
            pass

        messages.success(request, f"✅ Solicitud de retiro de ${monto} enviada a {gestor.username}.")
        return redirect('roles:mis_solicitudes_todas')

    context = {
        'tipo': 'retiro',
        'gestores': gestores,
        'formas_pago_saldo': formas_pago_saldo,
    }
    return render(request, 'roles/solicitar_retiro.html', context)


@login_required
def solicitar(request, tipo):
    user = request.user
    es_cliente = user.roles.filter(tipo='cliente', activo=True).exists()
    es_comercial = user.roles.filter(tipo='comercial', activo=True).exists()

    gestores_data = []
    formas_pago = []
    gestores = User.objects.none()

    if tipo in ['recarga', 'cobro', 'prestamo', 'retiro'] and not es_cliente:
        messages.error(request, f"No puedes solicitar {tipo} porque no eres cliente.")
        return redirect('publico:home')

    if tipo == 'retiro':
        return _solicitar_retiro_view(request, user)

    if tipo == 'fondos' and not es_comercial:
        messages.error(request, "Solo los comerciales pueden solicitar fondos.")
        return redirect('publico:home')

    gestores_ids = set()
    if tipo in ['recarga', 'cobro']:
        comerciales = User.objects.filter(roles__tipo='comercial', roles__activo=True)
        bancos = User.objects.filter(roles__tipo='banco', roles__activo=True)
        superadmins = User.objects.filter(roles__tipo='superadmin', roles__activo=True)
        for user_obj in comerciales:
            gestores_ids.add(user_obj.id)
        for user_obj in bancos:
            gestores_ids.add(user_obj.id)
        for user_obj in superadmins:
            gestores_ids.add(user_obj.id)
    elif tipo == 'prestamo':
        subordinacion = Subordinacion.objects.filter(subordinado=user, activo=True).first()
        comercial = subordinacion.jefe if subordinacion else None
        if not comercial:
            messages.error(request, "No tienes un comercial asignado. No puedes solicitar préstamos.")
            return render(request, 'roles/solicitar.html', {'tipo': tipo, 'no_gestor': True})
        otros_clientes_ids = Subordinacion.objects.filter(jefe=comercial, activo=True).exclude(
            subordinado=user
        ).values_list('subordinado_id', flat=True)
        clientes_con_fondos = Fondo.objects.filter(
            usuario__in=otros_clientes_ids,
            asignado_por=comercial,
            activo=True,
            monto__gt=0
        ).values_list('usuario_id', flat=True).distinct()
        superadmins = User.objects.filter(roles__tipo='superadmin', roles__activo=True).values_list('id', flat=True)
        gestores_ids = set(list(clientes_con_fondos) + list(superadmins))
        if user.id in gestores_ids:
            gestores_ids.remove(user.id)
    elif tipo == 'fondos':
        banco = get_banco_asignado(user)
        if banco:
            gestores_ids.add(banco.id)
        superadmins = User.objects.filter(roles__tipo='superadmin', roles__activo=True)
        for sa in superadmins:
            gestores_ids.add(sa.id)

    gestores = User.objects.filter(id__in=gestores_ids, is_active=True).distinct()
    if not gestores.exists():
        messages.warning(request, f"No tienes gestores disponibles para {tipo}.")
        return redirect('publico:home')

    if tipo in ['recarga', 'cobro']:
        for gestor in gestores:
            vias_pago = ViaPago.objects.filter(
                gestor=gestor,
                activo=True
            ).exclude(
                forma_pago__in=[2, 6]
            ).order_by('forma_pago__nombre')
            if vias_pago.exists():
                vias_json = []
                for via in vias_pago:
                    vias_json.append({
                        'id': via.id,
                        'forma_pago_id': via.forma_pago.id,
                        'forma_pago_nombre': via.forma_pago.nombre,
                        'nombre': via.nombre,
                        'numero': via.numero,
                    })
                gestores_data.append({
                    'gestor': gestor,
                    'vias_pago': vias_pago,
                    'vias_json': vias_json,
                })
        if not gestores_data:
            messages.warning(request, f"Tus gestores no tienen vías de pago configuradas para {tipo}.")
            return redirect('publico:home')
        formas_pago = FormaPago.objects.filter(activo=True)

    if request.method == 'POST':
        gestor_id = request.POST.get('gestor')
        monto_str = request.POST.get('monto')
        mensaje = request.POST.get('mensaje', '')

        try:
            gestor = User.objects.get(id=gestor_id, is_active=True)
        except User.DoesNotExist:
            messages.error(request, "Gestor no encontrado.")
            return redirect(f"{reverse('roles:solicitar', args=[tipo])}")

        try:
            monto = Decimal(monto_str)
            if monto <= 0:
                raise ValueError("El monto debe ser mayor a 0")
        except:
            messages.error(request, "Monto inválido.")
            return redirect(f"{reverse('roles:solicitar', args=[tipo])}")

        if tipo == 'recarga':
            forma_pago_id = request.POST.get('forma_pago')
            try:
                forma_pago = FormaPago.objects.get(id=forma_pago_id, activo=True)
            except FormaPago.DoesNotExist:
                messages.error(request, "Forma de pago no válida.")
                return redirect(f"{reverse('roles:solicitar', args=[tipo])}")
            if forma_pago.id in [2, 6]:
                messages.error(request, "No se puede procesar con esta forma de pago.")
                return redirect(f"{reverse('roles:solicitar', args=[tipo])}")

            solicitud = SolicitudRecarga.objects.create(
                cliente=user,
                gestor=gestor,
                forma_pago=forma_pago,
                monto=monto,
                estado='pendiente',
                mensaje_cliente=mensaje,
                creado_por=user
            )
            crear_notificacion(
                usuario=gestor,
                tipo='recarga',
                mensaje=f"📩 {user.username} ha solicitado una recarga de ${monto} en {forma_pago.nombre}.",
                datos={
                    'solicitud_id': solicitud.id,
                    'cliente': user.username,
                    'cliente_id': user.id,
                    'monto': float(monto),
                    'forma_pago': forma_pago.nombre,
                    'url_detalle': '/roles/gestionar-solicitudes/'
                },
                prioridad='alta',
                categoria='financiera'
            )
            messages.success(request, f"✅ Solicitud de recarga de ${monto} enviada a {gestor.username}.")

        elif tipo == 'cobro':
            forma_pago_id = request.POST.get('forma_pago')
            try:
                forma_pago = FormaPago.objects.get(id=forma_pago_id, activo=True)
            except FormaPago.DoesNotExist:
                messages.error(request, "Forma de pago no válida.")
                return redirect(f"{reverse('roles:solicitar', args=[tipo])}")
            if forma_pago.id in [2, 6]:
                messages.error(request, "No se puede procesar con esta forma de pago.")
                return redirect(f"{reverse('roles:solicitar', args=[tipo])}")

            fondos_cliente = Fondo.objects.filter(usuario=user, forma_pago=forma_pago, activo=True)
            total_fondos = sum(f.monto for f in fondos_cliente)
            if total_fondos < monto:
                messages.error(request, f"No tienes suficiente saldo en {forma_pago.nombre} para cobrar.")
                return redirect(f"{reverse('roles:solicitar', args=[tipo])}")

            solicitud = SolicitudCobroPremio.objects.create(
                cliente=user,
                gestor=gestor,
                forma_pago=forma_pago,
                monto=monto,
                estado='pendiente',
                mensaje_cliente=mensaje
            )
            crear_notificacion(
                usuario=gestor,
                tipo='cobro',
                mensaje=f"📩 {user.username} ha solicitado un cobro de ${monto} en {forma_pago.nombre}.",
                datos={
                    'solicitud_id': solicitud.id,
                    'cliente': user.username,
                    'cliente_id': user.id,
                    'monto': float(monto),
                    'forma_pago': forma_pago.nombre,
                    'url_detalle': '/roles/gestionar-solicitudes/'
                },
                prioridad='alta',
                categoria='financiera'
            )
            messages.success(request, f"✅ Solicitud de cobro de ${monto} enviada a {gestor.username}.")

        elif tipo == 'retiro':
            forma_pago_id = request.POST.get('forma_pago')
            try:
                forma_pago = FormaPago.objects.get(id=forma_pago_id, activo=True)
            except FormaPago.DoesNotExist:
                messages.error(request, "Forma de pago no válida.")
                return redirect(f"{reverse('roles:solicitar', args=[tipo])}")
            if forma_pago.id in [2, 6]:
                messages.error(request, "No se puede procesar con esta forma de pago.")
                return redirect(f"{reverse('roles:solicitar', args=[tipo])}")

            # Validar Fondo del cliente
            fondos_cliente = Fondo.objects.filter(usuario=user, forma_pago=forma_pago, activo=True)
            total_fondos = sum(f.monto for f in fondos_cliente)
            if total_fondos <= 0:
                messages.error(request, f"No tienes saldo disponible en {forma_pago.nombre}.")
                return redirect(f"{reverse('roles:solicitar', args=[tipo])}")
            if total_fondos < monto:
                messages.error(request, f"Saldo insuficiente. Disponible: ${total_fondos} en {forma_pago.nombre}.")
                return redirect(f"{reverse('roles:solicitar', args=[tipo])}")

            # Recoger datos de la vía del cliente (a dónde quiere recibir)
            datos_via = {}
            if forma_pago.nombre.lower() in ('tarjeta', 'clásica', 'clasica', 'mlc'):
                num_tarjeta = request.POST.get('numero_tarjeta', '').strip()
                telefono_via = request.POST.get('telefono_via', '').strip()
                if not num_tarjeta or not telefono_via:
                    messages.error(request, "Para esta forma de pago debes indicar número de tarjeta y teléfono.")
                    return redirect(f"{reverse('roles:solicitar', args=[tipo])}")
                digitos = num_tarjeta.replace(' ', '').replace('-', '')
                if not digitos.isdigit() or len(digitos) != 16:
                    messages.error(request, "El número de tarjeta debe tener 16 dígitos.")
                    return redirect(f"{reverse('roles:solicitar', args=[tipo])}")
                datos_via = {
                    'numero_tarjeta': ' '.join(digitos[i:i+4] for i in range(0, 16, 4)),
                    'telefono': telefono_via,
                }
            elif forma_pago.nombre.lower() in ('saldo móvil', 'saldo movil', 'monedero', 'zelle'):
                telefono_via = request.POST.get('telefono_via', '').strip()
                if not telefono_via:
                    messages.error(request, "Para esta forma de pago debes indicar un teléfono.")
                    return redirect(f"{reverse('roles:solicitar', args=[tipo])}")
                datos_via = {'telefono': telefono_via}
            # Efectivo: sin datos de vía

            solicitud = SolicitudRetiro.objects.create(
                cliente=user,
                gestor=gestor,
                forma_pago=forma_pago,
                monto=monto,
                estado='pendiente',
                mensaje_cliente=mensaje,
                datos_via_cliente=datos_via,
                motivo_tipo=request.POST.get('motivo_tipo', 'cobro_premios'),
                motivo_detalle=request.POST.get('motivo_detalle', '').strip(),
            )
            crear_notificacion(
                usuario=gestor,
                tipo='pago',
                mensaje=f"📩 {user.username} ha solicitado un retiro de ${monto} en {forma_pago.nombre}.",
                datos={
                    'solicitud_id': solicitud.id,
                    'cliente': user.username,
                    'cliente_id': user.id,
                    'monto': float(monto),
                    'forma_pago': forma_pago.nombre,
                    'datos_via': datos_via,
                    'url_detalle': '/roles/gestionar-solicitudes/retiro/'
                },
                prioridad='alta',
                categoria='financiera'
            )
            messages.success(request, f"✅ Solicitud de retiro de ${monto} enviada a {gestor.username}.")

        elif tipo == 'prestamo':
            motivo = request.POST.get('motivo', '')
            prestamo = Prestamo.objects.create(
                solicitante=user,
                prestamista=gestor,
                monto=monto,
                saldo_pendiente=monto,
                interes=0,
                motivo=motivo,
                estado='solicitado',
                comercial_comun=gestor if user.roles.filter(tipo='cliente', activo=True).exists() else None
            )
            datos_prestamo = {
                'prestamo_id': prestamo.id,
                'solicitante': user.username,
                'solicitante_id': user.id,
                'prestamista': gestor.username,
                'prestamista_id': gestor.id,
                'monto': float(monto),
                'saldo_pendiente': float(prestamo.saldo_pendiente),
                'motivo': motivo,
                'fecha_solicitud': timezone.now().isoformat(),
                'estado': 'solicitado',
                'url_detalle': '/roles/mis-solicitudes/'
            }
            crear_notificacion(
                usuario=gestor,
                tipo='prestamo',
                mensaje=f"📩 {user.username} ha solicitado un préstamo de ${monto:.2f}.",
                datos=datos_prestamo,
                prioridad='alta',
                categoria='financiera'
            )
            subordinacion = Subordinacion.objects.filter(subordinado=user, activo=True).first()
            if subordinacion and subordinacion.jefe != gestor:
                crear_notificacion(
                    usuario=subordinacion.jefe,
                    tipo='prestamo',
                    mensaje=f"📩 {user.username} ha solicitado un préstamo de ${monto:.2f} a {gestor.username}.",
                    datos=datos_prestamo,
                    prioridad='media',
                    categoria='financiera'
                )
            messages.success(request, f"✅ Solicitud de préstamo de ${monto:.2f} enviada a {gestor.username}.")

        elif tipo == 'fondos':
            motivo = request.POST.get('motivo', f"Solicitud de fondos para cuadre")
            prestamo = Prestamo.objects.create(
                solicitante=user,
                prestamista=gestor,
                monto=monto,
                saldo_pendiente=0,
                interes=0,
                motivo=motivo,
                estado='solicitado',
                metadata={'tipo': 'fondos', 'solicitado_por': user.username}
            )
            crear_notificacion(
                usuario=gestor,
                tipo='info',
                mensaje=f"📩 {user.username} (comercial) solicita fondos por ${monto:.2f}.",
                datos={
                    'solicitud_id': prestamo.id,
                    'solicitante': user.username,
                    'monto': float(monto),
                    'motivo': motivo,
                    'url_detalle': '/roles/gestionar-solicitudes/'
                },
                prioridad='alta',
                categoria='financiera'
            )
            messages.success(request, f"✅ Solicitud de fondos de ${monto:.2f} enviada a {gestor.username}.")

        return redirect('roles:mis_solicitudes_todas')

    context = {
        'tipo': tipo,
        'gestores_data': gestores_data,
        'gestores': gestores,
        'formas_pago': formas_pago,
    }
    return render(request, 'roles/solicitar.html', context)

@login_required
def gestionar_solicitudes(request, tipo=None):
    user = request.user
    es_gestor = user.roles.filter(tipo__in=['comercial', 'banco', 'superadmin'], activo=True).exists() or user.is_superuser
    if not es_gestor:
        messages.error(request, "No tienes permisos para gestionar solicitudes.")
        return redirect('publico:home')

    if tipo == 'recarga' or tipo is None:
        solicitudes = SolicitudRecarga.objects.filter(gestor=user).select_related('cliente', 'forma_pago', 'via_pago')
        solicitudes = solicitudes.annotate(tipo_solicitud=Value('recarga', output_field=CharField()))
    elif tipo == 'cobro':
        solicitudes = SolicitudCobroPremio.objects.filter(gestor=user).select_related('cliente', 'forma_pago', 'via_pago')
        solicitudes = solicitudes.annotate(tipo_solicitud=Value('cobro', output_field=CharField()))
    elif tipo == 'prestamo':
        solicitudes = Prestamo.objects.filter(prestamista=user).select_related('solicitante', 'prestamista')
        solicitudes = solicitudes.annotate(tipo_solicitud=Value('prestamo', output_field=CharField()))
    elif tipo == 'retiro':
        solicitudes = SolicitudRetiro.objects.filter(gestor=user).select_related('cliente', 'forma_pago')
        solicitudes = solicitudes.annotate(tipo_solicitud=Value('retiro', output_field=CharField()))
    elif tipo == 'fondos':
        solicitudes = Prestamo.objects.filter(
            prestamista=user,
            metadata__tipo='fondos'
        ).select_related('solicitante', 'prestamista')
        solicitudes = solicitudes.annotate(tipo_solicitud=Value('fondos', output_field=CharField()))
    else:
        messages.error(request, "Tipo de solicitud no válido.")
        return redirect('publico:home')

    estado = request.GET.get('estado')
    if estado:
        if tipo in ['recarga', 'cobro', 'retiro']:
            solicitudes = solicitudes.filter(estado=estado)
        elif tipo in ['prestamo', 'fondos']:
            solicitudes = solicitudes.filter(estado=estado)
    else:
        if tipo in ['recarga', 'cobro', 'retiro']:
            solicitudes = solicitudes.filter(estado='pendiente')
        elif tipo in ['prestamo', 'fondos']:
            solicitudes = solicitudes.filter(estado='solicitado')

    solicitudes = solicitudes.order_by('-fecha_solicitud' if hasattr(solicitudes.model, 'fecha_solicitud') else '-created_at')

    paginator = Paginator(solicitudes, 20)
    page = request.GET.get('page')
    solicitudes_page = paginator.get_page(page)

    context = {
        'tipo': tipo,
        'solicitudes': solicitudes_page,
        'estado_seleccionado': estado,
        'es_superadmin': user.is_superuser or user.roles.filter(tipo='superadmin', activo=True).exists(),
        'es_banco': user.roles.filter(tipo='banco', activo=True).exists(),
        'es_comercial': user.roles.filter(tipo='comercial', activo=True).exists(),
    }
    return render(request, 'roles/gestionar_solicitudes.html', context)

@login_required
def responder_solicitud(request, tipo, solicitud_id, accion=None):
    user = request.user
    es_gestor = user.roles.filter(tipo__in=['comercial', 'banco', 'superadmin'], activo=True).exists() or user.is_superuser
    if not es_gestor:
        messages.error(request, "No tienes permisos para gestionar solicitudes.")
        return redirect('publico:home')

    if tipo == 'recarga':
        solicitud = get_object_or_404(SolicitudRecarga, id=solicitud_id, gestor=user)
        vias_pago = ViaPago.objects.filter(
            gestor=user,
            forma_pago=solicitud.forma_pago,
            activo=True,
            direccion__in=['recibir', 'ambos']
        ).order_by('nombre')
        via_por_defecto = vias_pago.filter(es_por_defecto=True).first()
        template = 'roles/responder_recarga.html'
    elif tipo == 'cobro':
        solicitud = get_object_or_404(SolicitudCobroPremio, id=solicitud_id, gestor=user)
        vias_pago = ViaPago.objects.filter(
            gestor=user,
            forma_pago=solicitud.forma_pago,
            activo=True,
            direccion__in=['enviar', 'ambos']
        ).order_by('nombre')
        via_por_defecto = vias_pago.filter(es_por_defecto=True).first()
        template = 'roles/responder_cobro.html'
    elif tipo == 'retiro':
        solicitud = get_object_or_404(SolicitudRetiro, id=solicitud_id, gestor=user)
        vias_pago = []  # no aplica: la vía la indicó el cliente
        via_por_defecto = None
        template = 'roles/responder_retiro.html'
    elif tipo in ['prestamo', 'fondos']:
        solicitud = get_object_or_404(Prestamo, id=solicitud_id, prestamista=user)
        vias_pago = ViaPago.objects.filter(
            gestor=user,
            activo=True,
            direccion__in=['enviar', 'ambos']
        ).order_by('nombre')
        via_por_defecto = vias_pago.filter(es_por_defecto=True).first()
        template = 'roles/responder_prestamo.html'
    else:
        messages.error(request, "Tipo de solicitud no válido.")
        return redirect('roles:gestionar_solicitudes', tipo=tipo)

    estado_actual = solicitud.estado if hasattr(solicitud, 'estado') else getattr(solicitud, 'estado', 'solicitado')
    if accion in ['aceptar', 'rechazar'] and estado_actual not in ['pendiente', 'solicitado']:
        messages.warning(request, f"Esta solicitud ya está {estado_actual}.")
        return redirect('roles:gestionar_solicitudes', tipo=tipo)

    if request.method == 'POST':
        if accion == 'rechazar':
            motivo = request.POST.get('motivo', '')
            if tipo == 'recarga':
                success, msg = solicitud.rechazar(motivo)
            elif tipo == 'cobro':
                success, msg = solicitud.rechazar(motivo)
            elif tipo == 'retiro':
                success, msg = solicitud.rechazar(motivo)
            elif tipo in ['prestamo', 'fondos']:
                solicitud.estado = 'rechazado'
                solicitud.save()
                success, msg = True, "Solicitud rechazada."
            if success:
                messages.success(request, msg)
            else:
                messages.error(request, msg)
            return redirect('roles:gestionar_solicitudes', tipo=tipo)

        elif accion == 'aceptar':
            via = None
            if tipo != 'retiro':
                via_pago_id = request.POST.get('via_pago')
                if not via_pago_id:
                    messages.error(request, "Debes seleccionar una vía de pago.")
                    return redirect(request.path)
                try:
                    via = ViaPago.objects.get(id=via_pago_id, gestor=user, activo=True)
                except ViaPago.DoesNotExist:
                    messages.error(request, "Vía de pago no válida.")
                    return redirect(request.path)

            if tipo == 'recarga':
                success, msg = solicitud.aceptar(via.id)
            elif tipo == 'cobro':
                success, msg = solicitud.aceptar(via.id)
            elif tipo == 'retiro':
                success, msg = solicitud.aceptar()
            elif tipo == 'prestamo':
                success, msg = solicitud.aprobar(aprobado_por=user)
            elif tipo == 'fondos':
                try:
                    with transaction.atomic():
                        fondos_gestor = Fondo.objects.filter(usuario=user, activo=True)
                        saldo_gestor = sum(f.monto for f in fondos_gestor)
                        if saldo_gestor < solicitud.monto:
                            messages.error(request, f"No tienes suficientes fondos. Saldo: ${saldo_gestor}")
                            return redirect(request.path)
                        monto_restante = solicitud.monto
                        for fondo in fondos_gestor.order_by('id'):
                            if monto_restante <= 0:
                                break
                            saldo_ant_g = fondo.monto
                            if fondo.monto >= monto_restante:
                                fondo.monto -= monto_restante
                                delta_g = -monto_restante
                                monto_restante = 0
                            else:
                                delta_g = -fondo.monto
                                monto_restante -= fondo.monto
                                fondo.monto = 0
                            fondo.save()
                            try:
                                MovimientoFondo.objects.create(
                                    emisor=user,
                                    receptor=user,
                                    forma_pago=fondo.forma_pago,
                                    monto=delta_g,
                                    tipo='ajuste',
                                    estado='confirmado',
                                    motivo='Fondos aprobados a ' + solicitud.solicitante.username + ' (solicitud #' + str(solicitud.id) + ')',
                                    saldo_antes=saldo_ant_g,
                                    saldo_despues=fondo.monto,
                                    datos_transferencia={'solicitud_id': solicitud.id, 'rol': 'emisor'},
                                )
                            except Exception:
                                pass
                        forma_pago = FormaPago.objects.filter(activo=True).first()
                        if forma_pago:
                            fondo_comercial, _ = Fondo.objects.get_or_create(
                                usuario=solicitud.solicitante,
                                forma_pago=forma_pago,
                                defaults={'monto': 0, 'activo': True, 'asignado_por': user}
                            )
                            saldo_ant_c = fondo_comercial.monto
                            fondo_comercial.monto += solicitud.monto
                            fondo_comercial.save()
                            try:
                                MovimientoFondo.objects.create(
                                    emisor=user,
                                    receptor=solicitud.solicitante,
                                    forma_pago=forma_pago,
                                    monto=solicitud.monto,
                                    tipo='ajuste',
                                    estado='confirmado',
                                    motivo='Fondos recibidos de ' + user.username + ' (solicitud #' + str(solicitud.id) + ')',
                                    saldo_antes=saldo_ant_c,
                                    saldo_despues=fondo_comercial.monto,
                                    datos_transferencia={'solicitud_id': solicitud.id, 'rol': 'receptor'},
                                )
                            except Exception:
                                pass
                        solicitud.estado = 'aprobado'
                        solicitud.save()
                        success, msg = True, f"Solicitud de fondos aprobada. ${solicitud.monto} transferidos."
                except Exception as e:
                    success, msg = False, f"Error al procesar la solicitud: {str(e)}"
            else:
                success, msg = False, "Tipo de solicitud no válido para aceptar."

            if success:
                messages.success(request, msg)
            else:
                messages.error(request, msg)
            return redirect('roles:gestionar_solicitudes', tipo=tipo)

        elif accion == 'confirmar':
            if tipo == 'recarga':
                monto_abonado = request.POST.get('monto_abonado')
                try:
                    monto = Decimal(monto_abonado) if monto_abonado else solicitud.monto
                    if monto <= 0:
                        raise ValueError("El monto debe ser mayor a 0")
                    if monto > solicitud.monto:
                        raise ValueError(f"El monto no puede exceder ${solicitud.monto}")
                except:
                    messages.error(request, "Monto inválido.")
                    return redirect(request.path)

                success, msg = solicitud.pagar(monto)

                if success:
                    from .utils import verificar_postpago_al_recibir_recarga
                    descontado = verificar_postpago_al_recibir_recarga(
                        solicitud.cliente, monto, solicitud.id,
                        gestor=solicitud.gestor
                    )
                    if descontado > 0:
                        messages.info(request, f"💰 Se descontaron ${descontado:.2f} de postpagos pendientes del cliente.")

            elif tipo == 'cobro':
                success, msg = solicitud.pagar()
                # FIX_POSTPAGO_V2: descontar postpago del cliente y acreditar al gestor
                if success:
                    try:
                        from .utils import descontar_postpago
                        _desc = descontar_postpago(
                            cliente=solicitud.cliente,
                            monto=solicitud.monto,
                            tipo='premio',
                            origen_id=solicitud.id,
                            concepto=f"Cobro de premio #{solicitud.id}",
                            gestor=solicitud.gestor
                        )
                        if _desc > 0:
                            messages.info(
                                request,
                                f"💰 Postpago descontado: ${_desc:.2f} (acreditado al gestor)."
                            )
                    except Exception as e:
                        logger.warning(f"Error descontando postpago en cobro: {e}")
            elif tipo == 'retiro':
                success, msg = solicitud.pagar()
            elif tipo in ['prestamo', 'fondos']:
                success, msg = True, "Operación no implementada para este tipo."
            else:
                success, msg = False, "Tipo de solicitud no válido para confirmar."

            if success:
                messages.success(request, msg)
            else:
                messages.error(request, msg)
            return redirect('roles:gestionar_solicitudes', tipo=tipo)

    context = {
        'solicitud': solicitud,
        'vias_pago': vias_pago,
        'via_por_defecto': via_por_defecto,
        'tipo': tipo,
    }
    return render(request, template, context)

@login_required
def mis_solicitudes(request, tipo=None):
    user = request.user
    es_cliente = user.roles.filter(tipo='cliente', activo=True).exists()
    es_comercial = user.roles.filter(tipo='comercial', activo=True).exists()

    if not es_cliente and not es_comercial:
        messages.error(request, "No tienes acceso a esta sección.")
        return redirect('publico:home')

    if tipo == 'recarga' or tipo is None:
        solicitudes = SolicitudRecarga.objects.filter(cliente=user).select_related('gestor', 'forma_pago', 'via_pago')
        solicitudes = solicitudes.annotate(tipo_solicitud=Value('recarga', output_field=CharField()))
    elif tipo == 'cobro':
        solicitudes = SolicitudCobroPremio.objects.filter(cliente=user).select_related('gestor', 'forma_pago', 'via_pago')
        solicitudes = solicitudes.annotate(tipo_solicitud=Value('cobro', output_field=CharField()))
    elif tipo == 'prestamo':
        solicitudes = Prestamo.objects.filter(solicitante=user).select_related('solicitante', 'prestamista')
        solicitudes = solicitudes.annotate(tipo_solicitud=Value('prestamo', output_field=CharField()))
    elif tipo == 'fondos':
        if not es_comercial:
            messages.error(request, "No puedes ver solicitudes de fondos.")
            return redirect('publico:home')
        solicitudes = Prestamo.objects.filter(
            solicitante=user,
            metadata__tipo='fondos'
        ).select_related('solicitante', 'prestamista')
        solicitudes = solicitudes.annotate(tipo_solicitud=Value('fondos', output_field=CharField()))
    else:
        messages.error(request, "Tipo de solicitud no válido.")
        return redirect('publico:home')

    estado = request.GET.get('estado')
    if estado:
        if tipo in ['recarga', 'cobro']:
            solicitudes = solicitudes.filter(estado=estado)
        elif tipo in ['prestamo', 'fondos']:
            solicitudes = solicitudes.filter(estado=estado)

    solicitudes = solicitudes.order_by('-fecha_solicitud' if hasattr(solicitudes.model, 'fecha_solicitud') else '-created_at')

    paginator = Paginator(solicitudes, 10)
    page = request.GET.get('page')
    page_obj = paginator.get_page(page)

    context = {
        'tipo': tipo,
        'page_obj': page_obj,
        'estado_seleccionado': estado,
    }
    return render(request, 'roles/mis_solicitudes.html', context)

# ============================================================
# POSTPAGOS (CRÉDITO ACUMULATIVO) – VISTAS
# ============================================================
@login_required
def gestionar_postpagos(request):
    user = request.user
    es_gestor = user.roles.filter(tipo__in=['comercial', 'banco', 'superadmin'], activo=True).exists() or user.is_superuser
    if not es_gestor:
        messages.error(request, "No tienes permisos para gestionar postpagos.")
        return redirect('publico:home')

    if user.is_superuser or user.roles.filter(tipo='superadmin', activo=True).exists():
        clientes = User.objects.filter(roles__tipo='cliente', roles__activo=True).distinct()
        postpagos = Postpago.objects.all().select_related('cliente', 'gestor')
    elif user.roles.filter(tipo='banco', activo=True).exists():
        comerciales_ids = Subordinacion.objects.filter(jefe=user, activo=True).values_list('subordinado_id', flat=True)
        clientes_ids = Fondo.objects.filter(
            Q(asignado_por__in=comerciales_ids) | Q(asignado_por=user),
            activo=True
        ).values_list('usuario_id', flat=True).distinct()
        clientes = User.objects.filter(id__in=clientes_ids, is_active=True)
        postpagos = Postpago.objects.filter(cliente__in=clientes_ids).select_related('cliente', 'gestor')
    elif user.roles.filter(tipo='comercial', activo=True).exists():
        clientes_ids = Fondo.objects.filter(asignado_por=user, activo=True).values_list('usuario_id', flat=True).distinct()
        clientes = User.objects.filter(id__in=clientes_ids, is_active=True)
        postpagos = Postpago.objects.filter(cliente__in=clientes_ids).select_related('cliente', 'gestor')
    else:
        messages.error(request, "No tienes acceso a esta sección.")
        return redirect('publico:home')

    if request.method == 'POST' and 'crear_postpago' in request.POST:
        cliente_id = request.POST.get('cliente')
        monto_str = request.POST.get('monto')
        concepto = request.POST.get('concepto', '')

        try:
            cliente = User.objects.get(id=cliente_id, is_active=True)
        except User.DoesNotExist:
            messages.error(request, "Cliente no encontrado.")
            return redirect('roles:gestionar_postpagos')

        try:
            monto = Decimal(monto_str)
            if monto <= 0:
                raise ValueError("El monto debe ser mayor a 0")
        except:
            messages.error(request, "Monto inválido.")
            return redirect('roles:gestionar_postpagos')

        from .utils import agregar_postpago
        postpago = agregar_postpago(cliente, user, monto, concepto)
        messages.success(request, f"✅ Postpago de ${monto:.2f} añadido a {cliente.username}.")

        cliente_postpago = PostpagoCliente.objects.filter(cliente=cliente).first()
        saldo = cliente_postpago.saldo if cliente_postpago else Decimal('0.00')
        messages.info(request, f"Saldo actual de postpago: ${saldo:.2f}")

        return redirect('roles:gestionar_postpagos')

    estado = request.GET.get('estado')
    if estado:
        if estado == 'activos':
            postpagos = postpagos.filter(activo=True)
        elif estado == 'inactivos':
            postpagos = postpagos.filter(activo=False)

    postpagos = postpagos.order_by('-fecha_creacion')
    paginator = Paginator(postpagos, 20)
    page = request.GET.get('page')
    postpagos_page = paginator.get_page(page)

    clientes_con_saldo = []
    for cliente in clientes:
        cp = PostpagoCliente.objects.filter(cliente=cliente).first()
        saldo = cp.saldo if cp else Decimal('0.00')
        ultima_adicion = postpagos.filter(cliente=cliente).first()
        ultima_fecha = ultima_adicion.fecha_creacion if ultima_adicion else None
        dias = (timezone.now() - ultima_fecha).days if ultima_fecha else None
        clientes_con_saldo.append({
            'cliente': cliente,
            'saldo': saldo,
            'ultima_adicion': ultima_fecha,
            'dias_transcurridos': dias,
        })

    context = {
        'postpagos': postpagos_page,
        'clientes': clientes_con_saldo,
        'estado_seleccionado': estado,
        'es_superadmin': user.is_superuser or user.roles.filter(tipo='superadmin', activo=True).exists(),
        'es_banco': user.roles.filter(tipo='banco', activo=True).exists(),
        'es_comercial': user.roles.filter(tipo='comercial', activo=True).exists(),
    }
    return render(request, 'roles/gestionar_postpagos.html', context)

@login_required
def mis_postpagos(request):
    user = request.user
    es_cliente = user.roles.filter(tipo='cliente', activo=True).exists()
    if not es_cliente:
        messages.error(request, "No tienes acceso a esta sección.")
        return redirect('publico:home')

    cliente_postpago = PostpagoCliente.objects.filter(cliente=user).first()
    saldo = cliente_postpago.saldo if cliente_postpago else Decimal('0.00')

    adiciones = Postpago.objects.filter(cliente=user, activo=True).order_by('-fecha_creacion')
    descuentos = PostpagoDescuento.objects.filter(cliente=user).order_by('-fecha')

    historial = []
    for a in adiciones:
        dias = (timezone.now() - a.fecha_creacion).days
        historial.append({
            'fecha': a.fecha_creacion,
            'tipo': 'adicion',
            'monto': a.monto,
            'concepto': a.concepto,
            'dias': dias,
        })
    for d in descuentos:
        dias = (timezone.now() - d.fecha).days
        historial.append({
            'fecha': d.fecha,
            'tipo': 'descuento',
            'monto': d.monto,
            'concepto': d.concepto,
            'dias': dias,
        })
    historial.sort(key=lambda x: x['fecha'], reverse=True)

    context = {
        'saldo': saldo,
        'historial': historial,
    }
    return render(request, 'roles/mis_postpagos.html', context)

@login_required
def api_historial_postpagos(request, cliente_id):
    user = request.user
    es_gestor = user.roles.filter(tipo__in=['comercial', 'banco', 'superadmin'], activo=True).exists() or user.is_superuser
    if not es_gestor:
        return JsonResponse({'error': 'Sin permiso'}, status=403)

    cliente = get_object_or_404(User, id=cliente_id)
    adiciones = Postpago.objects.filter(cliente=cliente, activo=True).order_by('-fecha_creacion')
    descuentos = PostpagoDescuento.objects.filter(cliente=cliente).order_by('-fecha')

    historial = []
    for a in adiciones:
        dias = (timezone.now() - a.fecha_creacion).days
        historial.append({
            'fecha': a.fecha_creacion.strftime('%d/%m/%Y %H:%M'),
            'tipo': 'adicion',
            'monto': float(a.monto),
            'concepto': a.concepto,
            'dias': dias,
        })
    for d in descuentos:
        dias = (timezone.now() - d.fecha).days
        historial.append({
            'fecha': d.fecha.strftime('%d/%m/%Y %H:%M'),
            'tipo': 'descuento',
            'monto': -float(d.monto),
            'concepto': d.concepto,
            'dias': dias,
        })
    historial.sort(key=lambda x: x['fecha'], reverse=True)

    return JsonResponse({
        'cliente': cliente.username,
        'historial': historial
    })

# ============================================================
# GESTIÓN DE LÍMITES Y DOSIS
# ============================================================
@login_required
def gestion_limites_dosis(request):
    user = request.user
    es_superadmin = user.is_superuser or user.roles.filter(tipo='superadmin', activo=True).exists()
    es_banco = user.roles.filter(tipo='banco', activo=True).exists()
    if not (es_superadmin or es_banco):
        messages.error(request, "No tienes permisos para gestionar limites y dosis.")
        return redirect('publico:home')

    forma_juego_seleccionada = request.GET.get('forma_juego')
    q_busqueda = (request.GET.get('q') or '').strip()

    if es_superadmin:
        bancos = list(User.objects.filter(roles__tipo='banco', roles__activo=True).distinct().order_by('username'))
        banco_id = request.GET.get('banco') or request.POST.get('banco')
        banco_seleccionado = None
        if banco_id and str(banco_id).isdigit():
            banco_seleccionado = User.objects.filter(id=int(banco_id)).first()
        comerciales = []
        if banco_seleccionado:
            ids = Subordinacion.objects.filter(jefe=banco_seleccionado, activo=True).values_list('subordinado_id', flat=True)
            comerciales = list(User.objects.filter(id__in=ids, is_active=True).order_by('username'))
    else:
        bancos = [user]
        banco_seleccionado = user
        ids = Subordinacion.objects.filter(jefe=user, activo=True).values_list('subordinado_id', flat=True)
        comerciales = list(User.objects.filter(id__in=ids, is_active=True).order_by('username'))

    comercial_id = request.GET.get('comercial') or request.POST.get('comercial_id')
    comercial_seleccionado = None
    if comercial_id and str(comercial_id).isdigit():
        comerciales_ids = [c.id for c in comerciales]
        if int(comercial_id) in comerciales_ids:
            comercial_seleccionado = User.objects.filter(id=int(comercial_id)).first()

    es_destino_banco = comercial_seleccionado is None and banco_seleccionado is not None
    es_destino_comercial = comercial_seleccionado is not None

    if not banco_seleccionado:
        return render(request, 'roles/gestion_limites_dosis.html', {
            'bancos': bancos, 'comerciales': [], 'banco_seleccionado': None,
            'comercial_seleccionado': None, 'matriz': None,
            'formas_pago_activas': [], 'es_superadmin': es_superadmin, 'es_banco': es_banco,
            'formas_juego_disponibles': [], 'forma_juego_seleccionada': forma_juego_seleccionada,
            'todos_sorteos': [], 'todas_fj': [], 'todas_fp': [],
            'recursos_actuales': {'sorteos': [], 'fj': [], 'fp': []},
            'generado': False, 'es_destino_banco': False, 'es_destino_comercial': False,
        })

    recursos_actuales = {'sorteos': [], 'fj': [], 'fp': []}
    if es_destino_banco:
        for r in RecursoAsignado.objects.filter(banco=banco_seleccionado, comercial__isnull=True, activo=True):
            if r.tipo == 'sorteo' and r.sorteo_id: recursos_actuales['sorteos'].append(r.sorteo_id)
            elif r.tipo == 'forma_juego' and r.forma_juego_id: recursos_actuales['fj'].append(r.forma_juego_id)
            elif r.tipo == 'forma_pago' and r.forma_pago_id: recursos_actuales['fp'].append(r.forma_pago_id)
    else:
        for r in RecursoAsignado.objects.filter(comercial=comercial_seleccionado, banco__isnull=True, activo=True):
            if r.tipo == 'sorteo' and r.sorteo_id: recursos_actuales['sorteos'].append(r.sorteo_id)
            elif r.tipo == 'forma_juego' and r.forma_juego_id: recursos_actuales['fj'].append(r.forma_juego_id)
            elif r.tipo == 'forma_pago' and r.forma_pago_id: recursos_actuales['fp'].append(r.forma_pago_id)

    if request.method == 'POST' and request.POST.get('accion') == 'generar':
        sorteos_ids = [int(x) for x in request.POST.getlist('sorteos') if str(x).isdigit()]
        fj_ids = [int(x) for x in request.POST.getlist('formas_juego') if str(x).isdigit()]
        fp_ids = [int(x) for x in request.POST.getlist('formas_pago') if str(x).isdigit()]

        if not (sorteos_ids and fj_ids and fp_ids):
            messages.error(request, "Selecciona al menos 1 sorteo, 1 forma de juego y 1 forma de pago.")
        else:
            with transaction.atomic():
                if es_destino_banco:
                    RecursoAsignado.objects.filter(banco=banco_seleccionado, comercial__isnull=True).delete()
                else:
                    RecursoAsignado.objects.filter(comercial=comercial_seleccionado, banco__isnull=True).delete()
                for sid in sorteos_ids:
                    RecursoAsignado.objects.create(
                        banco=banco_seleccionado if es_destino_banco else None,
                        comercial=comercial_seleccionado if es_destino_comercial else None,
                        tipo='sorteo', sorteo_id=sid, activo=True, creado_por=user)
                for fj in fj_ids:
                    RecursoAsignado.objects.create(
                        banco=banco_seleccionado if es_destino_banco else None,
                        comercial=comercial_seleccionado if es_destino_comercial else None,
                        tipo='forma_juego', forma_juego_id=fj, activo=True, creado_por=user)
                for fp in fp_ids:
                    RecursoAsignado.objects.create(
                        banco=banco_seleccionado if es_destino_banco else None,
                        comercial=comercial_seleccionado if es_destino_comercial else None,
                        tipo='forma_pago', forma_pago_id=fp, activo=True, creado_por=user)
            messages.success(request, "Recursos asignados. Ahora edita dosis, limites y sobrelimites.")
            base = reverse('roles:gestion_limites_dosis') + "?banco=" + str(banco_seleccionado.id)
            if es_destino_comercial:
                base += "&comercial=" + str(comercial_seleccionado.id)
            return redirect(base + "&generado=1")

    if request.method == 'POST' and request.POST.get('accion') == 'guardar':
        guardados = 0
        sorteos_ids_dest = list(RecursoAsignado.objects.filter(
            banco=banco_seleccionado if es_destino_banco else None,
            comercial=comercial_seleccionado if es_destino_comercial else None,
            tipo='sorteo', activo=True).values_list('sorteo_id', flat=True))
        fj_ids_dest = list(RecursoAsignado.objects.filter(
            banco=banco_seleccionado if es_destino_banco else None,
            comercial=comercial_seleccionado if es_destino_comercial else None,
            tipo='forma_juego', activo=True).values_list('forma_juego_id', flat=True))
        fp_ids_dest = list(RecursoAsignado.objects.filter(
            banco=banco_seleccionado if es_destino_banco else None,
            comercial=comercial_seleccionado if es_destino_comercial else None,
            tipo='forma_pago', activo=True).values_list('forma_pago_id', flat=True))

        with transaction.atomic():
            for sid in sorteos_ids_dest:
                for fj in fj_ids_dest:
                    for fp in fp_ids_dest:
                        lim_str = (request.POST.get('limite_%s_%s_%s' % (fp, sid, fj)) or '').strip()
                        sob_str = (request.POST.get('sobrelimite_%s_%s_%s' % (fp, sid, fj)) or '').strip()
                        dos_str = (request.POST.get('dosis_%s_%s_%s' % (fp, sid, fj)) or '').strip()
                        if not (lim_str or sob_str or dos_str):
                            continue
                        try:
                            lim = Decimal(lim_str or '0')
                            sob = Decimal(sob_str or lim_str or '0')
                            dos = Decimal(dos_str) if dos_str else None
                        except Exception:
                            continue
                        filtros = {'sorteo_id': sid, 'forma_juego_id': fj, 'forma_pago_id': fp}
                        if es_destino_banco:
                            filtros['banco'] = banco_seleccionado
                            filtros['comercial'] = None
                        else:
                            filtros['banco'] = None
                            filtros['comercial'] = comercial_seleccionado
                        LimiteApuesta.objects.update_or_create(
                            **filtros,
                            defaults={'monto_maximo': lim, 'monto_sobrelimite': sob, 'activo': True})
                        if dos is not None:
                            DosisPago.objects.update_or_create(
                                **filtros,
                                defaults={'monto_por_peso': dos, 'activo': True})
                        guardados += 1
        messages.success(request, "Guardados %s registros." % guardados)
        base = reverse('roles:gestion_limites_dosis') + "?banco=" + str(banco_seleccionado.id)
        if es_destino_comercial:
            base += "&comercial=" + str(comercial_seleccionado.id)
        return redirect(base)

    if request.method == 'POST' and request.POST.get('accion') == 'copiar_limites_banco':
        if es_destino_comercial and banco_seleccionado:
            with transaction.atomic():
                LimiteApuesta.objects.filter(comercial=comercial_seleccionado).delete()
                DosisPago.objects.filter(comercial=comercial_seleccionado).delete()
                for lb in LimiteApuesta.objects.filter(banco=banco_seleccionado, comercial__isnull=True, activo=True):
                    LimiteApuesta.objects.create(
                        banco=None, comercial=comercial_seleccionado,
                        sorteo=lb.sorteo, forma_juego=lb.forma_juego, forma_pago=lb.forma_pago,
                        monto_maximo=lb.monto_maximo, monto_sobrelimite=lb.monto_sobrelimite,
                        activo=True, es_global=False)
                for db in DosisPago.objects.filter(banco=banco_seleccionado, comercial__isnull=True, activo=True):
                    DosisPago.objects.create(
                        banco=None, comercial=comercial_seleccionado,
                        sorteo=db.sorteo, forma_juego=db.forma_juego, forma_pago=db.forma_pago,
                        monto_por_peso=db.monto_por_peso, activo=True, es_global=False)
            messages.success(request, "Copiados limites y dosis del banco a " + comercial_seleccionado.username + ".")
        base = reverse('roles:gestion_limites_dosis') + "?banco=" + str(banco_seleccionado.id)
        if es_destino_comercial:
            base += "&comercial=" + str(comercial_seleccionado.id)
        return redirect(base)

    todos_sorteos = list(Sorteo.objects.filter(activo=True).order_by('nombre'))
    todas_fj = list(FormaJuego.objects.filter(activo=True).order_by('nombre'))
    todas_fp = list(FormaPago.objects.filter(activo=True).order_by('nombre'))

    generado = request.GET.get('generado') == '1' or bool(recursos_actuales['sorteos'])
    matriz = None
    if generado:
        matriz = get_matriz_limites_dosis(
            banco_seleccionado,
            comercial_seleccionado if es_destino_comercial else None)

    # ── Agrupar y ordenar filas para el template ──
    if matriz and matriz.get('filas'):
        PREFIJOS_PRIORITARIOS = [
            'texas', 'tennessee', 'florida', 'anguila', 'tok',
            'georgia', 'new york', 'new jersey', 'king lottery',
            'real', 'nacional', 'primera', 'haiti', 'haití',
            'leidsa', 'lotedom', 'loteka', 'suerte', 'gana',
        ]

        def prioridad_prefijo(nombre):
            n = nombre.lower()
            for i, p in enumerate(PREFIJOS_PRIORITARIOS):
                if n.startswith(p):
                    return (0, i, n)
            return (1, 0, n)

        grupos = {}
        for fila in matriz['filas']:
            nombre = fila['sorteo'].nombre
            prefijo = nombre.split()[0]
            grupos.setdefault(prefijo, []).append(fila)

        matriz['grupos'] = []
        for prefijo in sorted(grupos.keys(), key=lambda p: prioridad_prefijo(p)):
            filas = grupos[prefijo]
            filas.sort(key=lambda f: extraer_hora(f['sorteo'].nombre))
            matriz['grupos'].append({'prefijo': prefijo, 'filas': filas})
    elif matriz:
        matriz['grupos'] = []

    # ── Filtro por forma de juego ──
    if forma_juego_seleccionada and matriz and matriz.get('filas'):
        try:
            fj_id = int(forma_juego_seleccionada)
            matriz['filas'] = [
                f for f in matriz['filas']
                if any(c['forma_juego'].id == fj_id for c in f.get('combos', []))
            ]
            for fila in matriz['filas']:
                fila['combos'] = [c for c in fila['combos'] if c['forma_juego'].id == fj_id]
        except (ValueError, TypeError):
            pass

    formas_pago_activas = [fp.id for fp in matriz['formas_pago']] if matriz else []

    context = {
        'bancos': bancos,
        'comerciales': comerciales,
        'banco_seleccionado': banco_seleccionado,
        'comercial_seleccionado': comercial_seleccionado,
        'es_destino_banco': es_destino_banco,
        'es_destino_comercial': es_destino_comercial,
        'matriz': matriz,
        'formas_pago_activas': formas_pago_activas,
        'es_superadmin': es_superadmin,
        'es_banco': es_banco,
        'formas_juego_disponibles': todas_fj,
        'forma_juego_seleccionada': forma_juego_seleccionada,
        'todos_sorteos': todos_sorteos,
        'todas_fj': todas_fj,
        'todas_fp': todas_fp,
        'recursos_actuales': recursos_actuales,
        'generado': generado,
        'q_busqueda': q_busqueda,
    }
    return render(request, 'roles/gestion_limites_dosis.html', context)


@login_required
def cuadre_diario_view(request):
    usuario_actual = request.user
    hoy = date.today()
    fecha_str = request.GET.get("fecha")
    fecha_hasta_str = request.GET.get("fecha_hasta")
    fecha = parse_date(fecha_str) if fecha_str else hoy
    fecha_hasta = parse_date(fecha_hasta_str) if fecha_hasta_str else fecha

    def get_rol(user):
        rol = Rol.objects.filter(usuario=user, activo=True).first()
        return rol.tipo if rol else None

    rol_usuario = get_rol(usuario_actual)
    es_superadmin = usuario_actual.is_superuser or rol_usuario == 'superadmin'
    es_banco = rol_usuario == 'banco'
    es_comercial = rol_usuario == 'comercial'

    context = {
        "usuario_actual": usuario_actual, "fecha": fecha, "fecha_hasta": fecha_hasta,
        "hoy": hoy, "es_superadmin": es_superadmin, "es_banco": es_banco, "es_comercial": es_comercial,
    }

    if es_comercial:
        # FIX_FILTROS_DINAMICOS: comercial solo ve su cuadre, pero puede cambiar fecha
        context.update(CuadreService.generar_cuadre_completo(usuario_actual, fecha))
        context["vista"] = "comercial"
        context["bancos"] = User.objects.none()
        context["comerciales"] = User.objects.none()
        return render(request, "roles/cuadre_diario.html", context)

    if es_banco:
        # FIX_COMERCIALES_FILTRO: solo subordinados con rol COMERCIAL
        comerciales_ids_all = Subordinacion.objects.filter(
            jefe=usuario_actual, activo=True
        ).values_list('subordinado_id', flat=True)
        comerciales_ids = Rol.objects.filter(
            usuario_id__in=comerciales_ids_all,
            tipo='comercial',
            activo=True
        ).values_list('usuario_id', flat=True)
        comerciales = User.objects.filter(id__in=comerciales_ids, is_active=True)
        comercial_id = request.GET.get("comercial_id")
        if comercial_id:
            comercial = get_object_or_404(User, pk=comercial_id, id__in=comerciales_ids)
            context.update(CuadreService.generar_cuadre_completo(comercial, fecha))
            context["comercial_seleccionado"] = comercial
            context["vista"] = "banco_comercial"
        else:
            context["resumen_general"] = CuadreService.calcular_resumen_banco(usuario_actual, fecha, fecha_hasta)
            context.update(CuadreService.generar_cuadre_completo(usuario_actual, fecha))
            context["vista"] = "banco_resumen"
        context["comerciales"] = comerciales
        return render(request, "roles/cuadre_diario.html", context)

    # FIX_CUADRE_FILTROS_V1 — superadmin
    if es_superadmin:
        banco_id = request.GET.get("banco_id")
        comercial_id = request.GET.get("comercial_id")
        bancos_ids = list(Rol.objects.filter(tipo="banco", activo=True).values_list('usuario_id', flat=True))
        bancos = User.objects.filter(id__in=bancos_ids, is_active=True).order_by('username')

        comerciales = User.objects.none()

        if comercial_id:
            # Cargar el comercial específico y su banco asociado
            comercial = get_object_or_404(User, pk=comercial_id)
            context.update(CuadreService.generar_cuadre_completo(comercial, fecha))
            context["comercial_seleccionado"] = comercial
            context["vista"] = "superadmin_comercial"

            # Si el comercial tiene banco, mantenerlo en el context para el filtro
            if banco_id:
                banco_obj = User.objects.filter(pk=banco_id, id__in=bancos_ids).first()
                if banco_obj:
                    context["banco_seleccionado"] = banco_obj
                    # FIX_COMERCIALES_FILTRO: solo comerciales del banco
                    _sub_ids = Subordinacion.objects.filter(
                        jefe_id=banco_obj.id, activo=True
                    ).values_list('subordinado_id', flat=True)
                    _com_ids = Rol.objects.filter(
                        usuario_id__in=_sub_ids,
                        tipo='comercial',
                        activo=True
                    ).values_list('usuario_id', flat=True)
                    comerciales = User.objects.filter(
                        id__in=_com_ids, is_active=True
                    ).order_by('username')

        elif banco_id:
            banco = get_object_or_404(User, pk=banco_id, id__in=bancos_ids)
            # Cuadre del propio banco (antes faltaba esta llamada)
            context.update(CuadreService.generar_cuadre_completo(banco, fecha))
            context["resumen_general"] = CuadreService.calcular_resumen_banco(banco, fecha, fecha_hasta)
            context["banco_seleccionado"] = banco
            context["vista"] = "superadmin_banco"

            # FIX_COMERCIALES_FILTRO: comerciales (rol) del banco
            _sub_ids_b = Subordinacion.objects.filter(
                jefe_id=banco.id, activo=True
            ).values_list('subordinado_id', flat=True)
            _com_ids_b = Rol.objects.filter(
                usuario_id__in=_sub_ids_b,
                tipo='comercial',
                activo=True
            ).values_list('usuario_id', flat=True)
            comerciales = User.objects.filter(
                id__in=_com_ids_b, is_active=True
            ).order_by('username')

        else:
            # Sin filtros: resumen global + cuadre del propio superadmin
            context["resumen_general"] = CuadreService.calcular_resumen_superadmin(fecha, fecha_hasta)
            context.update(CuadreService.generar_cuadre_completo(usuario_actual, fecha))
            context["vista"] = "superadmin_resumen"
            # Sin banco seleccionado, no hay comerciales que listar
            # (se llenarán cuando elija un banco)

        context["bancos"] = bancos
        context["comerciales"] = comerciales
        return render(request, "roles/cuadre_diario.html", context)

    raise PermissionDenied("Rol no válido para ver el cuadre.")

@login_required
@require_POST
def api_actualizar_cuadre(request):
    try:
        data = json.loads(request.body)
        cuadre_id = data.get("cuadre_id")
        campo = data.get("campo")
        valor = Decimal(str(data.get("valor", "0")))
        cuadre = get_object_or_404(CuadreDiario, pk=cuadre_id)
        usuario = request.user
        puede_editar = False
        if usuario == cuadre.usuario:
            puede_editar = True
        elif usuario.is_superuser or Rol.objects.filter(usuario=usuario, tipo='superadmin', activo=True).exists():
            puede_editar = True
        else:
            es_banco = Rol.objects.filter(usuario=usuario, tipo='banco', activo=True).exists()
            if es_banco:
                es_subordinado = Subordinacion.objects.filter(jefe=usuario, subordinado=cuadre.usuario, activo=True).exists()
                if es_subordinado:
                    puede_editar = True
        if not puede_editar:
            return JsonResponse({"error": "Sin permiso"}, status=403)
        CAMPOS_EDITABLES = {'ajuste', 'envie', 'recibi', 'deuda', 'pagado'}
        if campo not in CAMPOS_EDITABLES:
            return JsonResponse({"error": "Campo no editable"}, status=400)
        if hasattr(cuadre, campo):
            setattr(cuadre, campo, valor)
            cuadre.save()
        context = CuadreService.generar_cuadre_completo(cuadre.usuario, cuadre.fecha)
        return JsonResponse({
            "fondo_tarjeta": str(context["control"]["fondo_actual"].get("tarjeta", 0)),
            "fondo_saldo": str(context["control"]["fondo_actual"].get("saldo", 0)),
            "fondo_cash": str(context["control"]["fondo_actual"].get("cash", 0)),
            "limpio_tarjeta": str(context["control"]["limpio"].get("tarjeta", 0)),
        })
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)

@login_required
def api_cerrar_cuadre(request, cuadre_id):
    cuadre = get_object_or_404(CuadreDiario, pk=cuadre_id)
    usuario = request.user
    puede_cerrar = False
    if usuario.is_superuser or Rol.objects.filter(usuario=usuario, tipo='superadmin', activo=True).exists():
        puede_cerrar = True
    else:
        es_banco = Rol.objects.filter(usuario=usuario, tipo='banco', activo=True).exists()
        if es_banco:
            es_subordinado = Subordinacion.objects.filter(jefe=usuario, subordinado=cuadre.usuario, activo=True).exists()
            if es_subordinado:
                puede_cerrar = True
    if not puede_cerrar:
        return JsonResponse({"error": "Sin permiso"}, status=403)
    cuadre.cerrado = True
    cuadre.save()
    return JsonResponse({"cerrado": True, "mensaje": "Cuadre cerrado correctamente."})

# ============================================================
# GESTIÓN DE NÚMEROS RESTRINGIDOS
# ============================================================

@login_required
def gestion_numeros_restringidos(request):
    user = request.user
    es_superadmin = user.is_superuser or user.roles.filter(tipo='superadmin', activo=True).exists()
    es_banco = user.roles.filter(tipo='banco', activo=True).exists()
    es_comercial = user.roles.filter(tipo='comercial', activo=True).exists()

    if not (es_superadmin or es_banco or es_comercial):
        messages.error(request, "No tienes permisos.")
        return redirect('publico:home')

    qs = NumeroRestringido.objects.all().select_related('sorteo', 'forma_juego', 'gestor')

    if es_superadmin:
        pass
    elif es_banco:
        comerciales_ids = Subordinacion.objects.filter(jefe=user, activo=True).values_list('subordinado_id', flat=True)
        qs = qs.filter(gestor__in=[user] + list(comerciales_ids))
    elif es_comercial:
        qs = qs.filter(gestor=user)

    sorteo_id = request.GET.get('sorteo')
    forma_juego_id = request.GET.get('forma_juego')
    activo = request.GET.get('activo')

    if sorteo_id:
        qs = qs.filter(sorteo_id=sorteo_id)
    if forma_juego_id:
        qs = qs.filter(forma_juego_id=forma_juego_id)
    if activo is not None:
        qs = qs.filter(activo=activo.lower() == 'true')

    qs = qs.order_by('-creado_en')

    paginator = Paginator(qs, 20)
    page = request.GET.get('page')
    page_obj = paginator.get_page(page)

    sorteos = Sorteo.objects.filter(activo=True).order_by('nombre')
    formas_juego = FormaJuego.objects.filter(activo=True).order_by('nombre')

    context = {
        'page_obj': page_obj,
        'sorteos': sorteos,
        'formas_juego': formas_juego,
        'filtro_sorteo': sorteo_id,
        'filtro_forma_juego': forma_juego_id,
        'filtro_activo': activo,
        'es_superadmin': es_superadmin,
        'es_banco': es_banco,
        'es_comercial': es_comercial,
    }
    return render(request, 'roles/gestion_numeros_restringidos.html', context)

@login_required
def crear_numero_restringido(request):
    user = request.user
    es_superadmin = user.is_superuser or user.roles.filter(tipo='superadmin', activo=True).exists()
    es_banco = user.roles.filter(tipo='banco', activo=True).exists()
    es_comercial = user.roles.filter(tipo='comercial', activo=True).exists()

    if not (es_superadmin or es_banco or es_comercial):
        messages.error(request, "No tienes permisos.")
        return redirect('publico:home')

    if request.method == 'POST':
        sorteo_id = request.POST.get('sorteo')
        forma_juego_id = request.POST.get('forma_juego')
        valores_raw = request.POST.get('valores', '').strip()
        fecha_vencimiento = request.POST.get('fecha_vencimiento')

        if not sorteo_id:
            messages.error(request, "Debes seleccionar un sorteo.")
            return redirect('roles:crear_numero_restringido')
        if not forma_juego_id:
            messages.error(request, "Debes seleccionar una forma de juego.")
            return redirect('roles:crear_numero_restringido')
        if not valores_raw:
            messages.error(request, "Debes ingresar al menos un valor.")
            return redirect('roles:crear_numero_restringido')
        if not fecha_vencimiento:
            messages.error(request, "Debes seleccionar una fecha de vencimiento.")
            return redirect('roles:crear_numero_restringido')

        try:
            sorteo = Sorteo.objects.get(id=sorteo_id, activo=True)
        except Sorteo.DoesNotExist:
            messages.error(request, "Sorteo no válido.")
            return redirect('roles:crear_numero_restringido')

        try:
            forma_juego = FormaJuego.objects.get(id=forma_juego_id, activo=True)
        except FormaJuego.DoesNotExist:
            messages.error(request, "Forma de juego no válida.")
            return redirect('roles:crear_numero_restringido')

        try:
            fecha_vencimiento = datetime.strptime(fecha_vencimiento, '%Y-%m-%d').date()
        except ValueError:
            messages.error(request, "Fecha de vencimiento no válida.")
            return redirect('roles:crear_numero_restringido')

        if fecha_vencimiento < timezone.now().date():
            messages.error(request, "La fecha de vencimiento no puede ser anterior a hoy.")
            return redirect('roles:crear_numero_restringido')

        valores = re.split(r'[,\s\n]+', valores_raw)
        valores = [v.strip().upper() for v in valores if v.strip()]

        if not valores:
            messages.error(request, "No se encontraron valores válidos.")
            return redirect('roles:crear_numero_restringido')

        creadas = 0
        errores = []

        for valor in valores:
            if NumeroRestringido.objects.filter(
                sorteo=sorteo,
                forma_juego=forma_juego,
                valor=valor,
                gestor=user
            ).exists():
                errores.append(f"'{valor}' ya está restringido para este sorteo y forma de juego.")
                continue

            try:
                NumeroRestringido.objects.create(
                    sorteo=sorteo,
                    forma_juego=forma_juego,
                    valor=valor,
                    fecha_vencimiento=fecha_vencimiento,
                    gestor=user,
                    activo=True
                )
                creadas += 1
            except Exception as e:
                errores.append(f"Error al crear '{valor}': {str(e)}")

        if creadas > 0:
            messages.success(request, f"✅ {creadas} restricción(es) creadas correctamente.")
        if errores:
            messages.warning(request, "⚠️ " + " | ".join(errores))

        return redirect('roles:gestion_numeros_restringidos')

    sorteos = Sorteo.objects.filter(activo=True).order_by('nombre')
    formas_juego = FormaJuego.objects.filter(activo=True).order_by('nombre')

    context = {
        'sorteos': sorteos,
        'formas_juego': formas_juego,
        'es_superadmin': es_superadmin,
        'es_banco': es_banco,
        'es_comercial': es_comercial,
    }
    return render(request, 'roles/crear_numero_restringido.html', context)

@login_required
def eliminar_numero_restringido(request, pk):
    user = request.user
    restriccion = get_object_or_404(NumeroRestringido, pk=pk)
    es_superadmin = user.is_superuser or user.roles.filter(tipo='superadmin', activo=True).exists()

    if not es_superadmin and restriccion.gestor != user:
        messages.error(request, "No puedes eliminar esta restricción porque no la creaste tú.")
        return redirect('roles:gestion_numeros_restringidos')

    if request.method == 'POST':
        restriccion.delete()
        messages.success(request, f"✅ Restricción '{restriccion.valor}' eliminada correctamente.")
        return redirect('roles:gestion_numeros_restringidos')

    context = {'restriccion': restriccion}
    return render(request, 'roles/eliminar_numero_restringido.html', context)

@login_required
def gestiones_banco(request):
    user = request.user

    es_banco = user.roles.filter(tipo='banco', activo=True).exists()
    es_superadmin = user.is_superuser or user.roles.filter(tipo='superadmin', activo=True).exists()
    es_comercial = user.roles.filter(tipo='comercial', activo=True).exists()

    if not (es_banco or es_superadmin or es_comercial):
        messages.error(request, "No tienes permisos para ver esta sección.")
        return redirect('publico:home')

    if es_superadmin:
        recargas = SolicitudRecarga.objects.all()
        cobros = SolicitudCobroPremio.objects.all()
        prestamos = Prestamo.objects.all()
        postpagos = Postpago.objects.filter(activo=True)
        fondos = Prestamo.objects.filter(metadata__tipo='fondos')
    elif es_banco:
        recargas = SolicitudRecarga.objects.filter(gestor=user)
        cobros = SolicitudCobroPremio.objects.filter(gestor=user)
        prestamos = Prestamo.objects.filter(prestamista=user)
        postpagos = Postpago.objects.filter(gestor=user, activo=True)
        fondos = Prestamo.objects.filter(prestamista=user, metadata__tipo='fondos')
    elif es_comercial:
        recargas = SolicitudRecarga.objects.filter(gestor=user)
        cobros = SolicitudCobroPremio.objects.filter(gestor=user)
        prestamos = Prestamo.objects.filter(prestamista=user)
        postpagos = Postpago.objects.filter(gestor=user, activo=True)
        fondos = Prestamo.objects.filter(solicitante=user, metadata__tipo='fondos')

    items = []

    for r in recargas:
        items.append({
            'id': r.id,
            'tipo': 'recarga',
            'cliente': r.cliente,
            'gestor': r.gestor,
            'monto': r.monto,
            'fecha': r.fecha_solicitud,
            'estado': r.estado,
            'objeto': r,
            'url_atender': f"/roles/responder-solicitud/recarga/{r.id}/aceptar/",
            'url_rechazar': f"/roles/responder-solicitud/recarga/{r.id}/rechazar/",
            'url_confirmar': f"/roles/responder-solicitud/recarga/{r.id}/confirmar/" if r.estado == 'aceptada' else None,
        })

    for c in cobros:
        items.append({
            'id': c.id,
            'tipo': 'cobro',
            'cliente': c.cliente,
            'gestor': c.gestor,
            'monto': c.monto,
            'fecha': c.fecha_solicitud,
            'estado': c.estado,
            'objeto': c,
            'url_atender': f"/roles/responder-solicitud/cobro/{c.id}/aceptar/",
            'url_rechazar': f"/roles/responder-solicitud/cobro/{c.id}/rechazar/",
            'url_confirmar': f"/roles/responder-solicitud/cobro/{c.id}/confirmar/" if c.estado == 'aceptada' else None,
        })

    for p in prestamos:
        items.append({
            'id': p.id,
            'tipo': 'prestamo',
            'cliente': p.solicitante,
            'gestor': p.prestamista,
            'monto': p.monto,
            'fecha': getattr(p, 'created_at', p.fecha_solicitud) if hasattr(p, 'fecha_solicitud') else p.created_at,
            'estado': p.estado,
            'objeto': p,
            'url_atender': f"/roles/responder-solicitud/prestamo/{p.id}/aceptar/",
            'url_rechazar': f"/roles/responder-solicitud/prestamo/{p.id}/rechazar/",
            'url_confirmar': None,
        })

    for pp in postpagos:
        items.append({
            'id': pp.id,
            'tipo': 'postpago',
            'cliente': pp.cliente,
            'gestor': pp.gestor,
            'monto': pp.monto,
            'fecha': pp.fecha_creacion,
            'estado': 'activo' if pp.activo else 'inactivo',
            'objeto': pp,
            'url_atender': None,
            'url_rechazar': None,
            'url_confirmar': None,
        })

    for f in fondos:
        items.append({
            'id': f.id,
            'tipo': 'fondos',
            'cliente': f.solicitante,
            'gestor': f.prestamista,
            'monto': f.monto,
            'fecha': getattr(f, 'created_at', f.fecha_solicitud) if hasattr(f, 'fecha_solicitud') else f.created_at,
            'estado': f.estado,
            'objeto': f,
            'url_atender': f"/roles/responder-solicitud/fondos/{f.id}/aceptar/",
            'url_rechazar': f"/roles/responder-solicitud/fondos/{f.id}/rechazar/",
            'url_confirmar': None,
        })

    estado_filtro = request.GET.get('estado', 'pendiente')
    if estado_filtro == 'pendiente':
        items = [i for i in items if i['estado'] in ['pendiente', 'solicitado', 'activo']]
    elif estado_filtro == 'todos':
        pass
    else:
        items = [i for i in items if i['estado'] == estado_filtro]

    items.sort(key=lambda x: x['fecha'], reverse=True)

    paginator = Paginator(items, 20)
    page = request.GET.get('page')
    items_page = paginator.get_page(page)

    context = {
        'items': items_page,
        'estado_filtro': estado_filtro,
        'es_superadmin': es_superadmin,
        'es_banco': es_banco,
        'es_comercial': es_comercial,
    }
    return render(request, 'roles/gestiones_banco.html', context)

# ============================================================
# RUTA DE PRUEBA
# ============================================================

# ═══════════════════════════════════════════════════════════════
# FIX_CUADRE_TRANSF_V1: gestión de transferencias en el cuadre
# ═══════════════════════════════════════════════════════════════

def _puede_gestionar_cuadre(user, cuadre):
    """Banco puede editar cuadre de sus comerciales. Superadmin todo. Comercial solo lectura."""
    if user.is_superuser or user.roles.filter(tipo='superadmin', activo=True).exists():
        return True
    es_banco = user.roles.filter(tipo='banco', activo=True).exists()
    if es_banco:
        es_subordinado = Subordinacion.objects.filter(
            jefe=user, subordinado=cuadre.usuario, activo=True
        ).exists()
        if es_subordinado:
            return True
    return False


@login_required
@require_POST
def agregar_transferencia(request, cuadre_id):
    """
    Agrega una transferencia al cuadre.
    Body (JSON): {'tipo': 'envie|recibi|ajuste', 'forma_pago': 'Tarjeta', 'monto': '100.00'}
    """
    try:
        cuadre = get_object_or_404(CuadreDiario, pk=cuadre_id)
        if not _puede_gestionar_cuadre(request.user, cuadre):
            return JsonResponse({'success': False, 'error': 'Sin permiso'}, status=403)

        data = json.loads(request.body)
        tipo = data.get('tipo', '')
        fp_nombre = data.get('forma_pago', '').strip()
        monto_raw = data.get('monto', '0')

        if tipo not in ('envie', 'recibi', 'ajuste'):
            return JsonResponse({'success': False, 'error': 'Tipo inválido'}, status=400)
        if not fp_nombre:
            return JsonResponse({'success': False, 'error': 'Falta forma de pago'}, status=400)

        try:
            monto = Decimal(str(monto_raw))
        except Exception:
            return JsonResponse({'success': False, 'error': 'Monto inválido'}, status=400)

        campo_lista = f'{tipo}_lista'
        lista_actual = getattr(cuadre, campo_lista) or {}
        valores = lista_actual.get(fp_nombre, [])
        valores.append(float(monto))
        lista_actual[fp_nombre] = valores
        setattr(cuadre, campo_lista, lista_actual)
        cuadre.save(update_fields=[campo_lista])

        return JsonResponse({
            'success': True,
            'valores': valores,
            'total': float(sum(Decimal(str(v)) for v in valores)),
        })
    except Exception as e:
        logger.error(f'Error agregando transferencia: {e}', exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_POST
def editar_transferencia(request, cuadre_id, idx):
    """
    Edita el valor en el índice idx de la lista.
    Body: {'tipo': ..., 'forma_pago': ..., 'monto': nuevo_monto}
    """
    try:
        cuadre = get_object_or_404(CuadreDiario, pk=cuadre_id)
        if not _puede_gestionar_cuadre(request.user, cuadre):
            return JsonResponse({'success': False, 'error': 'Sin permiso'}, status=403)

        data = json.loads(request.body)
        tipo = data.get('tipo', '')
        fp_nombre = data.get('forma_pago', '').strip()
        monto_raw = data.get('monto', '0')

        if tipo not in ('envie', 'recibi', 'ajuste'):
            return JsonResponse({'success': False, 'error': 'Tipo inválido'}, status=400)

        try:
            monto = Decimal(str(monto_raw))
        except Exception:
            return JsonResponse({'success': False, 'error': 'Monto inválido'}, status=400)

        campo_lista = f'{tipo}_lista'
        lista_actual = getattr(cuadre, campo_lista) or {}
        valores = lista_actual.get(fp_nombre, [])

        if idx < 0 or idx >= len(valores):
            return JsonResponse({'success': False, 'error': 'Índice fuera de rango'}, status=400)

        valores[idx] = float(monto)
        lista_actual[fp_nombre] = valores
        setattr(cuadre, campo_lista, lista_actual)
        cuadre.save(update_fields=[campo_lista])

        return JsonResponse({
            'success': True,
            'valores': valores,
            'total': float(sum(Decimal(str(v)) for v in valores)),
        })
    except Exception as e:
        logger.error(f'Error editando transferencia: {e}', exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_POST
def eliminar_transferencia(request, cuadre_id, idx):
    """
    Elimina el valor en el índice idx.
    Body: {'tipo': ..., 'forma_pago': ...}
    """
    try:
        cuadre = get_object_or_404(CuadreDiario, pk=cuadre_id)
        if not _puede_gestionar_cuadre(request.user, cuadre):
            return JsonResponse({'success': False, 'error': 'Sin permiso'}, status=403)

        data = json.loads(request.body)
        tipo = data.get('tipo', '')
        fp_nombre = data.get('forma_pago', '').strip()

        if tipo not in ('envie', 'recibi', 'ajuste'):
            return JsonResponse({'success': False, 'error': 'Tipo inválido'}, status=400)

        campo_lista = f'{tipo}_lista'
        lista_actual = getattr(cuadre, campo_lista) or {}
        valores = lista_actual.get(fp_nombre, [])

        if idx < 0 or idx >= len(valores):
            return JsonResponse({'success': False, 'error': 'Índice fuera de rango'}, status=400)

        valores.pop(idx)
        lista_actual[fp_nombre] = valores
        setattr(cuadre, campo_lista, lista_actual)
        cuadre.save(update_fields=[campo_lista])

        return JsonResponse({
            'success': True,
            'valores': valores,
            'total': float(sum(Decimal(str(v)) for v in valores)) if valores else 0,
        })
    except Exception as e:
        logger.error(f'Error eliminando transferencia: {e}', exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)}, status=500)



def test(request):
    return JsonResponse({'status': 'ok'})


# ============================================================
# ASIGNAR RECURSOS Y LIMITES (diseño B — checkbox por celda)
# ============================================================
@login_required
def asignar_recursos_limites(request):
    user = request.user
    es_superadmin = user.is_superuser or user.roles.filter(tipo='superadmin', activo=True).exists()
    es_banco = user.roles.filter(tipo='banco', activo=True).exists()

    if not (es_superadmin or es_banco):
        messages.error(request, "Sin permisos.")
        return redirect('publico:home')

    if es_superadmin:
        bancos = list(User.objects.filter(roles__tipo='banco', roles__activo=True, is_active=True).distinct().order_by('username'))
        comerciales = list(User.objects.filter(roles__tipo='comercial', roles__activo=True, is_active=True).distinct().order_by('username'))
    else:
        bancos = [user]
        ids = Subordinacion.objects.filter(jefe=user, activo=True).values_list('subordinado_id', flat=True)
        comerciales = list(User.objects.filter(id__in=ids, is_active=True).order_by('username'))

    todos_sorteos = list(Sorteo.objects.filter(activo=True).order_by('nombre'))
    todas_fj = list(FormaJuego.objects.filter(activo=True).order_by('nombre'))
    todas_fp = list(FormaPago.objects.filter(activo=True).exclude(nombre__iexact='bono').order_by('nombre'))

    destino_id = request.POST.get('destino') or request.GET.get('destino', '')
    destino = None
    es_destino_global = False
    es_destino_banco = False
    es_destino_comercial = False

    if destino_id == 'global':
        es_destino_global = True
    elif destino_id and str(destino_id).isdigit():
        destino = User.objects.filter(id=int(destino_id), is_active=True).first()
        if destino:
            es_destino_banco = destino.roles.filter(tipo='banco', activo=True).exists()
            es_destino_comercial = destino.roles.filter(tipo='comercial', activo=True).exists()

    if es_banco and not es_superadmin and destino and es_destino_comercial:
        if not Subordinacion.objects.filter(jefe=user, subordinado=destino, activo=True).exists():
            messages.error(request, "Ese comercial no es tu subordinado.")
            return redirect('roles:asignar_recursos_limites')

    # Recursos actuales (solo para bancos/comerciales, no para global)
    recursos_actuales = {'sorteos': [], 'fj': [], 'fp': []}
    if destino:
        filtro = {'banco': destino, 'comercial__isnull': True} if es_destino_banco else {'comercial': destino}
        for r in RecursoAsignado.objects.filter(**filtro, activo=True):
            if r.tipo == 'sorteo' and r.sorteo_id: recursos_actuales['sorteos'].append(r.sorteo_id)
            elif r.tipo == 'forma_juego' and r.forma_juego_id: recursos_actuales['fj'].append(r.forma_juego_id)
            elif r.tipo == 'forma_pago' and r.forma_pago_id: recursos_actuales['fp'].append(r.forma_pago_id)

    # ─── POST ───
    if request.method == 'POST':
        accion = request.POST.get('accion', '')

        if accion == 'cargar':
            if not destino_id:
                messages.error(request, "Selecciona un destino.")
                return redirect('roles:asignar_recursos_limites')
            return redirect(reverse('roles:asignar_recursos_limites') + "?destino=" + destino_id)

        if accion == 'generar':
            if not destino_id:
                messages.error(request, "Selecciona un destino.")
                return redirect('roles:asignar_recursos_limites')

            sorteos_ids = [int(x) for x in request.POST.getlist('sorteos') if str(x).isdigit()]
            fj_ids = [int(x) for x in request.POST.getlist('formas_juego') if str(x).isdigit()]
            fp_ids = [int(x) for x in request.POST.getlist('formas_pago') if str(x).isdigit()]

            if not (sorteos_ids and fj_ids and fp_ids):
                messages.error(request, "Marca al menos 1 sorteo, 1 FJ y 1 FP.")
                return redirect(reverse('roles:asignar_recursos_limites') + "?destino=" + destino_id)

            # Guardar recursos solo si es banco/comercial (no global)
            if not es_destino_global:
                with transaction.atomic():
                    filtro_del = {'banco': destino} if es_destino_banco else {'comercial': destino}
                    RecursoAsignado.objects.filter(**filtro_del).delete()
                    for sid in sorteos_ids:
                        RecursoAsignado.objects.create(
                            banco=destino if es_destino_banco else None,
                            comercial=destino if es_destino_comercial else None,
                            tipo='sorteo', sorteo_id=sid, activo=True, creado_por=user
                        )
                    for fj in fj_ids:
                        RecursoAsignado.objects.create(
                            banco=destino if es_destino_banco else None,
                            comercial=destino if es_destino_comercial else None,
                            tipo='forma_juego', forma_juego_id=fj, activo=True, creado_por=user
                        )
                    for fp in fp_ids:
                        RecursoAsignado.objects.create(
                            banco=destino if es_destino_banco else None,
                            comercial=destino if es_destino_comercial else None,
                            tipo='forma_pago', forma_pago_id=fp, activo=True, creado_por=user
                        )

            request.session['arl_sorteos'] = sorteos_ids
            request.session['arl_fj'] = fj_ids
            request.session['arl_fp'] = fp_ids
            request.session['arl_destino'] = destino_id
            messages.success(request, "Recursos cargados. Edita la matriz y guarda.")
            return redirect(reverse('roles:asignar_recursos_limites') + "?destino=" + destino_id + "&generado=1")

        if accion == 'guardar':
            if not destino_id:
                messages.error(request, "Sin destino.")
                return redirect('roles:asignar_recursos_limites')

            sorteos_ids = request.session.get('arl_sorteos', [])
            fj_ids = request.session.get('arl_fj', [])
            fp_ids = request.session.get('arl_fp', [])
            if not (sorteos_ids and fj_ids and fp_ids):
                messages.error(request, "Sesión expirada. Vuelve a generar la matriz.")
                return redirect(reverse('roles:asignar_recursos_limites') + "?destino=" + destino_id)

            guardados = 0
            desactivados = 0

            with transaction.atomic():
                for sid in sorteos_ids:
                    for fj_id in fj_ids:
                        for fp_id in fp_ids:
                            # Nombre de los checkboxes: chk_<fp>_<sorteo>_<fj>
                            chk_name = 'chk_%d_%d_%d' % (fp_id, sid, fj_id)
                            marcado = chk_name in request.POST

                            lim_str = (request.POST.get('limite_%d_%d_%d' % (fp_id, sid, fj_id)) or '').strip()
                            sob_str = (request.POST.get('sobrelimite_%d_%d_%d' % (fp_id, sid, fj_id)) or '').strip()
                            dos_str = (request.POST.get('dosis_%d_%d_%d' % (fp_id, sid, fj_id)) or '').strip()

                            filtros = {'sorteo_id': sid, 'forma_juego_id': fj_id, 'forma_pago_id': fp_id}
                            if es_destino_global:
                                filtros['banco'] = None
                                filtros['comercial'] = None
                                filtros['es_global'] = True
                            elif es_destino_banco:
                                filtros['banco'] = destino
                                filtros['comercial'] = None
                            else:
                                filtros['banco'] = None
                                filtros['comercial'] = destino

                            if not marcado:
                                # Desmarcada: desactivar si existía
                                LimiteApuesta.objects.filter(**filtros).update(activo=False)
                                DosisPago.objects.filter(**filtros).update(activo=False)
                                desactivados += 1
                                continue

                            # Marcada: guardar
                            try:
                                lim = Decimal(lim_str or '0')
                                sob = Decimal(sob_str or lim_str or '0')
                                dos = Decimal(dos_str) if dos_str else None
                            except Exception:
                                continue

                            defaults = {'monto_maximo': lim, 'monto_sobrelimite': sob, 'activo': True}
                            defaults['es_global'] = es_destino_global
                            LimiteApuesta.objects.update_or_create(**filtros, defaults=defaults)

                            if dos:
                                ddefaults = {'monto_por_peso': dos, 'activo': True}
                                ddefaults['es_global'] = es_destino_global
                                DosisPago.objects.update_or_create(**filtros, defaults=ddefaults)

                            guardados += 1

            # Guardar toggle "pagar fijo como corrido"
            from .models import ConfiguracionRecursos
            pagar_fc = (request.POST.get('pagar_fijo_como_corrido') == 'on')
            target_cfg_user = None
            if es_destino_global:
                target_cfg_user = user
            elif destino:
                target_cfg_user = destino
            if target_cfg_user:
                ConfiguracionRecursos.objects.update_or_create(
                    usuario=target_cfg_user,
                    defaults={
                        'pagar_fijo_como_corrido': pagar_fc,
                        'actualizado_por': user,
                    }
                )

            messages.success(request, "Guardados: %d. Desactivados: %d." % (guardados, desactivados))
            return redirect(reverse('roles:asignar_recursos_limites') + "?destino=" + destino_id + "&generado=1")

    # ─── GET ───
    matriz_filas = []
    fj_seleccionadas = []
    fp_seleccionadas = []
    sorteos_seleccionados_obj = []

    if request.GET.get('generado') == '1':
        # Recuperar de sesión, asegurando que coincidan con el destino actual
        destino_guardado = request.session.get('arl_destino', '')
        if str(destino_guardado) == str(destino_id):
            sorteos_ids = request.session.get('arl_sorteos', [])
            fj_ids = request.session.get('arl_fj', [])
            fp_ids = request.session.get('arl_fp', [])
        else:
            sorteos_ids = []
            fj_ids = []
            fp_ids = []

        if sorteos_ids and fj_ids and fp_ids:
            fj_seleccionadas = fj_ids
            fp_seleccionadas = fp_ids
            sorteos_seleccionados_obj = list(Sorteo.objects.filter(id__in=sorteos_ids).order_by('nombre'))

            fj_obj = list(FormaJuego.objects.filter(id__in=fj_ids).order_by('nombre'))
            fp_obj = list(FormaPago.objects.filter(id__in=fp_ids).order_by('nombre'))

            from .dosis_default import get_dosis_global, get_limite_por_forma, get_sobre_por_forma

            # Valores actuales del destino
            existentes_lim = {}
            existentes_dos = {}
            if es_destino_global:
                qs_l = LimiteApuesta.objects.filter(banco=None, comercial=None, es_global=True, activo=True)
                qs_d = DosisPago.objects.filter(banco=None, comercial=None, es_global=True, activo=True)
            elif es_destino_banco:
                qs_l = LimiteApuesta.objects.filter(banco=destino, comercial__isnull=True, activo=True)
                qs_d = DosisPago.objects.filter(banco=destino, comercial__isnull=True, activo=True)
            else:
                qs_l = LimiteApuesta.objects.filter(comercial=destino, activo=True)
                qs_d = DosisPago.objects.filter(comercial=destino, activo=True)

            for l in qs_l:
                existentes_lim[(l.sorteo_id, l.forma_juego_id, l.forma_pago_id)] = l
            for d in qs_d:
                existentes_dos[(d.sorteo_id, d.forma_juego_id, d.forma_pago_id)] = d

            for sorteo in sorteos_seleccionados_obj:
                filas_fj = []
                for fj in fj_obj:
                    celdas = []
                    for fp in fp_obj:
                        k = (sorteo.id, fj.id, fp.id)
                        tiene_guardado = k in existentes_lim
                        if tiene_guardado:
                            lim = float(existentes_lim[k].monto_maximo)
                            sob = float(existentes_lim[k].monto_sobrelimite)
                        else:
                            lim = float(get_limite_por_forma(fj.nombre))
                            sob = float(get_sobre_por_forma(fj.nombre))
                        if k in existentes_dos:
                            dos = float(existentes_dos[k].monto_por_peso)
                        else:
                            dos = float(get_dosis_global(fj.nombre) or 1)
                        celdas.append({
                            'fp_id': fp.id,
                            'fp_nombre': fp.nombre,
                            'limite': lim,
                            'sobre': sob,
                            'dosis': dos,
                            'marcado': tiene_guardado,
                        })
                    filas_fj.append({'fj': fj, 'celdas': celdas})
                matriz_filas.append({'sorteo': sorteo, 'filas_fj': filas_fj})

    # Leer toggle actual del destino
    pagar_fijo_como_corrido_actual = False
    try:
        from .models import ConfiguracionRecursos
        cfg_destino = None
        if es_destino_global:
            cfg_destino = ConfiguracionRecursos.objects.filter(usuario=user).first()
        elif destino:
            cfg_destino = ConfiguracionRecursos.objects.filter(usuario=destino).first()
        if cfg_destino:
            pagar_fijo_como_corrido_actual = cfg_destino.pagar_fijo_como_corrido
    except Exception:
        pass

    # Etiqueta del destino
    if es_destino_global:
        destino_nombre = "🌐 Global (valores de superadmin)"
    elif destino:
        tipo = "🏦 Banco" if es_destino_banco else "👤 Comercial"
        destino_nombre = "%s: %s" % (tipo, destino.username)
    else:
        destino_nombre = ""

    context = {
        'bancos': bancos,
        'comerciales': comerciales,
        'todos_sorteos': todos_sorteos,
        'todas_fj': todas_fj,
        'todas_fp': todas_fp,
        'destino': destino,
        'destino_id': destino_id,
        'destino_nombre': destino_nombre,
        'es_destino_global': es_destino_global,
        'es_destino_banco': es_destino_banco,
        'es_destino_comercial': es_destino_comercial,
        'recursos_actuales': recursos_actuales,
        'matriz_filas': matriz_filas,
        'sorteos_seleccionados_obj': sorteos_seleccionados_obj,
        'fp_seleccionadas': fp_seleccionadas,
        'fj_seleccionadas': fj_seleccionadas,
        'es_superadmin': es_superadmin,
        'es_banco': es_banco,
        'pagar_fijo_como_corrido_actual': pagar_fijo_como_corrido_actual,
    }
    return render(request, 'roles/asignar_recursos_limites.html', context)

@login_required
def asignar_recursos_limites(request):
    user = request.user
    es_superadmin = user.is_superuser or user.roles.filter(tipo='superadmin', activo=True).exists()
    es_banco = user.roles.filter(tipo='banco', activo=True).exists()

    if not (es_superadmin or es_banco):
        messages.error(request, "Sin permisos.")
        return redirect('publico:home')

    if es_superadmin:
        bancos = list(User.objects.filter(roles__tipo='banco', roles__activo=True, is_active=True).distinct().order_by('username'))
        comerciales = list(User.objects.filter(roles__tipo='comercial', roles__activo=True, is_active=True).distinct().order_by('username'))
    else:
        bancos = [user]
        ids = Subordinacion.objects.filter(jefe=user, activo=True).values_list('subordinado_id', flat=True)
        comerciales = list(User.objects.filter(id__in=ids, is_active=True).order_by('username'))

    todos_sorteos = list(Sorteo.objects.filter(activo=True).order_by('nombre'))
    todas_fj = list(FormaJuego.objects.filter(activo=True).order_by('nombre'))
    todas_fp = list(FormaPago.objects.filter(activo=True).order_by('nombre'))

    destino_id = request.POST.get('destino') or request.GET.get('destino', '')
    destino = None
    if destino_id and str(destino_id).isdigit():
        destino = User.objects.filter(id=int(destino_id), is_active=True).first()

    es_destino_banco = False
    es_destino_comercial = False
    if destino:
        es_destino_banco = destino.roles.filter(tipo='banco', activo=True).exists()
        es_destino_comercial = destino.roles.filter(tipo='comercial', activo=True).exists()

    if es_banco and not es_superadmin and destino and es_destino_comercial:
        if not Subordinacion.objects.filter(jefe=user, subordinado=destino, activo=True).exists():
            messages.error(request, "Ese comercial no es tu subordinado.")
            return redirect('roles:asignar_recursos_limites')

    recursos_actuales = {'sorteos': [], 'fj': [], 'fp': []}
    if destino:
        filtro = {'banco': destino, 'comercial__isnull': True} if es_destino_banco else {'comercial': destino, 'banco__isnull': True}
        for r in RecursoAsignado.objects.filter(**filtro, activo=True):
            if r.tipo == 'sorteo' and r.sorteo_id: recursos_actuales['sorteos'].append(r.sorteo_id)
            elif r.tipo == 'forma_juego' and r.forma_juego_id: recursos_actuales['fj'].append(r.forma_juego_id)
            elif r.tipo == 'forma_pago' and r.forma_pago_id: recursos_actuales['fp'].append(r.forma_pago_id)

    if request.method == 'POST':
        accion = request.POST.get('accion', '')
        if not destino:
            messages.error(request, "Selecciona un destino.")
            return redirect('roles:asignar_recursos_limites')

        if accion == 'cargar':
            return redirect(reverse('roles:asignar_recursos_limites') + "?destino=" + str(destino.id))

        if accion == 'generar':
            sorteos_ids = [int(x) for x in request.POST.getlist('sorteos') if str(x).isdigit()]
            fj_ids = [int(x) for x in request.POST.getlist('formas_juego') if str(x).isdigit()]
            fp_ids = [int(x) for x in request.POST.getlist('formas_pago') if str(x).isdigit()]

            if not (sorteos_ids and fj_ids and fp_ids):
                messages.error(request, "Selecciona al menos 1 sorteo, 1 FJ y 1 FP.")
                return redirect(reverse('roles:asignar_recursos_limites') + "?destino=" + str(destino.id))

            with transaction.atomic():
                filtro_del = {'banco': destino} if es_destino_banco else {'comercial': destino}
                RecursoAsignado.objects.filter(**filtro_del).delete()
                for sid in sorteos_ids:
                    RecursoAsignado.objects.create(
                        banco=destino if es_destino_banco else None,
                        comercial=destino if es_destino_comercial else None,
                        tipo='sorteo', sorteo_id=sid, activo=True, creado_por=user
                    )
                for fj in fj_ids:
                    RecursoAsignado.objects.create(
                        banco=destino if es_destino_banco else None,
                        comercial=destino if es_destino_comercial else None,
                        tipo='forma_juego', forma_juego_id=fj, activo=True, creado_por=user
                    )
                for fp in fp_ids:
                    RecursoAsignado.objects.create(
                        banco=destino if es_destino_banco else None,
                        comercial=destino if es_destino_comercial else None,
                        tipo='forma_pago', forma_pago_id=fp, activo=True, creado_por=user
                    )

            request.session['arl_sorteos'] = sorteos_ids
            request.session['arl_fj'] = fj_ids
            request.session['arl_fp'] = fp_ids
            primer = sorteos_ids[0]
            messages.success(request, "Recursos asignados a " + destino.username + ". Edita sorteo por sorteo.")
            return redirect(reverse('roles:asignar_recursos_limites') + "?destino=" + str(destino.id) + "&generado=1&sorteo_activo=" + str(primer))

        if accion == 'guardar':
            sorteo_id = request.POST.get('sorteo_activo')
            if not sorteo_id or not str(sorteo_id).isdigit():
                messages.error(request, "Sorteo activo invalido.")
                return redirect(reverse('roles:asignar_recursos_limites') + "?destino=" + str(destino.id) + "&generado=1")

            sorteos_ids = request.session.get('arl_sorteos', [])
            fj_ids = request.session.get('arl_fj', [])
            fp_ids = request.session.get('arl_fp', [])
            if not (sorteos_ids and fj_ids and fp_ids):
                messages.error(request, "Sesion expirada. Vuelve a generar la matriz.")
                return redirect(reverse('roles:asignar_recursos_limites') + "?destino=" + str(destino.id))

            sorteo_id = int(sorteo_id)
            guardados = 0
            with transaction.atomic():
                for fp_id in fp_ids:
                    for fj_id in fj_ids:
                        key = 'limite_' + str(fp_id) + '_' + str(sorteo_id) + '_' + str(fj_id)
                        if key not in request.POST:
                            continue
                        lim_str = (request.POST.get(key) or '').strip()
                        sob_str = (request.POST.get('sobrelimite_' + str(fp_id) + '_' + str(sorteo_id) + '_' + str(fj_id)) or '').strip()
                        dos_str = (request.POST.get('dosis_' + str(fp_id) + '_' + str(sorteo_id) + '_' + str(fj_id)) or '').strip()
                        try:
                            lim = Decimal(lim_str or '0')
                            sob = Decimal(sob_str or lim_str or '0')
                            dos = Decimal(dos_str) if dos_str else None
                        except Exception:
                            continue
                        if lim <= 0 and sob <= 0 and not dos:
                            continue

                        filtros = {'sorteo_id': sorteo_id, 'forma_juego_id': fj_id, 'forma_pago_id': fp_id}
                        if es_destino_banco:
                            filtros['banco'] = destino
                            filtros['comercial'] = None
                        else:
                            filtros['banco'] = None
                            filtros['comercial'] = destino

                        LimiteApuesta.objects.update_or_create(
                            **filtros,
                            defaults={'monto_maximo': lim, 'monto_sobrelimite': sob, 'activo': True}
                        )
                        if dos:
                            DosisPago.objects.update_or_create(
                                **filtros,
                                defaults={'monto_por_peso': dos, 'activo': True}
                            )
                        guardados += 1

            messages.success(request, "Guardados " + str(guardados) + " registros del sorteo seleccionado.")
            return redirect(reverse('roles:asignar_recursos_limites') + "?destino=" + str(destino.id) + "&generado=1&sorteo_activo=" + str(sorteo_id))

    matriz_filas = []
    sorteos_seleccionados_ids = []
    fj_seleccionadas_ids = []
    fp_seleccionadas_ids = []
    sorteo_activo_obj = None

    if destino and request.GET.get('generado') == '1':
        sorteos_seleccionados_ids = request.session.get('arl_sorteos', [])
        fj_seleccionadas_ids = request.session.get('arl_fj', [])
        fp_seleccionadas_ids = request.session.get('arl_fp', [])

        if sorteos_seleccionados_ids and fj_seleccionadas_ids and fp_seleccionadas_ids:
            sorteo_activo_id = request.GET.get('sorteo_activo')
            if not sorteo_activo_id or not str(sorteo_activo_id).isdigit():
                sorteo_activo_id = sorteos_seleccionados_ids[0]
            else:
                sorteo_activo_id = int(sorteo_activo_id)

            sorteo_activo_obj = Sorteo.objects.filter(id=sorteo_activo_id).first()
            if sorteo_activo_obj:
                fj_obj = list(FormaJuego.objects.filter(id__in=fj_seleccionadas_ids).order_by('nombre'))
                fp_obj = list(FormaPago.objects.filter(id__in=fp_seleccionadas_ids).order_by('nombre'))

                from .dosis_default import get_dosis_global, get_limite_por_forma, get_sobre_por_forma

                filtro_exist = {'banco': destino, 'comercial__isnull': True} if es_destino_banco else {'comercial': destino}
                existentes_lim = {}
                existentes_dos = {}
                for l in LimiteApuesta.objects.filter(**filtro_exist, sorteo_id=sorteo_activo_id, activo=True):
                    existentes_lim[(l.forma_juego_id, l.forma_pago_id)] = l
                for d in DosisPago.objects.filter(**filtro_exist, sorteo_id=sorteo_activo_id, activo=True):
                    existentes_dos[(d.forma_juego_id, d.forma_pago_id)] = d

                for fj in fj_obj:
                    celdas = []
                    for fp in fp_obj:
                        k = (fj.id, fp.id)
                        if k in existentes_lim:
                            lim = float(existentes_lim[k].monto_maximo)
                            sob = float(existentes_lim[k].monto_sobrelimite)
                        else:
                            lim = float(get_limite_por_forma(fj.nombre))
                            sob = float(get_sobre_por_forma(fj.nombre))
                        if k in existentes_dos:
                            dos = float(existentes_dos[k].monto_por_peso)
                        else:
                            dos = float(get_dosis_global(fj.nombre) or 1)
                        celdas.append({'fp_id': fp.id, 'limite': lim, 'sobre': sob, 'dosis': dos})
                    matriz_filas.append({'fj': fj, 'celdas': celdas})

    sorteos_seleccionados_obj = list(Sorteo.objects.filter(id__in=sorteos_seleccionados_ids).order_by('nombre'))

    context = {
        'bancos': bancos, 'comerciales': comerciales,
        'todos_sorteos': todos_sorteos, 'todas_fj': todas_fj, 'todas_fp': todas_fp,
        'destino': destino,
        'es_destino_banco': es_destino_banco,
        'es_destino_comercial': es_destino_comercial,
        'recursos_actuales': recursos_actuales,
        'matriz_filas': matriz_filas,
        'sorteo_activo': sorteo_activo_obj,
        'sorteos_seleccionados_obj': sorteos_seleccionados_obj,
        'fp_seleccionadas': fp_seleccionadas_ids,
        'fj_seleccionadas_ids': fj_seleccionadas_ids,
        'es_superadmin': es_superadmin,
        'es_banco': es_banco,
    }
    return render(request, 'roles/asignar_recursos_limites.html', context)

@login_required
def ascender_a_comercial(request, user_id):
    usuario_a_ascender = get_object_or_404(User, id=user_id)
    usuario_actual = request.user
    es_superadmin = usuario_actual.is_superuser or usuario_actual.roles.filter(tipo='superadmin', activo=True).exists()
    es_banco = Rol.objects.filter(usuario=usuario_actual, tipo='banco', activo=True).exists()
    if not (es_superadmin or es_banco):
        messages.error(request, "No tienes permiso para ascender usuarios.")
        return redirect('lista_clientes')
    if es_banco and not es_superadmin:
        usuarios_visibles = get_usuarios_visibles(request)
        if usuario_a_ascender not in usuarios_visibles:
            messages.error(request, "No puedes ascender a este usuario porque no está en tu red.")
            return redirect('lista_clientes')
    jefe = usuario_actual
    if es_banco and not es_superadmin:
        suscripcion = SuscripcionBanco.objects.filter(banco=jefe, activo=True).first()
        if suscripcion and not suscripcion.puede_ascender_comercial():
            messages.error(request, f"Has alcanzado el límite de {suscripcion.comerciales_permitidos} comerciales. Debes solicitar más cupo al superadmin.")
            return redirect('lista_clientes')
    with transaction.atomic():
        RecursoAsignado.objects.filter(comercial=usuario_a_ascender).delete()
        LimiteApuesta.objects.filter(comercial=usuario_a_ascender).delete()
        DosisPago.objects.filter(comercial=usuario_a_ascender).delete()
        Rol.objects.filter(usuario=usuario_a_ascender, activo=True).exclude(tipo='comercial').update(activo=False)
        rol, created = Rol.objects.get_or_create(usuario=usuario_a_ascender, tipo='comercial', defaults={'activo': True, 'banco_asignado': jefe})
        if not created:
            rol.activo = True
            rol.banco_asignado = jefe
            rol.save()
        Subordinacion.objects.update_or_create(jefe=jefe, subordinado=usuario_a_ascender, defaults={'activo': True, 'es_temporal': False})
        recursos_banco = RecursoAsignado.objects.filter(banco=jefe, activo=True)
        recursos_asignados = 0
        if recursos_banco.exists():
            for recurso in recursos_banco:
                RecursoAsignado.objects.get_or_create(banco=None, comercial=usuario_a_ascender, tipo=recurso.tipo, sorteo=recurso.sorteo, forma_juego=recurso.forma_juego, forma_pago=recurso.forma_pago, defaults={'activo': True, 'creado_por': usuario_actual})
                recursos_asignados += 1
            sorteos_ids = recursos_banco.filter(tipo='sorteo').values_list('sorteo_id', flat=True)
            formas_juego_ids = recursos_banco.filter(tipo='forma_juego').values_list('forma_juego_id', flat=True)
            formas_pago_ids = recursos_banco.filter(tipo='forma_pago').values_list('forma_pago_id', flat=True)
            asignar_limites_dosis_predeterminados(usuario=usuario_a_ascender, recursos_sorteos=sorteos_ids, recursos_formas_juego=formas_juego_ids, recursos_formas_pago=formas_pago_ids, banco_origen=jefe)
            mensaje_recursos = f" con {recursos_asignados} recursos y límites/dosis heredados del banco"
        else:
            sorteos_ids = Sorteo.objects.filter(activo=True).values_list('id', flat=True)
            formas_juego_ids = FormaJuego.objects.filter(activo=True).values_list('id', flat=True)
            formas_pago_ids = FormaPago.objects.filter(activo=True).values_list('id', flat=True)
            for sorteo in Sorteo.objects.filter(activo=True):
                RecursoAsignado.objects.get_or_create(banco=None, comercial=usuario_a_ascender, tipo='sorteo', sorteo=sorteo, defaults={'activo': True, 'creado_por': usuario_actual})
                recursos_asignados += 1
            for forma_juego in FormaJuego.objects.filter(activo=True):
                RecursoAsignado.objects.get_or_create(banco=None, comercial=usuario_a_ascender, tipo='forma_juego', forma_juego=forma_juego, defaults={'activo': True, 'creado_por': usuario_actual})
                recursos_asignados += 1
            for forma_pago in FormaPago.objects.filter(activo=True):
                RecursoAsignado.objects.get_or_create(banco=None, comercial=usuario_a_ascender, tipo='forma_pago', forma_pago=forma_pago, defaults={'activo': True, 'creado_por': usuario_actual})
                recursos_asignados += 1
            asignar_limites_dosis_predeterminados(usuario=usuario_a_ascender, recursos_sorteos=sorteos_ids, recursos_formas_juego=formas_juego_ids, recursos_formas_pago=formas_pago_ids, banco_origen=None)
            mensaje_recursos = f" con {recursos_asignados} recursos globales y límites/dosis por defecto"
        crear_notificacion(usuario=usuario_a_ascender, tipo='sistema', mensaje=f"Has sido ascendido a comercial por {jefe.username}{mensaje_recursos}.")
        if es_banco and not es_superadmin:
            suscripcion = SuscripcionBanco.objects.filter(banco=jefe, activo=True).first()
            crear_notificacion(usuario=jefe, tipo='sistema',
                mensaje=f"✅ Has ascendido a {usuario_a_ascender.username} como comercial. Costo mensual actualizado: ${suscripcion.costo_mensual() if suscripcion else '0'} ({suscripcion.comerciales_activos() if suscripcion else 0} comerciales activos, {suscripcion.recursos_activos().count() if suscripcion else 0} recursos)",
                datos={'comercial': usuario_a_ascender.username, 'comerciales_activos': suscripcion.comerciales_activos() if suscripcion else 0, 'recursos_activos': suscripcion.recursos_activos().count() if suscripcion else 0, 'costo_mensual': float(suscripcion.costo_mensual()) if suscripcion else 0},
                prioridad='media', categoria='financiera')

    anular_bonos_usuario(usuario_a_ascender)

    messages.success(request, f"✅ {usuario_a_ascender.username} ascendido a comercial bajo {jefe.username} con {recursos_asignados} recursos y límites/dosis heredados.")
    return redirect('lista_clientes')

@login_required
@csrf_exempt
def asignar_rol_usuario(request):
    """
    Vista para que bancos y superadmins asignen/remuevan roles a usuarios.
    Espera un POST con {'user_id': int, 'nuevo_rol': str}
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)

    try:
        data = json.loads(request.body)
        user_id = data.get('user_id')
        nuevo_rol = data.get('nuevo_rol')

        if not user_id or not nuevo_rol:
            return JsonResponse({'success': False, 'error': 'Faltan parámetros (user_id, nuevo_rol)'}, status=400)

        usuario_actual = request.user
        es_autorizado = (
            usuario_actual.is_superuser or
            usuario_actual.roles.filter(tipo__in=['superadmin', 'banco'], activo=True).exists()
        )
        if not es_autorizado:
            return JsonResponse({'success': False, 'error': 'No tienes permiso para asignar roles'}, status=403)

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Usuario no encontrado'}, status=404)

        if nuevo_rol == 'superadmin':
            user.is_superuser = True
        else:
            if user.is_superuser:
                user.is_superuser = False
        user.save()

        Rol.objects.filter(usuario=user, tipo=nuevo_rol).update(activo=False)

        rol, created = Rol.objects.get_or_create(
            usuario=user,
            tipo=nuevo_rol,
            defaults={'activo': True}
        )
        if not created:
            rol.activo = True
            rol.save()

        return JsonResponse({
            'success': True,
            'message': f'✅ Rol "{nuevo_rol}" asignado a {user.username} (ID: {user.id})'
        })

    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'JSON inválido'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
def recarga_directa(request):
    # AUTO_APPLIED_POSTPAGO
    user = request.user
    es_superadmin = user.is_superuser or user.roles.filter(tipo='superadmin', activo=True).exists()
    es_banco = user.roles.filter(tipo='banco', activo=True).exists()
    es_comercial = user.roles.filter(tipo='comercial', activo=True).exists()
    if not (es_superadmin or es_banco or es_comercial):
        messages.error(request, "Sin permisos para recargar.")
        return redirect('publico:home')

    usuario_preseleccionado_id = request.GET.get('usuario_id', '').strip()
    fp_preseleccionada_id      = request.GET.get('forma_pago_id', '').strip()
    volver                     = request.GET.get('volver', '').strip()

    usuario_preseleccionado = None
    fp_preseleccionada = None
    if usuario_preseleccionado_id.isdigit():
        usuario_preseleccionado = User.objects.filter(id=int(usuario_preseleccionado_id), is_active=True).first()
    if fp_preseleccionada_id.isdigit():
        fp_preseleccionada = FormaPago.objects.filter(id=int(fp_preseleccionada_id), activo=True).first()

    if request.method == 'POST':
        usuario_id    = request.POST.get('usuario_id', '').strip()
        monto_str     = request.POST.get('monto', '').strip()
        forma_pago_id = request.POST.get('forma_pago', '').strip()
        tipo_mov      = request.POST.get('tipo_movimiento', 'recarga').strip().lower()

        if tipo_mov not in ('recarga', 'postpago', 'ajuste'):
            messages.error(request, "Tipo invalido.")
            return redirect('roles:recarga_directa')
        try:
            usuario = User.objects.get(id=usuario_id, is_active=True)
        except User.DoesNotExist:
            messages.error(request, "Usuario no valido.")
            return redirect('roles:recarga_directa')
        try:
            monto = Decimal(monto_str)
            if monto <= 0: raise ValueError()
        except Exception:
            messages.error(request, "Monto invalido.")
            return redirect('roles:recarga_directa')
        try:
            forma_pago = FormaPago.objects.get(id=forma_pago_id, activo=True)
        except Exception:
            messages.error(request, "Forma de pago no valida.")
            return redirect('roles:recarga_directa')

        if tipo_mov == 'ajuste':
            signo  = (request.POST.get('signo') or 'sumar').strip().lower()
            motivo = (request.POST.get('motivo_ajuste') or '').strip()[:200]
            if signo not in ('sumar', 'restar'):
                messages.error(request, "Signo invalido.")
                return redirect('roles:recarga_directa')
            if not motivo:
                messages.error(request, "El motivo del ajuste es obligatorio.")
                return redirect('roles:recarga_directa')

            fondo_qs = Fondo.objects.select_for_update().filter(
                usuario=usuario, forma_pago=forma_pago, activo=True)
            if not es_superadmin:
                fondo_qs = fondo_qs.filter(asignado_por=user)

            with transaction.atomic():
                fondo = fondo_qs.first()
                if not fondo:
                    if not es_superadmin and not Fondo.objects.filter(
                        usuario=usuario, asignado_por=user, activo=True).exists():
                        messages.error(request, "Sin permiso para ajustar este cliente.")
                        return redirect('roles:recarga_directa')
                    fondo = Fondo.objects.create(
                        usuario=usuario, forma_pago=forma_pago,
                        asignado_por=user, monto=Decimal('0.00'), activo=True)

                saldo_antes = fondo.monto or Decimal('0.00')
                delta = monto if signo == 'sumar' else -monto
                fondo.monto = saldo_antes + delta
                fondo.save(update_fields=['monto', 'actualizado_en'])

                MovimientoFondo.objects.create(
                    emisor=user if signo == 'restar' else None,
                    receptor=usuario, forma_pago=forma_pago,
                    monto=delta, tipo='ajuste', estado='confirmado',
                    motivo=motivo,
                    nota=("Ajuste +" if signo == 'sumar' else "Ajuste -") + " " + forma_pago.nombre + ": " + motivo,
                    saldo_antes=saldo_antes, saldo_despues=fondo.monto,
                    datos_transferencia={'ajuste_manual': True, 'signo': signo,
                                         'gestor': user.username, 'gestor_id': user.id}
                )

            crear_notificacion(
                usuario=usuario, tipo='info',
                mensaje="Ajuste " + ("a favor" if signo == 'sumar' else "en contra") + " de $" + str(monto) + " en " + forma_pago.nombre + ". Motivo: " + motivo,
                datos={'monto': float(monto), 'signo': signo, 'forma_pago': forma_pago.nombre,
                       'gestor': user.username, 'saldo_antes': float(saldo_antes),
                       'saldo_despues': float(fondo.monto), 'motivo': motivo},
                prioridad='alta', categoria='financiera')
            messages.success(request, "Ajuste " + ("+" if signo == 'sumar' else "-") + "$" + str(monto) + " a " + usuario.username + ". Nuevo saldo: $" + str(fondo.monto))
            if volver == 'apostar':
                return redirect(reverse('jugadas:apostar') + "?cliente_id=" + str(usuario.id))
            return redirect('roles:recarga_directa')

        if tipo_mov == 'recarga':
            solicitud = SolicitudRecarga.objects.create(
                cliente=usuario, gestor=user, forma_pago=forma_pago, monto=monto,
                estado='pagada', mensaje_cliente="Recarga directa por " + user.username,
                creado_por=user)
            from .utils import _aplicar_ingreso_a_fondo
            monto_neto, descontado = _aplicar_ingreso_a_fondo(
                cliente=usuario, gestor=user, forma_pago=forma_pago, monto=monto)
            msg = user.username + " te recargo $" + str(monto) + " en " + forma_pago.nombre
            if descontado > 0:
                msg += ". Aplicado al postpago: $" + str(descontado) + ". Al fondo: $" + str(monto_neto)
            crear_notificacion(usuario=usuario, tipo='info', mensaje=msg,
                datos={'monto_bruto': float(monto), 'postpago_descontado': float(descontado),
                       'monto_neto': float(monto_neto), 'forma_pago': forma_pago.nombre,
                       'gestor': user.username},
                prioridad='alta', categoria='financiera')
            messages.success(request, "Recarga de $" + str(monto) + " a " + usuario.username)
            if volver == 'apostar':
                return redirect(reverse('jugadas:apostar') + "?cliente_id=" + str(usuario.id) + "&recarga_ok=1")
            return redirect('roles:recarga_directa')

        messages.error(request, "Postpago manual deshabilitado (Fase 1).")
        return redirect('roles:recarga_directa')

    q = request.GET.get('q', '').strip()
    usuarios = User.objects.filter(is_active=True).exclude(id=user.id).order_by('id')
    if q:
        usuarios = usuarios.filter(Q(username__icontains=q) | Q(perfil__telefono__icontains=q)).distinct()
    paginator = Paginator(usuarios, 20)
    page = request.GET.get('page')
    try:
        usuarios_page = paginator.page(page)
    except PageNotAnInteger:
        usuarios_page = paginator.page(1)
    except EmptyPage:
        usuarios_page = paginator.page(paginator.num_pages)
    from pagos.utils import get_formas_pago_activas
    formas_pago = get_formas_pago_activas()
    return render(request, 'roles/recarga_directa.html', {
        'formas_pago': formas_pago,
        'usuarios': usuarios_page, 'formas_pago': formas_pago, 'q': q,
        'es_superadmin': es_superadmin, 'es_banco': es_banco, 'es_comercial': es_comercial,
        'usuario_preseleccionado_id': usuario_preseleccionado_id,
        'fp_preseleccionada_id': fp_preseleccionada_id, 'volver': volver,
        'usuario_preseleccionado': usuario_preseleccionado,
        'fp_preseleccionada': fp_preseleccionada,
    })

@login_required
def gestionar_solicitudes_suscripcion(request):
    if not (request.user.is_superuser or request.user.roles.filter(tipo='superadmin', activo=True).exists()):
        messages.error(request, "No tienes permisos.")
        return redirect('publico:home')
    solicitudes = SuscripcionBanco.objects.filter(solicitud_pendiente=True, activo=True)
    if request.method == 'POST':
        suscripcion_id = request.POST.get('suscripcion_id')
        accion = request.POST.get('accion')
        suscripcion = get_object_or_404(SuscripcionBanco, id=suscripcion_id)
        if not suscripcion.solicitud_pendiente:
            messages.warning(request, "Esta solicitud ya fue procesada.")
            return redirect('roles:gestionar_solicitudes_suscripcion')
        if accion == 'aprobar':
            detalle = suscripcion.solicitud_detalle
            tipo = suscripcion.solicitud_tipo
            with transaction.atomic():
                if tipo in ('recursos', 'ambos'):
                    recursos_ids = detalle.get('recursos_ids', [])
                    for r_id in recursos_ids:
                        try:
                            recurso = RecursoAsignado.objects.get(id=r_id, activo=True, banco=None, comercial=None)
                            recurso.banco = suscripcion.banco
                            recurso.save()
                        except RecursoAsignado.DoesNotExist:
                            continue
                if tipo in ('comerciales', 'ambos'):
                    suscripcion.comerciales_permitidos = detalle.get('comerciales_solicitados', 0)
                suscripcion.solicitud_pendiente = False
                suscripcion.solicitud_tipo = None
                suscripcion.solicitud_detalle = {}
                suscripcion.save()
                crear_notificacion(
                    usuario=suscripcion.banco, tipo='suscripcion',
                    mensaje="✅ Tu solicitud de cambios ha sido APROBADA.",
                    datos={'suscripcion_id': suscripcion.id, 'tipo': tipo,
                           'detalle': detalle,
                           'url_detalle': '/roles/panel-suscripcion-banco/'},
                    prioridad='alta', categoria='financiera')
                messages.success(request, f"✅ Solicitud de {suscripcion.banco.username} aprobada.")
        elif accion == 'rechazar':
            suscripcion.solicitud_pendiente = False
            suscripcion.solicitud_tipo = None
            suscripcion.solicitud_detalle = {}
            suscripcion.save()
            crear_notificacion(
                usuario=suscripcion.banco, tipo='suscripcion',
                mensaje="❌ Tu solicitud de cambios ha sido RECHAZADA.",
                datos={'suscripcion_id': suscripcion.id,
                       'url_detalle': '/roles/panel-suscripcion-banco/'},
                prioridad='media', categoria='financiera')
            messages.warning(request, f"❌ Solicitud de {suscripcion.banco.username} rechazada.")
        return redirect('roles:gestionar_solicitudes_suscripcion')
    context = {'solicitudes': solicitudes}
    return render(request, 'roles/gestionar_solicitudes_suscripcion.html', context)


@login_required
def registrar_pago_banco(request, suscripcion_id):
    if not (request.user.is_superuser or request.user.roles.filter(tipo='superadmin', activo=True).exists()):
        messages.error(request, "No tienes permisos.")
        return redirect('publico:home')
    suscripcion = get_object_or_404(SuscripcionBanco, id=suscripcion_id)
    if request.method == 'POST':
        monto = request.POST.get('monto')
        try:
            monto = Decimal(monto)
            if monto <= 0:
                raise ValueError("El monto debe ser mayor a 0")
        except (InvalidOperation, TypeError, ValueError):
            messages.error(request, "Monto inválido.")
            return redirect('roles:panel_bancos')
        suscripcion.ultimo_pago = timezone.now()
        suscripcion.proximo_pago = timezone.now() + suscripcion.periodo
        suscripcion.fecha_vencimiento = suscripcion.proximo_pago
        suscripcion.activo = True

        # FIX_REACTIVAR_SUSCRIPCION_V1: reactivar banco + comerciales desactivados
        ids_reactivar = list(suscripcion.usuarios_desactivados or [])
        if ids_reactivar:
            from django.contrib.auth.models import User as _User
            from .models import Rol as _Rol
            _User.objects.filter(id__in=ids_reactivar).update(is_active=True)
            _Rol.objects.filter(
                usuario_id__in=ids_reactivar,
                tipo__in=['banco', 'comercial']
            ).update(activo=True)
            suscripcion.usuarios_desactivados = []
            messages.info(
                request,
                f"✅ {len(ids_reactivar)} usuario(s) reactivado(s)."
            )

        suscripcion.save()
        crear_notificacion(
            usuario=suscripcion.banco, tipo='suscripcion',
            mensaje=f"✅ Tu pago de ${monto} ha sido registrado. Próximo vencimiento: {suscripcion.proximo_pago.strftime('%d/%m/%Y')}",
            datos={'monto': float(monto), 'fecha_pago': timezone.now().isoformat(),
                   'proximo_pago': suscripcion.proximo_pago.isoformat(),
                   'url_detalle': '/roles/panel-suscripcion/'},
            prioridad='alta', categoria='financiera')
        messages.success(request, f"✅ Pago de ${monto} registrado para {suscripcion.banco.username}.")
        return redirect('roles:panel_bancos')
    context = {'suscripcion': suscripcion}
    return render(request, 'roles/registrar_pago_banco.html', context)


def es_auditor(user):
    """¿El usuario tiene rol de auditor activo?"""
    if not user or not user.is_authenticated:
        return False
    return Rol.objects.filter(usuario=user, tipo='auditor', activo=True).exists()


def get_banco_del_auditor(user):
    """Devuelve el banco al que está asignado el auditor."""
    if not user or not user.is_authenticated:
        return None
    rol = Rol.objects.filter(usuario=user, tipo='auditor', activo=True).first()
    return rol.banco_asignado if rol else None


def get_red_del_auditor(user):
    """
    Red completa del auditor:
    {banco, comerciales, clientes, todos_ids}
    """
    banco = get_banco_del_auditor(user)
    if not banco:
        return {'banco': None, 'comerciales': [], 'clientes': [], 'todos_ids': []}

    comerciales_ids = list(
        Subordinacion.objects.filter(jefe=banco, activo=True)
        .values_list('subordinado_id', flat=True)
    )

    clientes_por_fondo = list(
        Fondo.objects.filter(
            Q(asignado_por=banco) | Q(asignado_por__in=comerciales_ids),
            activo=True
        ).values_list('usuario_id', flat=True).distinct()
    )
    clientes_por_sub = list(
        Subordinacion.objects.filter(jefe__in=comerciales_ids, activo=True)
        .values_list('subordinado_id', flat=True)
    )
    clientes_ids = list(set(clientes_por_fondo + clientes_por_sub))

    return {
        'banco': banco,
        'comerciales': list(User.objects.filter(id__in=comerciales_ids)),
        'clientes': list(User.objects.filter(id__in=clientes_ids)),
        'todos_ids': list({banco.id, *comerciales_ids, *clientes_ids}),
    }

# FIX_FIFO_BONOS_V1: reintegro bonos ordenado por vencimiento

# FIX_POSTPAGO_V2: descuento postpago en premios y acreditación al gestor

# FIX_RECARGA_DIRECTA_POSTPAGO_V1: descuento de postpago en recarga directa

# FIX_REACTIVAR_SUSCRIPCION_V1: reactivar banco + comerciales al renovar


# ═══════════════════════════════════════════════════════════════
# HISTORIAL DE MOVIMIENTOS DE FONDO
# ═══════════════════════════════════════════════════════════════
@login_required
def historial_movimientos(request):
    user = request.user
    es_superadmin = user.is_superuser or user.roles.filter(tipo='superadmin', activo=True).exists()
    es_banco      = user.roles.filter(tipo='banco', activo=True).exists()
    es_comercial  = user.roles.filter(tipo='comercial', activo=True).exists()
    if not (es_superadmin or es_banco or es_comercial):
        messages.error(request, "Sin permisos.")
        return redirect('publico:home')
    qs = MovimientoFondo.objects.select_related('emisor', 'receptor', 'forma_pago')
    if es_superadmin:
        pass
    elif es_banco:
        comerciales_ids = list(Subordinacion.objects.filter(jefe=user, activo=True).values_list('subordinado_id', flat=True))
        clientes_ids = list(Fondo.objects.filter(Q(asignado_por__in=comerciales_ids) | Q(asignado_por=user), activo=True).values_list('usuario_id', flat=True).distinct())
        qs = qs.filter(Q(receptor_id__in=clientes_ids) | Q(emisor_id__in=clientes_ids))
    else:
        clientes_ids = list(Fondo.objects.filter(asignado_por=user, activo=True).values_list('usuario_id', flat=True).distinct())
        qs = qs.filter(Q(receptor_id__in=clientes_ids) | Q(emisor_id__in=clientes_ids))
    cliente_id = (request.GET.get('cliente') or '').strip()
    if cliente_id.isdigit():
        qs = qs.filter(Q(receptor_id=cliente_id) | Q(emisor_id=cliente_id))
    comercial_id = (request.GET.get('comercial') or '').strip()
    if comercial_id.isdigit() and (es_superadmin or es_banco):
        qs = qs.filter(emisor_id=comercial_id)
    tipo = (request.GET.get('tipo') or '').strip()
    if tipo:
        qs = qs.filter(tipo=tipo)
    fp_id = (request.GET.get('forma_pago') or '').strip()
    if fp_id.isdigit():
        qs = qs.filter(forma_pago_id=fp_id)
    fd = (request.GET.get('fecha_desde') or '').strip()
    fh = (request.GET.get('fecha_hasta') or '').strip()
    # FIX_DEFAULT_HOY_OK_V1: default hoy si no hay filtros de fecha
    if not fd and not fh:
        from django.utils import timezone as _tz_hoy
        fd = _tz_hoy.localdate().strftime('%Y-%m-%d')
        fh = _tz_hoy.localdate().strftime('%Y-%m-%d')
    if fd:
        qs = qs.filter(creado_en__date__gte=fd)
    if fh:
        qs = qs.filter(creado_en__date__lte=fh)
    q = (request.GET.get('q') or '').strip()
    if q:
        qs = qs.filter(Q(motivo__icontains=q) | Q(nota__icontains=q))
    agg = qs.aggregate(
        creditos=Sum(Case(
            When(monto__gt=0, then='monto'),
            default=Decimal('0.00'),
            output_field=DecimalField(max_digits=12, decimal_places=2)
        )),
        debitos=Sum(Case(
            When(monto__lt=0, then='monto'),
            default=Decimal('0.00'),
            output_field=DecimalField(max_digits=12, decimal_places=2)
        ))
    )
    total_creditos = agg['creditos'] or Decimal('0.00')
    total_debitos  = agg['debitos']  or Decimal('0.00')
    qs = qs.order_by('-creado_en')
    paginator = Paginator(qs, 30)
    page_obj = paginator.get_page(request.GET.get('page'))

    # _enriquecer_hist: refs + agrupación por día
    from roles.utils import resolver_referencia_movimiento, agrupar_movimientos_por_dia
    for _m in page_obj:
        _m.ref_label, _m.ref_url = resolver_referencia_movimiento(_m)
    grupos_dia = agrupar_movimientos_por_dia(list(page_obj))
    if es_superadmin:
        clientes_sel = User.objects.filter(
            roles__tipo='cliente', roles__activo=True, is_active=True
        ).exclude(
            roles__tipo__in=['comercial', 'banco', 'superadmin'],
            roles__activo=True
        ).distinct().order_by('username')
        comerciales_sel = User.objects.filter(
            roles__tipo='comercial', roles__activo=True, is_active=True
        ).exclude(
            roles__tipo='banco', roles__activo=True
        ).distinct().order_by('username')
    elif es_banco:
        clientes_sel = User.objects.filter(
            id__in=clientes_ids, is_active=True,
            roles__tipo='cliente', roles__activo=True,
        ).exclude(
            roles__tipo__in=['comercial', 'banco', 'superadmin'],
            roles__activo=True
        ).distinct().order_by('username')
        comerciales_sel = User.objects.filter(
            id__in=comerciales_ids, is_active=True,
            roles__tipo='comercial', roles__activo=True,
        ).exclude(
            roles__tipo='banco', roles__activo=True
        ).distinct().order_by('username')
    else:
        clientes_sel = User.objects.filter(
            id__in=clientes_ids, is_active=True,
            roles__tipo='cliente', roles__activo=True,
        ).exclude(
            roles__tipo__in=['comercial', 'banco', 'superadmin'],
            roles__activo=True
        ).distinct().order_by('username')
        comerciales_sel = User.objects.none()
    # ═══════════════════════════════════════════════════════════
    # EXPORT_CSV — exportar el queryset completo a CSV
    # ═══════════════════════════════════════════════════════════
    if request.GET.get('export') == 'csv':
        import csv
        from django.http import HttpResponse
        resp = HttpResponse(content_type='text/csv; charset=utf-8-sig')
        resp['Content-Disposition'] = 'attachment; filename="historial_movimientos.csv"'
        w = csv.writer(resp)
        w.writerow([
            'Fecha', 'Hora', 'Tipo', 'Emisor', 'Receptor', 'Monto',
            'Forma de pago', 'Motivo', 'Nota', 'Referencia',
            'Saldo antes', 'Saldo después',
        ])
        for m in qs.order_by('-creado_en').iterator():
            ref_label, _ = resolver_referencia_movimiento(m)
            w.writerow([
                timezone.localtime(m.creado_en).strftime('%Y-%m-%d'),
                timezone.localtime(m.creado_en).strftime('%H:%M'),
                (m.get_tipo_display() if hasattr(m, 'get_tipo_display') else m.tipo),
                m.emisor.username if m.emisor else '',
                m.receptor.username if m.receptor else '',
                str(m.monto),
                m.forma_pago.nombre if m.forma_pago else '',
                m.motivo or '',
                m.nota or '',
                ref_label or '',
                str(m.saldo_antes) if m.saldo_antes is not None else '',
                str(m.saldo_despues) if m.saldo_despues is not None else '',
            ])
        return resp

    return render(request, 'roles/historial_movimientos.html', {
        'grupos_dia': grupos_dia,
        'page_obj': page_obj,
        'total_creditos': total_creditos, 'total_debitos': total_debitos,
        'neto': total_creditos + total_debitos,
        'clientes_sel': clientes_sel, 'comerciales_sel': comerciales_sel,
        'formas_pago': FormaPago.objects.filter(activo=True).order_by('nombre'),
        'tipos': MovimientoFondo.TIPOS,
        'es_superadmin': es_superadmin, 'es_banco': es_banco, 'es_comercial': es_comercial,
        'filtros': {'cliente': cliente_id, 'comercial': comercial_id,
                    'tipo': tipo, 'forma_pago': fp_id,
                    'fecha_desde': fd, 'fecha_hasta': fh, 'q': q},
    })


# ═══════════════════════════════════════════════════════════════
# REALTIME_ONLINE_V1 · Endpoints para polling
# ═══════════════════════════════════════════════════════════════
@login_required
def api_saldos_clientes(request):
    """Devuelve saldo + online de un set de IDs. Query: ?ids[]=1&ids[]=2"""
    from django.db.models import Sum
    from roles.utils import get_online_ids

    ids = request.GET.getlist("ids[]") or request.GET.getlist("ids")
    if not ids:
        return JsonResponse({"success": False, "error": "Faltan ids"}, status=400)

    try:
        ids = [int(i) for i in ids][:200]
    except (ValueError, TypeError):
        return JsonResponse({"success": False, "error": "IDs inválidos"}, status=400)

    user = request.user
    es_superadmin = user.is_superuser or user.roles.filter(tipo="superadmin", activo=True).exists()
    if not es_superadmin:
        permitidos = set(Fondo.objects.filter(
            asignado_por=user, activo=True
        ).values_list("usuario_id", flat=True))
        ids = [i for i in ids if i in permitidos]

    saldos = Fondo.objects.filter(
        usuario_id__in=ids, activo=True
    ).values("usuario_id").annotate(total=Sum("monto"))
    saldo_map = {r["usuario_id"]: float(r["total"] or 0) for r in saldos}

    online = get_online_ids(ids)

    clientes = []
    for u in User.objects.filter(id__in=ids).only("id", "username"):
        clientes.append({
            "id": u.id,
            "username": u.username,
            "saldo": saldo_map.get(u.id, 0.0),
            "online": u.id in online,
        })

    return JsonResponse({
        "success": True,
        "clientes": clientes,
        "server_ts": timezone.now().isoformat(),
    })


@login_required
def api_saldo_cliente(request, cliente_id):
    """Devuelve saldo total + desglose por FP + online de UN cliente."""
    from django.db.models import Sum
    from roles.utils import esta_online

    cliente = get_object_or_404(User, id=cliente_id)
    saldo_total = Fondo.objects.filter(
        usuario=cliente, activo=True
    ).aggregate(t=Sum("monto"))["t"] or 0

    fondos_por_fp = {}
    for f in Fondo.objects.filter(usuario=cliente, activo=True).select_related("forma_pago"):
        fp = f.forma_pago.nombre if f.forma_pago else "Sin FP"
        fondos_por_fp[fp] = float(f.monto or 0)

    return JsonResponse({
        "success": True,
        "cliente_id": cliente.id,
        "username": cliente.username,
        "saldo_total": float(saldo_total),
        "fondos_por_fp": fondos_por_fp,
        "online": esta_online(cliente),
        "server_ts": timezone.now().isoformat(),
    })


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
            fila['limite'] = float(get_pool_gestor(gestor, sorteo, fj, forma_pago) or 0)
        except Exception:
            pass
        # Consumido del gestor para esa forma en (sorteo, fecha, FP)
        try:
            from jugadas.models import Jugada as _J
            from django.db.models import Sum as _Sum
            _q = _J.objects.filter(
                destinatario=gestor, sorteo=sorteo, forma_juego=fj,
                fecha_sorteo=fecha, estado__in=['confirmada', 'pendiente'],
            )
            if forma_pago:
                _q = _q.filter(forma_pago=forma_pago)
            fila['consumido'] = float(_q.aggregate(t=_Sum('monto'))['t'] or 0)
        except Exception:
            fila['consumido'] = 0.0
        fila['disponible'] = max(0.0, fila['limite'] - fila['consumido'])
        resultado_formas.append(fila)

    return JsonResponse({
        'success': True,
        'gestor': gestor.username,
        'sorteo': sorteo.nombre,
        'formas': resultado_formas,
    })



# ═══════════════════════════════════════════════════════════════
# API · Gestores y sorteos disponibles para consultar limites
# ═══════════════════════════════════════════════════════════════
@login_required
def api_gestores_disponibles(request):
    """Devuelve gestores que el usuario puede consultar + sorteos activos."""
    user = request.user
    es_superadmin = user.is_superuser or user.roles.filter(tipo='superadmin', activo=True).exists()
    es_banco = user.roles.filter(tipo='banco', activo=True).exists()
    es_comercial = user.roles.filter(tipo='comercial', activo=True).exists()

    if not (es_superadmin or es_banco or es_comercial):
        return JsonResponse({'success': False, 'error': 'Sin permisos'}, status=403)

    gestores = []
    if es_superadmin:
        # Todos los bancos + comerciales + él mismo
        gestores.append({'id': user.id, 'nombre': user.username + ' (yo)', 'tipo': 'superadmin'})
        for u in User.objects.filter(roles__tipo='banco', roles__activo=True, is_active=True).distinct():
            if u.id != user.id:
                gestores.append({'id': u.id, 'nombre': u.username, 'tipo': 'banco'})
        for u in User.objects.filter(roles__tipo='comercial', roles__activo=True, is_active=True).distinct():
            if u.id != user.id:
                gestores.append({'id': u.id, 'nombre': u.username, 'tipo': 'comercial'})
    elif es_banco:
        gestores.append({'id': user.id, 'nombre': user.username + ' (yo)', 'tipo': 'banco'})
        comerciales_ids = Subordinacion.objects.filter(jefe=user, activo=True).values_list('subordinado_id', flat=True)
        for u in User.objects.filter(id__in=comerciales_ids, is_active=True).order_by('username'):
            gestores.append({'id': u.id, 'nombre': u.username, 'tipo': 'comercial'})
    else:
        # Comercial: solo él mismo
        gestores.append({'id': user.id, 'nombre': user.username + ' (yo)', 'tipo': 'comercial'})

    # Sorteos activos
    sorteos = []
    for s in Sorteo.objects.filter(activo=True).order_by('nombre'):
        sorteos.append({'id': s.id, 'nombre': s.nombre})

    return JsonResponse({
        'success': True,
        'gestores': gestores,
        'sorteos': sorteos,
    })



# ═══════════════════════════════════════════════════════════════
# API · Clientes del gestor con sus formas de pago (para retiro rápido)
# ═══════════════════════════════════════════════════════════════
@login_required
def api_clientes_gestor(request):
    """Devuelve clientes del gestor con sus FPs y saldo."""
    from django.db.models import Sum as _Sum

    user = request.user
    es_superadmin = user.is_superuser or user.roles.filter(tipo='superadmin', activo=True).exists()
    es_banco = user.roles.filter(tipo='banco', activo=True).exists()
    es_comercial = user.roles.filter(tipo='comercial', activo=True).exists()

    if not (es_superadmin or es_banco or es_comercial):
        return JsonResponse({'success': False, 'error': 'Sin permisos'}, status=403)

    # Clientes: los que tienen fondo asignado por el user (o por sus comerciales si es banco)
    if es_superadmin:
        qs_fondos = Fondo.objects.filter(activo=True)
    elif es_banco:
        comerciales_ids = list(Subordinacion.objects.filter(jefe=user, activo=True).values_list('subordinado_id', flat=True))
        qs_fondos = Fondo.objects.filter(
            Q(asignado_por=user) | Q(asignado_por__in=comerciales_ids),
            activo=True
        )
    else:
        qs_fondos = Fondo.objects.filter(asignado_por=user, activo=True)

    # Agrupar por cliente
    clientes_map = {}
    for f in qs_fondos.select_related('usuario', 'forma_pago').order_by('usuario__username'):
        if not f.forma_pago:
            continue
        cid = f.usuario_id
        if cid not in clientes_map:
            clientes_map[cid] = {
                'id': cid,
                'nombre': f.usuario.username,
                'fps': []
            }
        clientes_map[cid]['fps'].append({
            'id': f.forma_pago_id,
            'nombre': f.forma_pago.nombre,
            'saldo': float(f.monto or 0),
        })

    clientes = list(clientes_map.values())

    return JsonResponse({
        'success': True,
        'clientes': clientes,
    })



@login_required
def api_pool_gestor(request):
    """Devuelve pool por forma de juego para (gestor + sorteo + forma_pago)."""
    from roles.utils import get_pool_gestor
    from jugadas.models import FormaJuego

    gestor_id = (request.GET.get('gestor_id') or '').strip()
    sorteo_id = (request.GET.get('sorteo_id') or '').strip()
    forma_pago_id = (request.GET.get('forma_pago_id') or '').strip()

    if not (gestor_id.isdigit() and sorteo_id.isdigit()):
        return JsonResponse({'success': False, 'error': 'Faltan parametros'}, status=400)

    try:
        gestor = User.objects.get(id=int(gestor_id))
        sorteo = Sorteo.objects.get(id=int(sorteo_id))
    except (User.DoesNotExist, Sorteo.DoesNotExist):
        return JsonResponse({'success': False, 'error': 'No encontrado'}, status=404)

    forma_pago = None
    if forma_pago_id.isdigit():
        try:
            forma_pago = FormaPago.objects.get(id=int(forma_pago_id))
        except FormaPago.DoesNotExist:
            pass

    pools = {}
    for fj in FormaJuego.objects.filter(activo=True):
        try:
            val = get_pool_gestor(gestor, sorteo, fj, forma_pago)
            pools[fj.nombre.lower()] = float(val or 0)
        except Exception:
            pools[fj.nombre.lower()] = 0

    return JsonResponse({'success': True, 'pools': pools})


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
