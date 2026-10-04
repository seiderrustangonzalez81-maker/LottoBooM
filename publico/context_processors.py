from django.core.cache import cache
from django.utils import timezone
from django.db.models import Count, Q
from .models import VisitaDiaria


def contadores(request):
    hoy = timezone.now().date()
    cache_key = f'contadores_{hoy}'
    datos = cache.get(cache_key)

    if datos is None:
        # Visitas de hoy
        total_hoy = VisitaDiaria.objects.filter(fecha=hoy).count()
        # Totales historicos
        total_general = VisitaDiaria.objects.count()
        # Anonimos hoy (usuarios sin autenticar)
        anonimos_hoy = VisitaDiaria.objects.filter(fecha=hoy, usuario__isnull=True).count()
        # Usuarios registrados hoy
        registrados_hoy = VisitaDiaria.objects.filter(fecha=hoy, usuario__isnull=False).count()

        datos = {
            'total_hoy': total_hoy,
            'total_general': total_general,
            'anonimos_hoy': anonimos_hoy,
            'registrados_hoy': registrados_hoy,
        }
        cache.set(cache_key, datos, 60)  # cache de 1 minuto

    return datos