import logging
from decimal import Decimal

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.models import User

from roles.models import Fondo, MovimientoFondo, RecursoAsignado, Notificacion, Subordinacion
from pagos.models import FormaPago

logger = logging.getLogger(__name__)


# ============================================================
# DASHBOARD DEL BANCO
# ============================================================
@login_required
def dashboard_banco(request):
    context = {'titulo': 'Panel del Banco'}
    return render(request, 'banco/dashboard.html', context)


# ============================================================
# GESTIÓN DE COMERCIALES
# ============================================================
@login_required
def gestion_comerciales(request):
    context = {'titulo': 'Gestión de Comerciales'}
    return render(request, 'banco/gestion_comerciales.html', context)


# ============================================================
# GESTIÓN DE LÍMITES
# ============================================================
@login_required
def gestion_limites_banco(request):
    context = {'titulo': 'Gestión de Límites'}
    return render(request, 'banco/gestion_limites.html', context)


# ============================================================
# GESTIÓN DE DOSIS
# ============================================================
@login_required
def gestion_dosis_banco(request):
    context = {'titulo': 'Gestión de Dosis'}
    return render(request, 'banco/gestion_dosis.html', context)


# ============================================================
# REPORTE DE VENTAS
# ============================================================
@login_required
def reporte_ventas_banco(request):
    context = {'titulo': 'Reporte de Ventas'}
    return render(request, 'banco/reporte_ventas.html', context)


# ============================================================
# RESUMEN DE RENTABILIDAD
# ============================================================
@login_required
def resumen_rentabilidad(request):
    context = {'titulo': 'Resumen de Rentabilidad'}
    return render(request, 'banco/resumen_rentabilidad.html', context)


# ============================================================
# RESUMEN DE UN COMERCIAL ESPECÍFICO
# ============================================================
@login_required
def resumen_comercial(request, comercial_id):
    context = {
        'titulo': 'Resumen del Comercial',
        'comercial_id': comercial_id,
    }
    return render(request, 'banco/resumen_comercial.html', context)


# ============================================================
# COMPARTIR RESUMEN (VÍA TOKEN)
# ============================================================
def compartir_resumen(request, token):
    context = {
        'titulo': 'Resumen Compartido',
        'token': token,
    }
    return render(request, 'banco/compartir_resumen.html', context)


# ============================================================
# RECARGAR USUARIO (CORREGIDA)
# ============================================================
@login_required
def recargar_usuario(request):
    user = request.user

    es_superadmin = user.is_superuser or user.roles.filter(tipo='superadmin', activo=True).exists()
    es_banco = user.roles.filter(tipo='banco', activo=True).exists()
    es_comercial = user.roles.filter(tipo='comercial', activo=True).exists()

    if not (es_superadmin or es_banco or es_comercial):
        messages.error(request, "No tienes permisos para recargar usuarios.")
        return redirect('publico:home')

    # --- Formas de pago ---
    formas_pago = FormaPago.objects.none()
    if es_superadmin:
        formas_pago = FormaPago.objects.filter(activo=True)
    elif es_banco:
        recursos_fp = RecursoAsignado.objects.filter(banco=user, tipo='forma_pago', activo=True)
        formas_pago_ids = recursos_fp.values_list('forma_pago_id', flat=True)
        formas_pago = FormaPago.objects.filter(id__in=formas_pago_ids, activo=True)
        if not formas_pago.exists():
            formas_pago = FormaPago.objects.filter(activo=True)
    elif es_comercial:
        rol_comercial = user.roles.filter(tipo='comercial', activo=True).first()
        banco = rol_comercial.banco_asignado if rol_comercial and rol_comercial.banco_asignado else None
        if banco:
            recursos_fp = RecursoAsignado.objects.filter(banco=banco, tipo='forma_pago', activo=True)
            formas_pago_ids = recursos_fp.values_list('forma_pago_id', flat=True)
            formas_pago = FormaPago.objects.filter(id__in=formas_pago_ids, activo=True)
        else:
            formas_pago = FormaPago.objects.filter(activo=True)

    # --- Usuarios ---
    usuarios = User.objects.none()
    if es_superadmin:
        usuarios = User.objects.filter(is_active=True).exclude(id=user.id)
    elif es_banco:
        usuarios = User.objects.filter(is_active=True).exclude(id=user.id)
    elif es_comercial:
        usuarios = User.objects.filter(is_active=True).exclude(id=user.id)
        rol_comercial = user.roles.filter(tipo='comercial', activo=True).first()
        if rol_comercial and rol_comercial.banco_asignado:
            usuarios = usuarios.exclude(id=rol_comercial.banco_asignado.id)
        superadmins = User.objects.filter(roles__tipo='superadmin', roles__activo=True).values_list('id', flat=True)
        usuarios = usuarios.exclude(id__in=superadmins)

    # --- POST ---
    if request.method == 'POST':
        usuario_id = request.POST.get('usuario_id')
        forma_pago_id = request.POST.get('forma_pago_id')
        monto_str = request.POST.get('monto')

        if not usuario_id or not forma_pago_id or not monto_str:
            messages.error(request, "Todos los campos son obligatorios.")
            return redirect('banco:recargar_usuario')

        try:
            usuario = User.objects.get(id=usuario_id, is_active=True)
        except User.DoesNotExist:
            messages.error(request, "Usuario no válido.")
            return redirect('banco:recargar_usuario')

        if not usuarios.filter(id=usuario.id).exists():
            messages.error(request, "No tienes permisos para recargar a este usuario.")
            return redirect('banco:recargar_usuario')

        try:
            forma_pago = FormaPago.objects.get(id=forma_pago_id, activo=True)
        except FormaPago.DoesNotExist:
            messages.error(request, "Forma de pago no válida.")
            return redirect('banco:recargar_usuario')

        try:
            monto = Decimal(monto_str)
            if monto <= 0:
                raise ValueError("El monto debe ser mayor a 0")
        except (ValueError, TypeError) as e:
            messages.error(request, f"Monto inválido: {str(e)}")
            return redirect('banco:recargar_usuario')

        try:
            fondo, created = Fondo.objects.get_or_create(
                usuario=usuario,
                forma_pago=forma_pago,
                defaults={'monto': 0, 'activo': True, 'asignado_por': user}
            )
            fondo.monto += monto
            fondo.save()

            MovimientoFondo.objects.create(
                emisor=user,
                receptor=usuario,
                forma_pago=forma_pago,
                monto=monto,
                tipo='recarga',
                estado='confirmado',
                datos_transferencia={'recarga_por': user.username},
                nota=f"Recarga realizada por {user.username}"
            )

            Notificacion.objects.create(
                usuario=usuario,
                tipo='recarga',
                mensaje=f"💰 Has recibido una recarga de ${monto} en {forma_pago.nombre} de {user.username}.",
                datos={'monto': float(monto), 'forma_pago': forma_pago.nombre},
                prioridad='alta',
                categoria='financiera'
            )

            messages.success(request, f"✅ Recarga de ${monto} realizada a {usuario.username}.")
        except Exception as e:
            logger.error(f"Error al recargar: {e}")
            messages.error(request, "Ocurrió un error al procesar la recarga.")
            return redirect('banco:recargar_usuario')

        return redirect('banco:recargar_usuario')

    context = {
        'usuarios': usuarios,
        'formas_pago': formas_pago,
    }
    return render(request, 'banco/recargar_usuario.html', context)
