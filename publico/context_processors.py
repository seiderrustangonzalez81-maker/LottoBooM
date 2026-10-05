from django.core.cache import cache
from django.utils import timezone
from .models import VisitaDiaria


def contadores(request):
    """FIX_CONTADORES_V1: contadores de visitas globales."""
    # FIX_TZ_CONTADORES_V1: fecha local (Cuba)
    hoy = timezone.localdate()
    cache_key = f'contadores_{hoy}'
    datos = cache.get(cache_key)

    if datos is None:
        datos = {
            'total_hoy': VisitaDiaria.objects.filter(fecha=hoy).count(),
            'total_general': VisitaDiaria.objects.count(),
            'anonimos_hoy': VisitaDiaria.objects.filter(fecha=hoy, usuario__isnull=True).count(),
            'registrados_hoy': VisitaDiaria.objects.filter(fecha=hoy, usuario__isnull=False).count(),
        }
        cache.set(cache_key, datos, 60)

    return datos
