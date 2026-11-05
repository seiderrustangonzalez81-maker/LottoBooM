# -*- coding: utf-8 -*-
"""Landing pública v2 — datos reales, autocontenida."""
import re
from datetime import datetime, timedelta
from django.db.models import Sum
from django.shortcuts import render
from django.utils import timezone


def _numeros_bolas(r):
    """Convierte numero_ganador (o fallback) en lista de strings para las bolas."""
    if not r:
        return []
    for campo in ('numero_ganador', 'pick3', 'pick2', 'fijo'):
        val = (getattr(r, campo, '') or '').strip()
        if not val:
            continue
        # Separadores explícitos: "12 34 56", "12-34-56", "12,34,56"
        partes = [p for p in re.split(r'[\s,\-]+', val) if p]
        if len(partes) > 1:
            return partes
        # Número único → dígito a dígito
        return list(val)
    return []


def _ultimos_resultados(limit=15):
    from resultados.models import Resultado
    qs = Resultado.objects.order_by('-fecha', '-hora')[:limit]
    try:
        qs = qs.select_related('sorteo')
    except Exception:
        pass
    rs = list(qs)
    for r in rs:
        r.numeros_lista = _numeros_bolas(r)
    return rs


def _proximos_sorteos(limit=6):
    from sorteos.models import Sorteo
    hoy = timezone.localdate()
    lista = []
    try:
        from sorteos.utils import get_sorteos_hoy
        sorteos, _ = get_sorteos_hoy(hoy)
        abiertos = [s for s in sorteos if getattr(s, 'estado_actual', None) == 'abierto']
        lista = abiertos or sorteos
    except Exception:
        lista = list(Sorteo.objects.filter(activo=True).order_by('-creado_en')[:limit])

    # Enriquecer con datetime para countdown
    for s in lista:
        hs = getattr(s, 'hora_salida', None)
        s.proximo_dt = None
        if hs:
            try:
                naive = datetime.combine(hoy, hs)
                s.proximo_dt = timezone.make_aware(naive)
            except Exception:
                pass
    return lista[:limit]


def _stats():
    from jugadas.models import Jugada
    from sorteos.models import Sorteo
    from usuarios.models import User
    hoy = timezone.localdate()
    hace_7d = timezone.now() - timedelta(days=7)
    premios = (
        Jugada.objects
        .filter(monto_premio__gt=0, fecha__gte=hace_7d)
        .aggregate(t=Sum('monto_premio'))
    )['t'] or 0
    return {
        'apostadores': User.objects.filter(is_active=True).count(),
        'jugadas_hoy': Jugada.objects.filter(fecha__date=hoy).count(),
        'sorteos_activos': Sorteo.objects.filter(activo=True).count(),
        'premios_pagados': int(premios),
    }


def _top_ganadores(limit=10):
    from jugadas.models import Jugada
    hace_7d = timezone.now() - timedelta(days=7)
    try:
        qs = (Jugada.objects
              .filter(monto_premio__gt=0, fecha__gte=hace_7d)
              .select_related('usuario', 'sorteo')
              .order_by('-monto_premio')[:limit])
        return list(qs)
    except Exception:
        return []


def landing(request):
    ultimos = _ultimos_resultados()
    return render(request, 'publico/landing.html', {
        'ultimos_resultados': ultimos,
        'ultimo_resultado': ultimos[0] if ultimos else None,
        'proximos_sorteos': _proximos_sorteos(),
        'stats': _stats(),
        'top_ganadores': _top_ganadores(),
    })
