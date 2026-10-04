# FIX_PRESTAMO_V1: context para el link de préstamos en sidebar
def prestamos_context(request):
    from roles.utils import _es_cliente_frecuente
    from jugadas.models import Boleta
    from django.utils import timezone
    from datetime import timedelta

    default = {'mostrar_link_prestamos': False, 'perfil_prestamo_badge_visto': True}

    try:
        if not request.user.is_authenticated:
            return default
        if not request.user.roles.filter(tipo='cliente', activo=True).exists():
            return default

        corte = timezone.now() - timedelta(days=7)
        gestores_ids = Boleta.objects.filter(
            usuario=request.user, estado='activa', creado_en__gte=corte,
        ).values_list('destinatario_id', flat=True).distinct()

        mostrar = False
        from django.contrib.auth.models import User as _U
        for gid in gestores_ids:
            g = _U.objects.filter(id=gid).first()
            if g and _es_cliente_frecuente(request.user, g):
                mostrar = True
                break

        perfil = getattr(request.user, 'perfil', None)
        return {
            'mostrar_link_prestamos': mostrar,
            'perfil_prestamo_badge_visto': getattr(perfil, 'prestamo_badge_visto', True) if perfil else True,
        }
    except Exception:
        return default

