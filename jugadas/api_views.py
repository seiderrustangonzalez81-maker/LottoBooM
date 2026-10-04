from django.http import JsonResponse
from django.contrib.auth.models import User
from django.db import models
from roles.models import Rol, Fondo
from sorteos.models import Sorteo
from .models import Jugada
from django.contrib.auth.decorators import login_required


@login_required
def api_usuarios_fondo(request):
    """API para obtener usuarios con fondos (para comerciales/banco)"""
    query = request.GET.get('q', '')
    usuarios = User.objects.filter(
        models.Q(username__icontains=query) |
        models.Q(email__icontains=query)
    ).exclude(id=request.user.id)[:10]

    data = []
    for user in usuarios:
        fondos = Fondo.objects.filter(usuario=user, activo=True)
        saldo = sum(f.monto for f in fondos)
        data.append({
            'id': user.id,
            'username': user.username,
            'saldo': float(saldo)
        })

    return JsonResponse(data, safe=False)


@login_required
def api_saldo_usuario(request, usuario_id):
    """API para obtener saldo de un usuario"""
    try:
        user = User.objects.get(id=usuario_id)
        fondos = Fondo.objects.filter(usuario=user, activo=True)
        saldo = sum(f.monto for f in fondos)

        return JsonResponse({
            'success': True,
            'saldo': float(saldo)
        })
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Usuario no encontrado'})


@login_required
def api_sorteos_disponibles(request):
    try:
        fecha_str = request.GET.get('fecha')
        if fecha_str:
            fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        else:
            fecha = timezone.now().date()

        sorteos = []
        for s in get_sorteos_disponibles(fecha):
            hora_salida = obtener_hora_salida_sorteo(s, fecha)
            sorteos.append({
                'id': s.id,
                'nombre': s.nombre,
                'hora_salida': hora_salida.strftime('%H:%M') if hora_salida else '',
                'minutos_restantes': getattr(s, 'minutos_restantes', 0)
            })

        sorteos.sort(key=lambda x: x['hora_salida'])
        return JsonResponse(sorteos, safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def api_mis_apuestas(request):
    """API para obtener las apuestas del usuario"""
    jugadas = Jugada.objects.filter(usuario=request.user).values(
        'id', 'numero', 'monto', 'estado', 'fecha', 'sorteo__nombre', 'forma_juego__nombre'
    ).order_by('-fecha')
    return JsonResponse(list(jugadas), safe=False)
