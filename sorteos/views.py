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
from .utils import segundos_hasta_proximo as _seg_hasta_prox, calcular_estado_sorteo, get_hora_salida, obtener_hora_desde_horarios
from jugadas.models import FormaJuego


CUBA_TZ = ZoneInfo('America/Havana')

def _tz_cuba(fecha):
    """tzinfo con el offset correcto de Cuba (respeta es_verano_cuba)."""
    from LottoBooM.utils import es_verano_cuba
    from datetime import timezone as _dt_tz
    return _dt_tz(timedelta(hours=-4 if es_verano_cuba(fecha) else -5))

def _ahora_cuba():
    """datetime.now() con el offset correcto de Cuba."""
    from datetime import timezone as _dt_tz
    utc = datetime.now(_dt_tz.utc)
    return utc.astimezone(_tz_cuba(utc.date()))



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
    dia_es = {0:'lunes',1:'martes',2:'miercoles',3:'jueves',
              4:'viernes',5:'sabado',6:'domingo'}[hoy.weekday()]
    temp = 'verano' if es_verano_cuba(hoy) else 'invierno'

    if sorteo.horarios:
        hora_str = (sorteo.horarios.get(temp) or {}).get(dia_es)
        if not hora_str:
            return None
        try:
            hh, mm = hora_str.split(':')
            return time(int(hh), int(mm))
        except Exception:
            return None

    return sorteo.hora_salida


def _calcular_estado(sorteo, hora_salida, ahora):
    minutos = sorteo.minutos_cierre if sorteo.minutos_cierre is not None else 60
    dt_salida = datetime.combine(ahora.date(), hora_salida, tzinfo=_tz_cuba(ahora.date()))
    dt_cierre = dt_salida - timedelta(minutes=minutos)

    if ahora < dt_cierre:
        return {
            'estado': 'abierto',
            'segundos_restantes': int((dt_cierre - ahora).total_seconds()),
            'hora_cierre': dt_cierre,
        }
    elif ahora < dt_salida:
        return {
            'estado': 'cerrado',
            'segundos_restantes': int((dt_salida - ahora).total_seconds()),
            'hora_cierre': dt_cierre,
        }
    else:
        return {
            'estado': 'salido',
            'segundos_restantes': 0,
            'hora_cierre': dt_cierre,
        }


def lista_sorteos(request):
    ahora = _ahora_cuba()
    hoy = ahora.date()

    abiertos, cerrados, salidos = [], [], []

    for s in Sorteo.objects.filter(activo=True):
        hora_salida = _hora_salida_hoy(s, hoy)
        if not hora_salida:
            continue

        info = _calcular_estado(s, hora_salida, ahora)

        s.estado_actual = info['estado']
        s.segundos_restantes = info['segundos_restantes']
        s.hora_salida_str = hora_salida.strftime('%I:%M %p')
        s.hora_cierre = info['hora_cierre']

        s.hora_cierre_str = info['hora_cierre'].strftime('%I:%M %p') if info['hora_cierre'] else '—'
        s.hora_salida = hora_salida
        s.formas_filtradas = _formas_de_sorteo(s)

        # FIX_PROXIMO_EN_LISTA_V1: si ya salió, calcular segundos al próximo día
        s.segundos_proximo = 0
        if info['estado'] == 'salido':
            try:
                s.segundos_proximo = _seg_hasta_prox(s, ahora) or 0
            except Exception:
                s.segundos_proximo = 0

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

    mes = hoy.month
    if 4 <= mes <= 10:
        temporada_actual, proxima_temporada = 'Verano', 'Invierno'
    else:
        temporada_actual, proxima_temporada = 'Invierno', 'Verano'

    context = {
        'sorteos': sorteos_ordenados,
        'total_sorteos': len(sorteos_ordenados),
        'total_abiertos': len(abiertos),
        'total_cerrados': len(cerrados),
        'total_salidos': len(salidos),
        'temporada_actual': temporada_actual,
        'proxima_temporada': proxima_temporada,
        'dias_restantes_cambio': 0,
        'dia_semana_actual': hoy.strftime('%A'),
    }
    return render(request, 'sorteos/sorteos.html', context)


def detalle_sorteo(request, sorteo_id):
    sorteo = get_object_or_404(Sorteo, id=sorteo_id, activo=True)
    ahora = _ahora_cuba()
    hoy = ahora.date()

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
    hoy = ahora.date()
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
    hoy = ahora.date()
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
            'minutos_cierre': s.minutos_cierre,
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
    hoy = ahora.date()
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
        'minutos_cierre': sorteo.minutos_cierre,
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
    hoy = ahora.date()
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
    hoy = ahora.date()
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
    hoy = ahora.date()
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
    hoy = ahora.date()
    limite = int(horas) * 3600
    result = []
    for s in Sorteo.objects.filter(activo=True):
        hora_salida = _hora_salida_hoy(s, hoy)
        if not hora_salida:
            continue
        dt_salida = datetime.combine(hoy, hora_salida, tzinfo=_tz_cuba(hoy))
        if dt_salida <= ahora:
            continue
        seg = int((dt_salida - ahora).total_seconds())
        if seg <= limite:
            minutos = s.minutos_cierre if s.minutos_cierre is not None else 60
            cierre = dt_salida - timedelta(minutes=minutos)
            result.append({
                'id': s.id, 'nombre': s.nombre, 'origen': s.origen,
                'formas_juego': s.formas_juego or [],
                'estado': 'abierto' if ahora < cierre else 'cerrado',
                'segundos_restantes': seg,
                'hora_salida': hora_salida.strftime('%I:%M %p').lstrip('0'),
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
    hoy = ahora.date()
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

    # FIX_SORTEOS_TEMPORADA_V1: dia de semana + fecha + temporada
    DIAS_ES = {
        0: 'Lunes', 1: 'Martes', 2: 'Miercoles', 3: 'Jueves',
        4: 'Viernes', 5: 'Sabado', 6: 'Domingo',
    }
    dia_semana = DIAS_ES.get(hoy.weekday(), hoy.strftime('%A'))
    temporada = 'Verano' if es_verano_cuba(hoy) else 'Invierno'

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
