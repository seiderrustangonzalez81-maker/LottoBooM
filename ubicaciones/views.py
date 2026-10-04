# ubicaciones/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import UbicacionUsuario
from .forms import UbicacionForm, BuscarUbicacionForm


@login_required
def mis_ubicaciones(request):
    """Lista las ubicaciones del usuario"""
    ubicaciones = UbicacionUsuario.objects.filter(
        usuario=request.user,
        activo=True
    ).order_by('-fecha_registro')

    context = {
        'ubicaciones': ubicaciones,
    }
    return render(request, 'ubicaciones/mis_ubicaciones.html', context)


@login_required
def registrar_ubicacion(request):
    """Registra una nueva ubicación"""
    if request.method == 'POST':
        form = UbicacionForm(request.POST)
        if form.is_valid():
            ubicacion = form.save(commit=False)
            ubicacion.usuario = request.user
            ubicacion.save()
            messages.success(request, "Ubicación registrada exitosamente")
            return redirect('ubicaciones:mis_ubicaciones')
    else:
        form = UbicacionForm()

    context = {
        'form': form,
    }
    return render(request, 'ubicaciones/registrar.html', context)


@login_required
def editar_ubicacion(request, ubicacion_id):
    """Edita una ubicación existente"""
    ubicacion = get_object_or_404(UbicacionUsuario, id=ubicacion_id, usuario=request.user)

    if request.method == 'POST':
        form = UbicacionForm(request.POST, instance=ubicacion)
        if form.is_valid():
            form.save()
            messages.success(request, "Ubicación actualizada exitosamente")
            return redirect('ubicaciones:mis_ubicaciones')
    else:
        form = UbicacionForm(instance=ubicacion)

    context = {
        'form': form,
        'ubicacion': ubicacion,
    }
    return render(request, 'ubicaciones/editar.html', context)


@login_required
def eliminar_ubicacion(request, ubicacion_id):
    """Elimina (desactiva) una ubicación"""
    ubicacion = get_object_or_404(UbicacionUsuario, id=ubicacion_id, usuario=request.user)
    ubicacion.activo = False
    ubicacion.save()
    messages.success(request, "Ubicación eliminada exitosamente")
    return redirect('ubicaciones:mis_ubicaciones')


@login_required
def buscar_ubicaciones(request, telefono=None):
    """Busca ubicaciones por teléfono (para comerciales/banco)"""
    user = request.user

    # Verificar roles correctamente
    es_comercial = user.roles.filter(tipo="comercial", activo=True).exists()
    es_banco = user.roles.filter(tipo="banco", activo=True).exists()
    es_superadmin = user.is_superuser or user.roles.filter(tipo="superadmin", activo=True).exists()

    if not (es_comercial or es_banco or es_superadmin):
        messages.error(request, "No tienes permisos para buscar ubicaciones")
        return redirect('publico:home')

    # Buscar por teléfono específico
    if telefono:
        ubicaciones = UbicacionUsuario.objects.filter(
            telefono__icontains=telefono,
            activo=True
        ).select_related('usuario')
        form = None
    else:
        # Búsqueda con filtros
        form = BuscarUbicacionForm(request.GET)
        ubicaciones = UbicacionUsuario.objects.filter(activo=True).select_related('usuario')

        if form.is_valid():
            ubicaciones = form.filter_queryset(ubicaciones)

    context = {
        'ubicaciones': ubicaciones,
        'form': form,
        'telefono': telefono,
    }
    return render(request, 'ubicaciones/buscar.html', context)