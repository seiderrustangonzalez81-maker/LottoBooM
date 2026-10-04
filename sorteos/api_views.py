from django.http import JsonResponse
from django.utils import timezone
from sorteos.models import Sorteo
from .utils import calcular_estado_sorteo

def api_sorteos_data(request):
    hoy = timezone.now().date()
    ahora = timezone.now()
    # Obtener todos los sorteos activos (sin filtrar por fecha de creación)
    sorteos = Sorteo.objects.filter(activo=True)

    data = {'sorteos': []}
    for s in sorteos:
        # Calcular estado y segundos restantes
        s = calcular_estado_sorteo(s, ahora, hoy)

        data['sorteos'].append({
            'id': s.id,
            'estado': s.estado_actual,          # 'abierto', 'cerrado', 'salido'
            'segundos_restantes': s.segundos_restantes,  # número de segundos
        })
    return JsonResponse(data)