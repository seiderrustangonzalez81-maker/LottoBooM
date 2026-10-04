# pagos/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from .models import Pago, FormaPago
from .forms import CrearPagoForm, CambiarEstadoPagoForm
from roles.models import Rol, Subordinacion, Notificacion
from roles.utils import get_recursos_visibles  # ← NUEVO IMPORT


# ============================================================
# FUNCIÓN HELPER PARA NOTIFICACIONES ENRIQUECIDAS
# ============================================================

def crear_notificacion(usuario, tipo, mensaje, datos=None):
    """Crea una notificación con datos enriquecidos."""
    if not usuario:
        return
    Notificacion.objects.create(
        usuario=usuario,
        tipo=tipo,
        mensaje=mensaje,
        datos=datos or {},
        leido=False
    )


# ============================================================
# VISTAS
# ============================================================

@login_required
def mis_pagos(request):
    """Lista los pagos del usuario (los que él ha creado)"""
    pagos = Pago.objects.filter(usuario=request.user).order_by('-fecha')
    context = {'pagos': pagos}
    return render(request, 'pagos/mis_pagos.html', context)


@login_required
def crear(request):
    """
    Crear un nuevo pago.
    Las formas de pago disponibles se filtran según el rol del usuario
    usando get_recursos_visibles(tipo='forma_pago').
    """
    # Obtener las formas de pago que el usuario puede ver/usar
    formas_pago_visibles = get_recursos_visibles(request.user, 'forma_pago')

    if request.method == 'POST':
        form = CrearPagoForm(request.POST, usuario=request.user)
        # Asignar el queryset filtrado al campo 'forma_pago'
        form.fields['forma_pago'].queryset = formas_pago_visibles

        if form.is_valid():
            pago = form.save(commit=False)
            pago.fecha = timezone.now()
            pago.estado = 'pendiente'
            pago.save()

            # --- NOTIFICACIÓN ENRIQUECIDA ---
            datos_pago = {
                'pago_id': pago.id,
                'monto': float(pago.monto),
                'forma_pago': pago.forma_pago.nombre if pago.forma_pago else 'N/A',
                'estado': pago.estado,
                'fecha': pago.fecha.isoformat(),
                'descripcion': pago.descripcion if hasattr(pago, 'descripcion') else '',
                'url_detalle': f'/pagos/detalle/{pago.id}/',
                'rol': 'usuario'
            }

            crear_notificacion(
                usuario=request.user,
                tipo='pago',
                mensaje=f"💰 Has creado un pago de ${pago.monto} ({pago.estado}).",
                datos=datos_pago
            )

            # Si el pago tiene un destinatario (comercial/banco), notificar también
            if hasattr(pago, 'destinatario') and pago.destinatario and pago.destinatario != request.user:
                datos_pago['rol'] = 'destinatario'
                crear_notificacion(
                    usuario=pago.destinatario,
                    tipo='pago',
                    mensaje=f"📥 {request.user.username} ha creado un pago de ${pago.monto} para ti.",
                    datos=datos_pago
                )

            messages.success(request, "Pago creado exitosamente.")
            return redirect('pagos:detalle', pk=pago.pk)
    else:
        form = CrearPagoForm(usuario=request.user)
        # Asignar el queryset filtrado al campo 'forma_pago'
        form.fields['forma_pago'].queryset = formas_pago_visibles

    context = {
        'form': form,
        'formas_pago_visibles': formas_pago_visibles,  # opcional para debug
    }
    return render(request, 'pagos/crear.html', context)


@login_required
def detalle(request, pk):
    """Ver detalle de un pago"""
    pago = get_object_or_404(Pago, pk=pk)

    # Verificar permisos
    if pago.usuario != request.user and not request.user.is_superuser:
        es_comercial = request.user.roles.filter(tipo='comercial', activo=True).exists()
        if es_comercial:
            clientes_ids = Subordinacion.objects.filter(
                jefe=request.user,
                activo=True
            ).values_list('subordinado_id', flat=True)
            if pago.usuario.id not in clientes_ids:
                messages.error(request, "No tienes permiso para ver este pago.")
                return redirect('pagos:mis_pagos')
        else:
            messages.error(request, "No tienes permiso para ver este pago.")
            return redirect('pagos:mis_pagos')

    context = {'pago': pago}
    return render(request, 'pagos/detalle.html', context)


@login_required
def gestionar(request):
    """Gestionar pagos (para comerciales/banco/superadmin)"""
    es_comercial = request.user.roles.filter(tipo='comercial', activo=True).exists()
    es_banco = request.user.roles.filter(tipo='banco', activo=True).exists()
    es_superadmin = request.user.is_superuser or request.user.roles.filter(tipo='superadmin', activo=True).exists()

    if not (es_comercial or es_banco or es_superadmin):
        messages.error(request, "No tienes permiso para gestionar pagos.")
        return redirect('pagos:mis_pagos')

    # Obtener pagos según rol
    if es_superadmin:
        pagos = Pago.objects.all().select_related('usuario').order_by('-fecha')
    elif es_banco:
        subordinados_ids = Subordinacion.objects.filter(
            jefe=request.user,
            activo=True
        ).values_list('subordinado_id', flat=True)
        pagos = Pago.objects.filter(
            models.Q(usuario__in=subordinados_ids) | models.Q(usuario=request.user)
        ).select_related('usuario').order_by('-fecha')
    else:  # comercial
        clientes_ids = Subordinacion.objects.filter(
            jefe=request.user,
            activo=True
        ).values_list('subordinado_id', flat=True)
        pagos = Pago.objects.filter(
            models.Q(usuario__in=clientes_ids) | models.Q(usuario=request.user)
        ).select_related('usuario').order_by('-fecha')

    context = {
        'pagos': pagos,
        'es_comercial': es_comercial,
        'es_banco': es_banco,
        'es_superadmin': es_superadmin,
    }
    return render(request, 'pagos/gestionar.html', context)


@login_required
def cambiar_estado(request, pk):
    """Cambiar estado de un pago"""
    pago = get_object_or_404(Pago, pk=pk)

    es_comercial = request.user.roles.filter(tipo='comercial', activo=True).exists()
    es_banco = request.user.roles.filter(tipo='banco', activo=True).exists()
    es_superadmin = request.user.is_superuser or request.user.roles.filter(tipo='superadmin', activo=True).exists()

    if not (es_comercial or es_banco or es_superadmin):
        messages.error(request, "No tienes permiso para cambiar el estado de este pago.")
        return redirect('pagos:mis_pagos')

    if request.method == 'POST':
        form = CambiarEstadoPagoForm(request.POST)
        if form.is_valid():
            nuevo_estado = form.cleaned_data['estado']
            nota = form.cleaned_data.get('nota', '')

            estado_anterior = pago.estado
            pago.estado = nuevo_estado
            if nota:
                pago.nota = nota
            pago.save()

            # --- NOTIFICACIONES ENRIQUECIDAS ---
            datos_pago = {
                'pago_id': pago.id,
                'monto': float(pago.monto),
                'forma_pago': pago.forma_pago.nombre if pago.forma_pago else 'N/A',
                'estado_anterior': estado_anterior,
                'nuevo_estado': nuevo_estado,
                'fecha': timezone.now().isoformat(),
                'modificado_por': request.user.username,
                'modificado_por_id': request.user.id,
                'nota': nota,
                'url_detalle': f'/pagos/detalle/{pago.id}/',
            }

            # Notificar al usuario del pago
            if pago.usuario != request.user:
                crear_notificacion(
                    usuario=pago.usuario,
                    tipo='pago',
                    mensaje=f"📊 El estado de tu pago de ${pago.monto} ha cambiado de {estado_anterior} a {nuevo_estado}.",
                    datos={**datos_pago, 'rol': 'usuario_pago'}
                )

            # Notificar al gestor que realizó el cambio (si es diferente)
            if request.user != pago.usuario:
                crear_notificacion(
                    usuario=request.user,
                    tipo='pago',
                    mensaje=f"✅ Has cambiado el estado del pago de {pago.usuario.username} de {estado_anterior} a {nuevo_estado}.",
                    datos={**datos_pago, 'rol': 'gestor'}
                )

            # Notificar a superadmins (si no es superadmin)
            if not es_superadmin:
                superadmins = User.objects.filter(roles__tipo='superadmin', roles__activo=True)
                for admin in superadmins:
                    if admin != request.user and admin != pago.usuario:
                        crear_notificacion(
                            admin,
                            'pago',
                            f"📊 Pago de ${pago.monto} de {pago.usuario.username} cambiado de {estado_anterior} a {nuevo_estado} por {request.user.username}.",
                            datos={**datos_pago, 'rol': 'superadmin'}
                        )

            messages.success(request, f"Estado del pago actualizado a {nuevo_estado}.")
            return redirect('pagos:detalle', pk=pago.pk)
    else:
        form = CambiarEstadoPagoForm(initial={'estado': pago.estado})

    context = {
        'form': form,
        'pago': pago,
    }
    return render(request, 'pagos/cambiar_estado.html', context)