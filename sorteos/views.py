from LottoBooM.utils import es_verano_cuba
# -*- coding: utf-8 -*-
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo

from django.utils import timezone
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required  # FIX_IMPORT_LOGIN

from .models import Sorteo
from .forms import SorteoForm
from .utils import (segundos_hasta_proximo as _seg_hasta_prox, calcular_estado_sorteo, get_hora_salida, get_datetime_salida_cuba, obtener_hora_desde_horarios)
from jugadas.models import FormaJuego


CUBA_TZ = ZoneInfo('America/Havana')

DIAS_SEMANA_ES = {
    0: 'Lunes', 1: 'Martes', 2: 'Miércoles', 3: 'Jueves',
    4: 'Viernes', 5: 'Sábado', 6: 'Domingo',
}


def _temporada_actual(fecha):
    return 'Verano' if es_verano_cuba(fecha) else 'Invierno'

def _tz_cuba(fecha):
    """tzinfo con el offset correcto de Cuba (respeta es_verano_cuba)."""
    from LottoBooM.utils import es_verano_cuba
    from datetime import timezone as _dt_tz
    return _dt_tz(timedelta(hours=-4 if es_verano_cuba(fecha) else -5))

def _ahora_cuba():
    """datetime.now() con el offset correcto de Cuba."""
    from datetime import timezone as _dt_tz
    utc = datetime.now(_dt_tz.utc)
    return utc.astimezone(_tz_cuba(utc))



MAPEO_FJ = {
    'pick2': 'Pick 2', 'pick3': 'Pick 3', 'pick4': 'Pick 4', 'pick5': 'Pick 5',
    'fijo': 'Fijo', 'corrido1': 'Corrido 1', 'corrido2': 'Corrido 2',
    'pf': 'PF', 'vspf': 'VS PF', 'vspick2': 'VS Pick2', 'pick2vspf': 'Pick2 vs PF',
    'tripleta': 'Tripleta', 'posicion': 'Posición',
    'centena corrida1': 'Centena Corrida 1', 'centena corrida2': 'Centena Corrida 2',
    'superparlet': 'Superparlet', 'parlet': 'Parlet',
}


def _formas_de_sorteo(sorteo):
    fj_map = {fj.nombre.lower(): fj for fj in FormaJuego.objects.filter(activo=True)}
    resultado = []
    for clave in (sorteo.formas_juego or []):
        nombre = MAPEO_FJ.get(clave.lower(), clave).lower()
        fj = fj_map.get(nombre) or fj_map.get(clave.lower())
        if fj and fj not in resultado:
            resultado.append(fj)
    return resultado


def _hora_salida_hoy(sorteo, hoy):
    """Hora de salida ya normalizada a Cuba desde el calendario maestro."""
    return get_hora_salida(sorteo, hoy)


def _calcular_estado(sorteo, hora_salida, ahora, fecha_operativa=None):
    """Devuelve el contrato histórico como diccionario, con cálculo horario único."""
    if fecha_operativa is None:
        fecha_operativa = (ahora - timedelta(hours=1)).date()
    estado = calcular_estado_sorteo(sorteo, ahora, fecha_operativa)
    return {
        'estado': estado.estado_actual,
        'segundos_restantes': getattr(estado, 'segundos_restantes', 0) or 0,
        'hora_cierre': getattr(estado, 'hora_cierre', None),
        'hora_salida': getattr(estado, 'hora_salida', None),
        'hora_salida_str': getattr(estado, 'hora_salida_str', '—'),
        'hora_cierre_str': getattr(estado, 'hora_cierre_str', '—'),
        'segundos_proximo': getattr(estado, 'segundos_proximo', None),
    }


def lista_sorteos(request):
    ahora = _ahora_cuba()
    hoy = (ahora - timedelta(hours=1)).date()

    abiertos, cerrados, salidos = [], [], []

    for s in Sorteo.objects.filter(activo=True):
        hora_salida = _hora_salida_hoy(s, hoy)
        if not hora_salida:
            continue

        info = _calcular_estado(s, hora_salida, ahora, hoy)
        if info['estado'] == 'no_programado':
            continue

        s.estado_actual = info['estado']
        s.segundos_restantes = info['segundos_restantes']
        s.hora_salida = info['hora_salida']
        s.hora_salida_str = info['hora_salida_str']
        s.hora_cierre = info['hora_cierre']
        s.hora_cierre_str = info['hora_cierre_str']
        s.segundos_proximo = info['segundos_proximo']
        s.formas_filtradas = _formas_de_sorteo(s)

        if info['estado'] == 'abierto':
            abiertos.append(s)
        elif info['estado'] == 'cerrado':
            cerrados.append(s)
        else:
            salidos.append(s)

    abiertos.sort(key=lambda x: x.segundos_restantes)
    cerrados.sort(key=lambda x: x.segundos_restantes)
    salidos.sort(key=lambda x: x.hora_salida or time(0, 0))

    sorteos_ordenados = abiertos + cerrados + salidos

    temporada_actual = _temporada_actual(hoy)
    proxima_temporada = 'Invierno' if temporada_actual == 'Verano' else 'Verano'

    context = {
        'sorteos': sorteos_ordenados,
        'total_sorteos': len(sorteos_ordenados),
        'total_abiertos': len(abiertos),
        'total_cerrados': len(cerrados),
        'total_salidos': len(salidos),
        'temporada_actual': temporada_actual,
        'proxima_temporada': proxima_temporada,
        'dias_restantes_cambio': 0,
        'dia_semana_actual': DIAS_SEMANA_ES[hoy.weekday()],
    }
    return render(request, 'sorteos/sorteos.html', context)


def detalle_sorteo(request, sorteo_id):
    sorteo = get_object_or_404(Sorteo, id=sorteo_id, activo=True)
    ahora = _ahora_cuba()
    hoy = (ahora - timedelta(hours=1)).date()

    hora_salida = _hora_salida_hoy(sorteo, hoy)
    if hora_salida:
        info = _calcular_estado(sorteo, hora_salida, ahora)
        sorteo.estado_actual = info['estado']
        sorteo.segundos_restantes = info['segundos_restantes']
        sorteo.hora_salida_str = hora_salida.strftime('%I:%M %p')
        sorteo.hora_cierre = info['hora_cierre']

        sorteo.hora_cierre_str = info['hora_cierre'].strftime('%I:%M %p') if info['hora_cierre'] else '—'
    else:
        sorteo.estado_actual = 'no_programado'
        sorteo.segundos_restantes = 0
        sorteo.hora_salida_str = '—'
        sorteo.hora_cierre = None

    sorteo.formas_filtradas = _formas_de_sorteo(sorteo)
    return render(request, 'sorteos/sorteo_detalle.html', {'sorteo': sorteo})


def api_sorteos_data(request):
    ahora = _ahora_cuba()
    hoy = (ahora - timedelta(hours=1)).date()
    data = {'sorteos': []}
    for s in Sorteo.objects.filter(activo=True).order_by('nombre'):
        hora_salida = _hora_salida_hoy(s, hoy)
        if not hora_salida:
            continue
        info = _calcular_estado(s, hora_salida, ahora)
        data['sorteos'].append({
            'id': s.id,
            'nombre': s.nombre,
            'estado': info['estado'],
            'segundos_restantes': info['segundos_restantes'],
            'hora_salida': hora_salida.strftime('%I:%M %p').lstrip('0'),
            'origen': s.origen,
        })
    return JsonResponse(data)


def api_sorteos_list(request):
    ahora = _ahora_cuba()
    hoy = (ahora - timedelta(hours=1)).date()
    result = []
    for s in Sorteo.objects.filter(activo=True).order_by('nombre'):
        hora_salida = _hora_salida_hoy(s, hoy)
        if not hora_salida:
            continue
        info = _calcular_estado(s, hora_salida, ahora)
        result.append({
            'id': s.id,
            'nombre': s.nombre,
            'origen': s.origen,
            'activo': s.activo,
            'minutos_cierre': 10,
            'formas_juego': s.formas_juego or [],
            'formas_juego_nombres': [fj.nombre for fj in _formas_de_sorteo(s)],
            'estado': info['estado'],
            'segundos_restantes': info['segundos_restantes'],
            'hora_salida': hora_salida.strftime('%I:%M %p').lstrip('0'),
            'hora_cierre': info['hora_cierre'].strftime('%I:%M %p').lstrip('0') if info['hora_cierre'] else None,
        })
    return JsonResponse({'sorteos': result})


def api_sorteo_detail(request, sorteo_id):
    try:
        sorteo = Sorteo.objects.get(id=sorteo_id, activo=True)
    except Sorteo.DoesNotExist:
        return JsonResponse({'error': 'Sorteo no encontrado'}, status=404)

    ahora = _ahora_cuba()
    hoy = (ahora - timedelta(hours=1)).date()
    hora_salida = _hora_salida_hoy(sorteo, hoy)

    if hora_salida:
        info = _calcular_estado(sorteo, hora_salida, ahora)
        estado = info['estado']
        segundos = info['segundos_restantes']
        hora_cierre = info['hora_cierre']
    else:
        estado, segundos, hora_cierre = 'no_programado', 0, None

    return JsonResponse({
        'id': sorteo.id,
        'nombre': sorteo.nombre,
        'origen': sorteo.origen,
        'activo': sorteo.activo,
        'minutos_cierre': 10,
        'horarios': sorteo.horarios,
        'formas_juego': sorteo.formas_juego or [],
        'formas_disponibles': [{'id': fj.id, 'nombre': fj.nombre, 'activo': fj.activo}
                               for fj in _formas_de_sorteo(sorteo)],
        'estado': estado,
        'segundos_restantes': segundos,
        'hora_salida': hora_salida.strftime('%I:%M %p').lstrip('0') if hora_salida else None,
        'hora_cierre': hora_cierre.strftime('%H:%M') if hora_cierre else None,
    })


def api_sorteos_by_origin(request, origen):
    if origen not in ['dominicano', 'americano', 'haitiano']:
        return JsonResponse({'error': 'Origen no válido'}, status=400)
    ahora = _ahora_cuba()
    hoy = (ahora - timedelta(hours=1)).date()
    result = []
    for s in Sorteo.objects.filter(activo=True, origen=origen).order_by('nombre'):
        hora_salida = _hora_salida_hoy(s, hoy)
        if not hora_salida:
            continue
        info = _calcular_estado(s, hora_salida, ahora)
        result.append({
            'id': s.id, 'nombre': s.nombre, 'origen': s.origen,
            'estado': info['estado'],
            'segundos_restantes': info['segundos_restantes'],
            'hora_salida': hora_salida.strftime('%I:%M %p').lstrip('0'),
        })
    return JsonResponse({'sorteos': result})


def api_sorteos_by_status(request, estado):
    if estado not in ['abierto', 'cerrado', 'salido', 'no_programado']:
        return JsonResponse({'error': 'Estado no válido'}, status=400)
    ahora = _ahora_cuba()
    hoy = (ahora - timedelta(hours=1)).date()
    result = []
    for s in Sorteo.objects.filter(activo=True).order_by('nombre'):
        hora_salida = _hora_salida_hoy(s, hoy)
        if not hora_salida:
            est = 'no_programado'
            seg = 0
            hs = None
        else:
            info = _calcular_estado(s, hora_salida, ahora)
            est = info['estado']
            seg = info['segundos_restantes']
            hs = hora_salida.strftime('%I:%M %p').lstrip('0')
        if est == estado:
            result.append({
                'id': s.id, 'nombre': s.nombre, 'origen': s.origen,
                'estado': est, 'segundos_restantes': seg, 'hora_salida': hs,
            })
    return JsonResponse({'sorteos': result})


def api_sorteos_abiertos(request):
    ahora = _ahora_cuba()
    hoy = (ahora - timedelta(hours=1)).date()
    result = []
    for s in Sorteo.objects.filter(activo=True).order_by('nombre'):
        hora_salida = _hora_salida_hoy(s, hoy)
        if not hora_salida:
            continue
        info = _calcular_estado(s, hora_salida, ahora)
        if info['estado'] == 'abierto':
            result.append({
                'id': s.id, 'nombre': s.nombre, 'origen': s.origen,
                'formas_juego': s.formas_juego or [],
                'segundos_restantes': info['segundos_restantes'],
                'hora_salida': hora_salida.strftime('%I:%M %p').lstrip('0'),
                'hora_cierre': info['hora_cierre'].strftime('%I:%M %p').lstrip('0') if info['hora_cierre'] else None,
            })
    result.sort(key=lambda x: x['segundos_restantes'])
    return JsonResponse({'sorteos': result})


def api_proximos_sorteos(request, horas=4):
    ahora = _ahora_cuba()
    hoy = (ahora - timedelta(hours=1)).date()
    limite = int(horas) * 3600
    result = []
    for s in Sorteo.objects.filter(activo=True):
        dt_salida = get_datetime_salida_cuba(s, hoy)
        if not dt_salida or dt_salida <= ahora:
            continue
        seg = int((dt_salida - ahora).total_seconds())
        if seg <= limite:
            cierre = dt_salida - timedelta(minutes=10)
            result.append({
                'id': s.id, 'nombre': s.nombre, 'origen': s.origen,
                'formas_juego': s.formas_juego or [],
                'estado': 'abierto' if ahora < cierre else 'cerrado',
                'segundos_restantes': seg,
                'hora_salida': dt_salida.strftime('%I:%M %p').lstrip('0'),
            })
    result.sort(key=lambda x: x['segundos_restantes'])
    return JsonResponse({'sorteos': result})


@staff_member_required
def sorteo_crear(request):
    if request.method == 'POST':
        form = SorteoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Sorteo creado correctamente.')
            return redirect('sorteos:lista_sorteos')
    else:
        form = SorteoForm()
    return render(request, 'sorteos/form_sorteo.html', {'form': form, 'titulo': 'Crear Sorteo'})


@staff_member_required
def sorteo_editar(request, sorteo_id):
    sorteo = get_object_or_404(Sorteo, id=sorteo_id)
    if request.method == 'POST':
        form = SorteoForm(request.POST, instance=sorteo)
        if form.is_valid():
            form.save()
            messages.success(request, 'Sorteo actualizado correctamente.')
            return redirect('sorteos:lista_sorteos')
    else:
        form = SorteoForm(instance=sorteo)
    return render(request, 'sorteos/form_sorteo.html', {'form': form, 'sorteo': sorteo, 'titulo': 'Editar Sorteo'})


@staff_member_required
def sorteo_eliminar(request, sorteo_id):
    sorteo = get_object_or_404(Sorteo, id=sorteo_id)
    if request.method == 'POST':
        sorteo.delete()
        messages.success(request, 'Sorteo eliminado correctamente.')
        return redirect('sorteos:lista_sorteos')
    return render(request, 'sorteos/confirmar_eliminar.html', {'sorteo': sorteo})


@staff_member_required
def resultado_crear(request):
    return HttpResponse("Vista de creación de resultados (pendiente de implementar)")


@login_required
def api_sorteos_compartir(request):
    """FIX_COMPARTIR_SORTEOS_V1 (2026-10-16): devuelve texto para WhatsApp
    con los sorteos abiertos en este momento, su hora de cierre y de salida."""
    from datetime import time as _t

    # FIX_TZ_CUBA_V1 (2026-10-16): usar hora Cuba explicitamente,
    # igual que lista_sorteos. Antes usaba timezone.localtime() que devuelve
    # la hora del servidor (UTC) y daba todos los sorteos como cerrados.
    ahora = _ahora_cuba()
    hoy = (ahora - timedelta(hours=1)).date()
    lista = []

    for s in Sorteo.objects.filter(activo=True):
        try:
            hora_salida = _hora_salida_hoy(s, hoy)
            if not hora_salida:
                continue
            info = _calcular_estado(s, hora_salida, ahora)
            if info.get('estado') != 'abierto':
                continue
            hc = info.get('hora_cierre')
            lista.append({'nombre': s.nombre, 'hc': hc, 'hs': hora_salida})
        except Exception:
            continue

    lista.sort(key=lambda x: x['hc'] or _t(23, 59))
    
    # FIX_DEDUP_COMPARTIR_V1: Evitar nombres duplicados en el mensaje
    _vistos = set()
    lista_dedup = []
    for it in lista:
        key = (it['nombre'], it['hc'], it['hs'])
        if key not in _vistos:
            _vistos.add(key)
            lista_dedup.append(it)
    lista = lista_dedup

    # Calendario determinista: no depende del locale del proceso.
    dia_semana = DIAS_SEMANA_ES[hoy.weekday()]
    temporada = _temporada_actual(hoy)

    lines = []
    lines.append("*LOTTOBOOM*")
    lines.append("*SORTEOS ABIERTOS*")
    lines.append(f"📅 *{dia_semana}, {hoy.strftime('%d/%m/%Y')}* ·")
    lines.append(f"Temporada: *{temporada}*")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("")
    if not lista:
        lines.append("❌ No hay sorteos abiertos en este momento.")
    else:
        for it in lista:
            hc_s = it['hc'].strftime('%I:%M %p').lstrip('0') if it['hc'] else '—'
            hs_s = it['hs'].strftime('%I:%M %p').lstrip('0') if it['hs'] else '—'
            lines.append(f"🎯 *{it['nombre']}*")
            lines.append(f"⏰ Cierra: {hc_s}  ·  ")
            lines.append(f"🎲 Sorteo: {hs_s}")
            lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("🔗 https://lottoboom.pythonanywhere.com")
    lines.append("🍀 ¡Juega ya en LottoBooM! 🍀")

    return JsonResponse({'success': True, 'resumen': "\n".join(lines)})
