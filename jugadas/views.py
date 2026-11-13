# -*- coding: utf-8 -*-
import json
import re
import logging
import traceback
import os
import threading
from decimal import Decimal
from datetime import datetime, timedelta, time
from collections import defaultdict
from zoneinfo import ZoneInfo

import pytz
from django.conf import settings
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.db import transaction
from django.db.models import Q, Sum, Count
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.db.models.functions import TruncDate
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.core.management import call_command

from LottoBooM.utils import es_verano_cuba
from resultados.models import Premio
from roles.models import Rol, Fondo, Bono, Subordinacion, Notificacion, MovimientoFondo, NumeroRestringido
from sorteos.models import Sorteo
from sorteos.utils import get_sorteos_abiertos, calcular_estado_sorteo, get_hora_salida
from sorteos.utils import segundos_hasta_proximo as _seg_hasta_prox
from pagos.models import FormaPago
from roles.utils import get_pool_gestor, get_dosis_gestor, get_sobrelimite_gestor
from jugadas.utils import consumir_postpago, liquidar_postpago, otorgar_postpago
from .models import Jugada, FormaJuego, Boleta, ClienteOffline

import os
import threading
from django.core.management import call_command
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
# FIX URGENTE: FORZAR ZONA HORARIA DE CUBA (UTC-4)
# ═══════════════════════════════════════════════════════════════
def _obtener_sorteos_cuba_estricto():
    """
    Calcula la hora real en Cuba y devuelve solo los sorteos abiertos.
    """
    try:
        CUBA_TZ = ZoneInfo('America/Havana')
    except Exception:
        CUBA_TZ = pytz.timezone('America/Havana')

    ahora_cuba = timezone.now().astimezone(CUBA_TZ)
    fecha_cuba = ahora_cuba.date()

    sorteos_validos = []

    for s in Sorteo.objects.filter(activo=True).order_by('hora_salida'):
        temp = 'verano' if es_verano_cuba(fecha_cuba) else 'invierno'
        dia_es = {0: 'lunes', 1: 'martes', 2: 'miercoles', 3: 'jueves', 4: 'viernes', 5: 'sabado', 6: 'domingo'}[fecha_cuba.weekday()]

        hora_salida = None
        if s.horarios and temp in s.horarios and dia_es in s.horarios[temp]:
            hora_str = s.horarios[temp][dia_es]
            try:
                hh, mm = hora_str.split(':')
                hora_salida = time(int(hh), int(mm))
            except Exception:
                pass

        if not hora_salida:
            hora_salida = s.hora_salida

        if not hora_salida:
            continue

        # Calcular salida y cierre en hora Cuba
        dt_salida = datetime.combine(fecha_cuba, hora_salida).replace(tzinfo=CUBA_TZ)

        # Si la hora de salida es de madrugada, pertenece al día siguiente.
        if hora_salida.hour < 6:
            dt_salida += timedelta(days=1)

        minutos_cierre = s.minutos_cierre if s.minutos_cierre is not None else 60
        dt_cierre = dt_salida - timedelta(minutes=minutos_cierre)

        # ¿Estamos antes del cierre?
        if ahora_cuba < dt_cierre:
            s.estado_actual = 'abierto'
            s.hora_salida = hora_salida
            s.hora_cierre = dt_cierre
            s.hora_salida_str = hora_salida.strftime('%I:%M %p').lstrip('0')
            sorteos_validos.append(s)

    return sorteos_validos

# ═══════════════════════════════════════════════════════════════
# Helper · Detecta si una BOLETA completa ya existe en BD
# Firma = (cliente, sorteo, fecha, forma_pago, sorted[(numero, forma_juego, monto)])
# ═══════════════════════════════════════════════════════════════
def _boleta_duplicada(cliente_id, forma_pago_id, fecha_sorteo, items):
    """
    Detecta si los items forman una boleta IDENTICA a una ya existente.
    Compara por BOLETA (no mezcla jugadas de boletas distintas).
    Firma = (cliente, sorteo, fecha, FP, sorted[(numero, forma_juego, monto)])
    """
    from decimal import Decimal, InvalidOperation
    from collections import defaultdict

    if not items or not cliente_id or not forma_pago_id or not fecha_sorteo:
        return []

    # ─── Agrupar items nuevos por sorteo_id ───
    por_sorteo = defaultdict(list)
    for it in items:
        sid = it.get('sorteo_id')
        if not sid:
            continue
        try:
            num_norm = str(it.get('numero', '')).strip().upper()
            tipo_norm = str(it.get('tipo', '')).strip().lower()
            monto_dec = Decimal(str(it.get('monto', 0))).quantize(Decimal('0.01'))
        except (InvalidOperation, ValueError, TypeError):
            continue
        if not num_norm:
            continue
        por_sorteo[sid].append((num_norm, tipo_norm, str(monto_dec)))

    # ─── Para cada sorteo, comparar contra CADA boleta existente ───
    duplicados = []
    for sid, firma_nueva in por_sorteo.items():
        firma_nueva_set = set(firma_nueva)
        if not firma_nueva_set:
            continue

        # FIX_DUP_SIN_VENTANA_V1: bloquear duplicados sin importar tiempo
        # (mientras la boleta siga activa y sea exactamente la misma)
        boletas = Boleta.objects.filter(
            usuario_id=cliente_id,
            fecha_sorteo=fecha_sorteo,
            forma_pago_id=forma_pago_id,
            estado='activa',
            jugadas__sorteo_id=sid,
            jugadas__estado__in=['confirmada', 'pendiente'],
        ).distinct()

        for b in boletas:
            # Jugadas SOLO de esta boleta y este sorteo
            jugadas = b.jugadas.filter(
                sorteo_id=sid,
                estado__in=['confirmada', 'pendiente'],
            ).values('numero', 'forma_juego__nombre', 'monto')

            firma_existente = set()
            for j in jugadas:
                num_norm = str(j['numero'] or '').strip().upper()
                tipo_norm = str(j['forma_juego__nombre'] or '').strip().lower()
                try:
                    monto_norm = str(Decimal(str(j['monto'])).quantize(Decimal('0.01')))
                except (InvalidOperation, ValueError, TypeError):
                    monto_norm = str(j['monto'])
                firma_existente.add((num_norm, tipo_norm, monto_norm))

            if firma_nueva_set == firma_existente:
                duplicados.append({
                    'sorteo_id': sid,
                    'boleta_id': b.id,
                    'boleta_ref': b.referencia,
                    'cantidad': len(firma_nueva_set),
                })
                break  # con 1 match es suficiente

    return duplicados


# ═══════════════════════════════════════════════════════════════
# Helper · Consolidar tripletas (FIX_TRIPLETA_V1)
# ═══════════════════════════════════════════════════════════════
def _consolidar_tripletas(items):
    """Agrupa items tripleta con mismo (sorteo_id, monto) en uno solo."""
    if not items:
        return items
    otros = []
    tripletas_por_key = {}
    for it in items:
        tipo = (it.get('tipo') or '').strip().lower()
        if tipo != 'tripleta':
            otros.append(it)
            continue
        key = (it.get('sorteo_id'), str(it.get('monto', 0)))
        if key not in tripletas_por_key:
            tripletas_por_key[key] = {
                'tipo': it.get('tipo'),
                'numero': it.get('numero', ''),
                'monto': it.get('monto', 0),
                'sorteo_id': it.get('sorteo_id'),
            }
        else:
            nums_prev = tripletas_por_key[key]['numero']
            nums_new = it.get('numero', '')
            tripletas_por_key[key]['numero'] = (nums_prev + ' ' + nums_new).strip()
    return otros + list(tripletas_por_key.values())


# ─── Rangos de teléfonos offline ─────────────────────────────
BLOQUES_DISPONIBLES = 10
MAX_DENTRO_BLOQUE = 9_999_999

def _siguiente_telefono_offline():
    """
    Genera el siguiente teléfono del rango offline.
    Bloque actual: +5350XXXXXXX (10M).
    """
    for bloque in range(BLOQUES_DISPONIBLES):
        prefijo = f"+535{bloque}"
        existentes = ClienteOffline.objects.filter(
            telefono_offline__startswith=prefijo
        ).values_list('telefono_offline', flat=True)

        max_n = -1
        for tel in existentes:
            try:
                n = int(tel[len(prefijo):])
                if n > max_n:
                    max_n = n
            except (ValueError, IndexError):
                continue

        if max_n < MAX_DENTRO_BLOQUE:
            return f"{prefijo}{max_n + 1:07d}"

    raise RuntimeError('Rango completo de teléfonos offline agotado (100M usados)')


def _get_telefono(user):
    """Devuelve el telefono del usuario desde su perfil, o '' si no tiene."""
    if not user:
        return ''
    try:
        perfil = getattr(user, 'perfil', None)
        if perfil is not None:
            return getattr(perfil, 'telefono', '') or ''
    except Exception:
        pass
    return ''


def _get_banco_de(user):
    """Devuelve el banco superior del user, si existe. None si no hay."""
    if not user or not user.id:
        return None
    sub = Subordinacion.objects.filter(
        subordinado=user, activo=True
    ).select_related('jefe').first()
    if sub and sub.jefe:
        if sub.jefe.is_superuser or sub.jefe.roles.filter(tipo='banco', activo=True).exists():
            return sub.jefe
    return None

def _construir_clientes_visibles(user, gestor_cuenta_id=None):
    """
    Personas visibles para `user` al apostar.

    FIX_CLIENTES_VISIBLES_V2:
      - Cliente    → solo gestores con los que tenga FONDO activo > 0,
                     BONO activo > 0 o POSTPAGO pendiente > 0.
      - Comercial  → solo clientes que ÉL mismo haya recargado.
      - Banco      → clientes recargados por él O por sus comerciales.
      - Superadmin → todos los usuarios activos.

    NUEVO (selector "Bajo cuenta de"):
      - Si `gestor_cuenta_id` viene y user es banco o superadmin,
        se delega la consulta a ese gestor (como si ese gestor
        estuviera consultando).
      - Si coincide con user.id, o no viene, comportamiento normal.
    """
    es_superadmin = user.is_superuser or user.roles.filter(tipo='superadmin', activo=True).exists()
    es_banco      = user.roles.filter(tipo='banco', activo=True).exists()
    es_comercial  = user.roles.filter(tipo='comercial', activo=True).exists()
    es_cliente    = user.roles.filter(tipo='cliente', activo=True).exists()

    # ═══ NUEVO: filtro por gestor seleccionado ═══
    if gestor_cuenta_id and (es_superadmin or es_banco):
        try:
            gid = int(gestor_cuenta_id)
            if gid != user.id:
                if es_superadmin:
                    gestor_sel = User.objects.get(id=gid, is_active=True)
                else:
                    # banco: solo sus comerciales reales (ascendidos por él)
                    gestor_sel = User.objects.get(
                        id=gid, is_active=True,
                        roles__tipo='comercial', roles__activo=True,
                        jefes__jefe=user, jefes__activo=True,
                    )
                return _construir_clientes_visibles(gestor_sel)
        except (User.DoesNotExist, User.MultipleObjectsReturned, ValueError, TypeError):
            pass

    # ═══════════════════════════════════════════════════════════
    # CASO CLIENTE → gestores con fondo/bono/postpago > 0
    # ═══════════════════════════════════════════════════════════
    if es_cliente and not (es_superadmin or es_banco or es_comercial):
        gestor_ids = set()

        for gid in Fondo.objects.filter(
            usuario=user, activo=True, monto__gt=0
        ).values_list('asignado_por_id', flat=True):
            if gid:
                gestor_ids.add(gid)

        for gid in Bono.objects.filter(
            usuario=user, estado='activo', saldo_restante__gt=0
        ).values_list('asignado_por_id', flat=True):
            if gid:
                gestor_ids.add(gid)

        try:
            from roles.models import Postpago
            for gid in Postpago.objects.filter(
                cliente=user, saldo__lt=0
            ).values_list('gestor_id', flat=True):
                if gid:
                    gestor_ids.add(gid)
        except Exception:
            pass

        gestores = User.objects.filter(id__in=gestor_ids, is_active=True).exclude(id=user.id)

        result = []
        for u in gestores:
            rol_obj = u.roles.filter(activo=True).first()
            result.append({
                'id': u.id,
                'nombre': u.username,
                'telefono': _get_telefono(u),
                'saldo_total': 0.0,
                'saldo_real': 0.0,
                'bonos_activos': 0.0,
                'rol': rol_obj.tipo if rol_obj else ('superadmin' if u.is_superuser else 'gestor'),
                'es_offline': False,
            })

        result.sort(key=lambda c: c['nombre'].lower())
        return result

    # ═══════════════════════════════════════════════════════════
    # CASO GESTOR
    # ═══════════════════════════════════════════════════════════
    if not (es_superadmin or es_banco or es_comercial):
        return []

    ids = set()
    _huerfanos_ids = set()

    if es_superadmin:
        ids.update(
            User.objects.filter(is_active=True).exclude(id=user.id)
            .values_list('id', flat=True)
        )
    else:
        # Clientes que YO recargué (fondo activo con monto > 0)
        ids.update(
            Fondo.objects.filter(
                asignado_por=user, activo=True, monto__gt=0
            ).values_list('usuario_id', flat=True).distinct()
        )
        # Clientes con bono activo asignado por mí
        ids.update(
            Bono.objects.filter(
                asignado_por=user, estado='activo', saldo_restante__gt=0
            ).values_list('usuario_id', flat=True).distinct()
        )
        # Clientes con postpago activo asignado por mí (deuda pendiente)
        try:
            from roles.models import Postpago as _PP
            ids.update(
                _PP.objects.filter(
                    gestor=user, activo=True, saldo__lt=0
                ).values_list('cliente_id', flat=True).distinct()
            )
        except Exception:
            pass

        if es_banco:
            # FIX_BANCO_VE_TODOS_V1: el banco ve TODOS los clientes activos
            # (no solo los que ha recargado o los asignados a él)
            ids.update(
                User.objects.filter(
                    is_active=True,
                    roles__tipo='cliente',
                    roles__activo=True,
                ).values_list('id', flat=True).distinct()
            )
            # Además: clientes recargados por MIS comerciales directos
            comerciales_ids = list(
                Subordinacion.objects.filter(jefe=user, activo=True)
                .values_list('subordinado_id', flat=True)
            )
            if comerciales_ids:
                ids.update(
                    Fondo.objects.filter(
                        asignado_por__in=comerciales_ids, activo=True, monto__gt=0
                    ).values_list('usuario_id', flat=True).distinct()
                )
                ids.update(
                    Bono.objects.filter(
                        asignado_por__in=comerciales_ids, estado='activo', saldo_restante__gt=0
                    ).values_list('usuario_id', flat=True).distinct()
                )
                try:
                    from roles.models import Postpago as _PP2
                    ids.update(
                        _PP2.objects.filter(
                            gestor__in=comerciales_ids, activo=True, saldo__lt=0
                        ).values_list('cliente_id', flat=True).distinct()
                    )
                except Exception:
                    pass

        # FIX_HUERFANOS_VISIBLES_V1: clientes sin gestor (solo bono con asignado_por=None)
        try:
            from django.utils import timezone as _tzH
            from django.db.models import Q as _QH
            _huerfanos_bono = set(Bono.objects.filter(
                asignado_por__isnull=True, estado='activo', saldo_restante__gt=0,
            ).filter(
                _QH(fecha_vencimiento__isnull=True) | _QH(fecha_vencimiento__gte=_tzH.now())
            ).values_list('usuario_id', flat=True))
            _con_gestor = set(Fondo.objects.filter(
                activo=True, asignado_por__isnull=False
            ).values_list('usuario_id', flat=True))
            _huerfanos_ids = _huerfanos_bono - _con_gestor
            ids.update(_huerfanos_ids)
        except Exception:
            _huerfanos_ids = set()

    ids.discard(user.id)

    if not ids:
        return []

    result = []
    for u in User.objects.filter(id__in=ids, is_active=True).distinct():
        from decimal import Decimal as _Dec2
        try:
            from roles.utils import calcular_saldos_cliente as _calc_saldos
            _gestor_arg = None if es_superadmin else user
            _saldos_u = _calc_saldos(u, gestor=_gestor_arg)
        except Exception:
            _saldos_u = {'por_gestor': {}, 'total_global': {}}

        _tg = _saldos_u.get('total_global') or {}
        saldo_total = float(_tg.get('saldo_total') or _Dec2('0'))
        saldo_real  = float(_tg.get('saldo_real') or _Dec2('0'))
        total_bonos = float(_tg.get('bonos') or _Dec2('0'))
        total_post  = float(_tg.get('postpago') or _Dec2('0'))

        rol_obj = u.roles.filter(activo=True).first()
        es_offline = hasattr(u, 'cliente_offline')

        result.append({
            'id': u.id,
            'nombre': u.username,
            'telefono': _get_telefono(u),
            'saldo_total': saldo_total,
            'saldo_real': saldo_real,
            'bonos_activos': total_bonos,
            'postpago': total_post,
            'rol': rol_obj.tipo if rol_obj else ('superadmin' if u.is_superuser else 'cliente'),
            'es_offline': es_offline,
            'es_huerfano': u.id in _huerfanos_ids,
        })

    result.sort(key=lambda c: c['nombre'].lower())
    return result


# ============================================================
# MAPEO DE TABLAS
# ============================================================
TABLA_FORMA_MAP = {
    'tabla-tradicional': ['pick2', 'pf', 'fijo', 'corridos', 'parlet', 'candado'],
    'tabla-pick3': ['pick3'],
    'tabla-centenas': ['centenas corridas'],
    'tabla-pick4': ['pick4'],
    'tabla-pick5': ['pick5'],
    'tabla-vs': ['vs'],
    'tabla-vspf': ['vspf'],
    'tabla-vspick2': ['vspick2'],
    'tabla-pick2vspf': ['pick2vspf'],
    'tabla-vs100': ['vs100'],
    'tabla-posiciones': ['posicion'],
    'tabla-tripleta': ['tripleta'],
}


def obtener_configuracion_sorteo(sorteo):
    nombre_sorteo = sorteo.nombre.strip()
    formas_disponibles = sorteo.formas_juego or []
    formas_normalizadas = [f.strip().lower() for f in formas_disponibles]
    es_florida = 'florida' in nombre_sorteo.lower()
    es_pega3 = 'pega 3' in nombre_sorteo.lower()
    es_especial_fijo = nombre_sorteo in ['Quemaito', 'Quinielón']

    todas_formas = set()
    for formas in TABLA_FORMA_MAP.values():
        todas_formas.update(formas)

    config_formas = {}
    for forma in todas_formas:
        if es_florida:
            config_formas[forma] = True
        elif es_especial_fijo:
            config_formas[forma] = (forma == 'fijo')
        elif es_pega3:
            config_formas[forma] = (forma in formas_normalizadas)
        else:
            config_formas[forma] = (forma in formas_normalizadas)

    if config_formas.get('fijo', False):
        config_formas['parlet'] = True
        config_formas['vs100'] = True

    # FIX_CIERRE_V1: candado visible siempre que parlet esté activo
    # FIX_VS_CON_PARLET_V1: VS básica visible cuando parlet está activo
    if config_formas.get('parlet', False):
        config_formas['candado'] = True
        config_formas['vs'] = True

    if not config_formas.get('fijo', False) and not config_formas.get('corridos', False):
        if 'posicion' not in formas_normalizadas:
            config_formas['posicion'] = False
        if 'tripleta' not in formas_normalizadas:
            config_formas['tripleta'] = False

    tiene_pick3 = 'pick3' in formas_normalizadas
    tiene_pick4 = 'pick4' in formas_normalizadas
    if tiene_pick3 and tiene_pick4 and not es_florida:
        config_formas['vspick2'] = False
        config_formas['pick2vspf'] = False
        config_formas['pick5'] = False

    es_dominicano = any(dominicano in nombre_sorteo.lower() for dominicano in [
        'anguila', 'haiti', 'lotedom', 'primera', 'real', 'king',
        'new york', 'new yol', 'new jersey', 'nacional', 'leidsa'
    ])
    if es_dominicano and not es_florida:
        for forma in ['pick2', 'pick3', 'pick4', 'pick5', 'vspick2', 'pick2vspf']:
            if not es_pega3:
                if forma not in formas_normalizadas:
                    config_formas[forma] = False

    tablas_visibles = []
    for tabla_id, formas_necesarias in TABLA_FORMA_MAP.items():
        if any(config_formas.get(forma, False) for forma in formas_necesarias):
            tablas_visibles.append(tabla_id)

    superparlet_visible = not es_especial_fijo

    columnas_tradicional = {
        'pick2': config_formas.get('pick2', False),
        'pf': config_formas.get('pf', False),
        'fijo': config_formas.get('fijo', False),
        'corridos': config_formas.get('corridos', False),
        'parlet': config_formas.get('parlet', False),
        'candado': config_formas.get('candado', False),
    }

    return {
        'config': config_formas,
        'tablas_visibles': tablas_visibles,
        'superparlet_visible': superparlet_visible,
        'columnas_tradicional': columnas_tradicional,
    }

# ============================================================
# AGRUPACIÓN CENTRADA EN BOLETA (v4)
# ============================================================
def agrupar_jugadas(qs):
    from collections import OrderedDict

    buckets_normal = OrderedDict()
    buckets_super  = OrderedDict()
    huerfanas      = {}

    def _nueva_entry(j, es_super=False):
        return {
            'boleta': j.boleta,
            'boletas': set(),  # FIX_AGRUPAR_CLIENTE_SORTEO_V1
            'cliente': j.usuario,
            'destinatario': j.destinatario,
            'forma_pago': j.forma_pago,
            'fecha_sorteo': j.fecha_sorteo,
            'es_super': es_super,
            'lineas': [],
            'total_apostado': Decimal('0.00'),
            'total_premios': Decimal('0.00'),
            'estados': set(),
            'agentes': set(),
        }

    for j in qs.select_related(
        'boleta', 'sorteo', 'forma_juego', 'forma_pago',
        'usuario', 'destinatario', 'comercial'
    ):
        es_super = (j.forma_juego and j.forma_juego.nombre.lower() == 'superparlet')

        # FIX_AGRUPAR_CLIENTE_SORTEO_V1: agrupar por (cliente, sorteo, fecha)
        key = (j.usuario_id, j.sorteo_id, j.fecha_sorteo, es_super)
        if j.boleta_id:
            bucket = buckets_super if es_super else buckets_normal
            entry = bucket.setdefault(key, _nueva_entry(j, es_super))
        else:
            entry = huerfanas.setdefault(key, _nueva_entry(j, es_super))

        if j.boleta_id:
            entry['boletas'].add(j.boleta_id)
        entry['lineas'].append(j)
        entry['total_apostado'] += j.monto
        if j.monto_premio:
            entry['total_premios'] += j.monto_premio
        entry['estados'].add(j.estado)

        if j.comercial:
            entry['agentes'].add(j.comercial.username)
        elif j.usuario_id == j.destinatario_id:
            entry['agentes'].add('Autoapuesta')
        elif j.destinatario:
            entry['agentes'].add(j.destinatario.username)

    def _procesar(entry):
        por_sorteo = OrderedDict()
        sorteo_pair_label = None

        for j in entry['lineas']:
            sid = j.sorteo_id
            s = por_sorteo.setdefault(sid, {
                'sorteo': j.sorteo,
                'por_forma': OrderedDict(),
                'total': Decimal('0.00'),
                'premios': Decimal('0.00'),
            })
            s['total'] += j.monto
            if j.monto_premio:
                s['premios'] += j.monto_premio

            fkey = j.forma_juego.nombre if j.forma_juego else 'Sin tipo'
            if fkey.lower() == 'candado':
                fkey = 'parlet'

            f_entry = s['por_forma'].setdefault(fkey, {
                'forma_nombre': fkey,
                'por_monto': OrderedDict(),
                'total': Decimal('0.00'),
                'estados': set(),
            })
            f_entry['total'] += j.monto
            f_entry['estados'].add(j.estado)

            mkey = f"{j.monto:.2f}"
            m_entry = f_entry['por_monto'].setdefault(mkey, {
                'monto': j.monto, 'numeros': [],
                'premios': Decimal('0.00'), 'estados': set(),
            })
            m_entry['numeros'].append({'numero': j.numero, 'estado': j.estado})
            if j.monto_premio:
                m_entry['premios'] += j.monto_premio
            m_entry['estados'].add(j.estado)

        if entry['es_super'] and entry['lineas']:
            meta = (entry['lineas'][0].metadata or {})
            par = meta.get('sorteos', [])
            if len(par) == 2:
                s1 = Sorteo.objects.filter(id=par[0]).first()
                s2 = Sorteo.objects.filter(id=par[1]).first()
                if s1 and s2:
                    sorteo_pair_label = f"{s1.nombre} / {s2.nombre}"

        sorteos_list = []
        for s in por_sorteo.values():
            formas_list = []
            for f in s['por_forma'].values():
                numeros_con_monto = []
                for m in f['por_monto'].values():
                    for num_dict in m['numeros']:
                        numeros_con_monto.append({
                            'monto': m['monto'],
                            'numero': num_dict['numero'],
                            'estado': num_dict['estado'],
                            'premios': m['premios'],
                        })
                numeros_con_monto.sort(key=lambda g: -float(g['monto']))
                est_f = next((e for e in ('ganadora', 'pendiente', 'perdedora')
                              if e in f['estados']), 'finalizada')
                formas_list.append({
                    'forma_nombre': f['forma_nombre'],
                    'numeros_con_monto': numeros_con_monto,
                    'monto_total': f['total'],
                    'estado': est_f,
                })
            formas_list.sort(key=lambda x: x['forma_nombre'])
            sorteos_list.append({
                'sorteo': s['sorteo'],
                'formas_juego': formas_list,
                'total': s['total'],
                'premios': s['premios'],
            })

        est = entry['estados']
        boleta_obj = entry['boleta']
        if boleta_obj and boleta_obj.estado == 'cancelada':
            estado_general = 'cancelada'
        elif 'cancelada' in est and len(est) == 1:
            estado_general = 'cancelada'
        elif 'ganadora' in est:
            estado_general = 'ganadora'
        elif 'pendiente' in est:
            estado_general = 'pendiente'
        elif 'perdedora' in est:
            estado_general = 'perdedora'
        else:
            estado_general = 'finalizada'

        boletas_ids = sorted(entry.get('boletas', set()))
        boletas_count = len(boletas_ids)
        if boleta_obj and boletas_count > 1:
            referencia_display = f"{boleta_obj.referencia} +{boletas_count - 1}"
        elif boleta_obj:
            referencia_display = boleta_obj.referencia
        else:
            referencia_display = '— sin boleta —'

        return {
            'boleta': boleta_obj,
            'boleta_id': boleta_obj.id if boleta_obj else None,
            'boletas_ids': boletas_ids,
            'boletas_count': boletas_count,
            'referencia': referencia_display,
            'cliente': entry['cliente'],
            'destinatario': entry['destinatario'],
            'forma_pago': entry['forma_pago'],
            'fecha_sorteo': entry['fecha_sorteo'],
            'creado_en': entry['lineas'][0].fecha if entry['lineas'] else None,
            'total_apostado': entry['total_apostado'],
            'total_premios': entry['total_premios'],
            'ganancia_neta': entry['total_premios'] - entry['total_apostado'],
            'cantidad_numeros': len(entry['lineas']),
            'cantidad_sorteos': len(sorteos_list),
            'estado_general': estado_general,
            'agentes': ', '.join(sorted(entry['agentes'])) or 'Autoapuesta',
            'sorteos': sorteos_list,
            'sorteo_pair_label': sorteo_pair_label,
            'es_super': entry['es_super'],
        }

    normales = [_procesar(e) for e in buckets_normal.values()]
    supers   = [_procesar(e) for e in buckets_super.values()]
    huerf    = [_procesar(e) for e in huerfanas.values()]

    def _key(b):
        return (b['fecha_sorteo'] or timezone.localdate(), b['boleta_id'] or 0)

    normales.sort(key=_key, reverse=True)
    supers.sort(key=_key, reverse=True)
    normales = huerf + normales

    return normales, supers

# ============================================================
# FUNCIÓN AUXILIAR
# ============================================================
def crear_notificacion(usuario, tipo, mensaje, datos=None, prioridad='media', categoria='general'):
    if not usuario:
        return
    Notificacion.objects.create(
        usuario=usuario, tipo=tipo, mensaje=mensaje, datos=datos or {},
        prioridad=prioridad, categoria=categoria, leido=False
    )


# ============================================================
# VALIDACIÓN DE PERMISOS JERÁRQUICOS
# ============================================================
def tiene_permiso_jerarquico(apostador, objetivo_id):
    es_superadmin = apostador.is_superuser or apostador.roles.filter(tipo='superadmin', activo=True).exists()
    if es_superadmin:
        return True

    es_banco = apostador.roles.filter(tipo='banco', activo=True).exists()
    es_comercial = apostador.roles.filter(tipo='comercial', activo=True).exists()

    if not (es_banco or es_comercial):
        gestores_ids = set()
        for f in Fondo.objects.filter(usuario=apostador, activo=True).select_related('asignado_por'):
            if f.asignado_por:
                gestores_ids.add(f.asignado_por.id)
        for b in Bono.objects.filter(usuario=apostador, estado='activo'):
            if b.asignado_por:
                gestores_ids.add(b.asignado_por.id)
        for rec in MovimientoFondo.objects.filter(receptor=apostador, tipo__iexact='recarga'):
            if rec.emisor:
                gestores_ids.add(rec.emisor.id)
        for sa in User.objects.filter(roles__tipo='superadmin', roles__activo=True):
            gestores_ids.add(sa.id)
        return objetivo_id in gestores_ids

    if Subordinacion.objects.filter(jefe=apostador, subordinado_id=objetivo_id, activo=True).exists():
        return True
    if Fondo.objects.filter(asignado_por=apostador, usuario_id=objetivo_id, activo=True).exists():
        return True
    if MovimientoFondo.objects.filter(
        Q(emisor=apostador) | Q(receptor=apostador),
        Q(emisor_id=objetivo_id) | Q(receptor_id=objetivo_id),
        tipo__iexact='recarga'
    ).exists():
        return True

    if es_banco:
        comerciales_ids = Subordinacion.objects.filter(jefe=apostador, activo=True).values_list('subordinado_id', flat=True)
        if Subordinacion.objects.filter(jefe__in=comerciales_ids, subordinado_id=objetivo_id, activo=True).exists():
            return True
        if Fondo.objects.filter(asignado_por__in=comerciales_ids, usuario_id=objetivo_id, activo=True).exists():
            return True

    return False


# ============================================================
# HELPER DE CANCELACIÓN (core reutilizable)
# ============================================================
def _do_cancelar_boleta(boleta, user, motivo=''):
    if not boleta.puede_cancelar():
        return False, None, f"Boleta en estado '{boleta.estado}', no se puede cancelar"

    jugadas = list(boleta.jugadas.exclude(estado='cancelada'))
    if not jugadas:
        return False, None, 'La boleta no tiene jugadas activas'

    es_superadmin = user.is_superuser or user.roles.filter(tipo='superadmin', activo=True).exists()
    es_banco = user.roles.filter(tipo='banco', activo=True).exists()
    if not (es_superadmin or es_banco):
        for j in jugadas:
            if not j.puede_modificar():
                return False, None, f"El sorteo '{j.sorteo.nombre}' ya cerró."

    monto_a_reintegrar = sum(j.monto for j in jugadas)
    pago = (boleta.metadata or {}).get('pago')

    if not pago or not any(
        pago.get(k, '0.00') not in ('0', '0.00', None, '')
        for k in ('fondo', 'bono', 'postpago')
    ):
        monto_fondo_orig    = monto_a_reintegrar
        monto_bono_orig     = Decimal('0.00')
        monto_postpago_orig = Decimal('0.00')
        total_original      = monto_a_reintegrar
    else:
        monto_fondo_orig    = Decimal(str(pago.get('fondo', '0.00')))
        monto_bono_orig     = Decimal(str(pago.get('bono', '0.00')))
        monto_postpago_orig = Decimal(str(pago.get('postpago', '0.00')))
        total_original      = monto_fondo_orig + monto_bono_orig + monto_postpago_orig

    factor = Decimal('1.00')
    if total_original > 0 and monto_a_reintegrar < total_original:
        factor = (monto_a_reintegrar / total_original).quantize(Decimal('0.0001'))

    monto_fondo    = (monto_fondo_orig * factor).quantize(Decimal('0.01'))
    monto_bono     = (monto_bono_orig * factor).quantize(Decimal('0.01'))
    monto_postpago = (monto_postpago_orig * factor).quantize(Decimal('0.01'))

    detalle = {'fondo': Decimal('0.00'), 'bono': Decimal('0.00'), 'postpago': Decimal('0.00')}
    reintegr_total = Decimal('0.00')
    forma_pago_ref = jugadas[0].forma_pago

    if monto_fondo > 0 and forma_pago_ref:
        fondo, _ = Fondo.objects.select_for_update().get_or_create(
            usuario=boleta.usuario, forma_pago=forma_pago_ref,
            asignado_por=boleta.destinatario,
            defaults={'monto': Decimal('0.00'), 'activo': True},
        )
        fondo.monto += monto_fondo
        fondo.save(update_fields=['monto'])
        detalle['fondo'] = monto_fondo
        reintegr_total += monto_fondo
        MovimientoFondo.objects.create(
            emisor=boleta.destinatario, receptor=boleta.usuario,
            forma_pago=forma_pago_ref, monto=monto_fondo,
            tipo='ajuste', estado='confirmado',
            motivo=f"Cancelación boleta {boleta.referencia}",
            datos_transferencia={
                'boleta_id': boleta.id,
                'referencia': str(boleta.referencia),
                'cancelacion': True,
                'motivo': motivo or '',
            },
            nota=f"Reembolso por cancelación. Motivo: {motivo or 'sin motivo'}",
            saldo_antes=fondo.monto - monto_fondo,
            saldo_despues=fondo.monto,
        )

    if monto_bono > 0:
        bono_obj = Bono.objects.select_for_update().filter(
            usuario=boleta.usuario, asignado_por=boleta.destinatario,
            estado__in=['activo', 'agotado'],
        ).order_by('-creado_en').first()
        if bono_obj:
            bono_obj.saldo_restante += monto_bono
            if bono_obj.saldo_restante > 0 and bono_obj.estado == 'agotado':
                bono_obj.estado = 'activo'
            bono_obj.save(update_fields=['saldo_restante', 'estado'])
            detalle['bono'] = monto_bono
            reintegr_total += monto_bono

    if monto_postpago > 0 and forma_pago_ref:
        # FASE1_POSTPAGO_V1_CANCEL: revertir sumando al saldo del Postpago
        from roles.models import Postpago
        pp = Postpago.objects.select_for_update().filter(
            cliente=boleta.usuario,
            gestor=boleta.destinatario,
            forma_pago=forma_pago_ref,
            activo=True,
        ).first()
        if pp:
            pp.saldo += monto_postpago
            if pp.saldo == 0:
                pp.activo = False
            pp.save(update_fields=['saldo', 'activo', 'actualizado_en'])
            detalle['postpago'] = monto_postpago
            reintegr_total += monto_postpago

    # ═══ FIX_CANCELAR_REVIERTE_PREMIOS_V1 ═══
    # Al cancelar boleta, revertir premios pagados del fondo del cliente
    premios_boleta = Premio.objects.filter(
        jugada__boleta=boleta, estado='pagado', cobrado=True,
    )
    for p_prem in premios_boleta:
        fp_premio = p_prem.jugada.forma_pago or forma_pago_ref
        if fp_premio:
            fondo_premio = Fondo.objects.select_for_update().filter(
                usuario=boleta.usuario, forma_pago=fp_premio, activo=True,
            ).first()
            if fondo_premio:
                saldo_antes_premio = fondo_premio.monto
                fondo_premio.monto -= p_prem.monto_premio
                fondo_premio.save(update_fields=['monto'])
                MovimientoFondo.objects.create(
                    emisor=None,
                    receptor=boleta.usuario,
                    forma_pago=fp_premio,
                    monto=-p_prem.monto_premio,
                    tipo='ajuste',
                    estado='confirmado',
                    motivo=f'Reversión premio #{p_prem.id} por cancelación boleta {boleta.referencia}',
                    saldo_antes=saldo_antes_premio,
                    saldo_despues=fondo_premio.monto,
                    datos_transferencia={
                        'premio_id': p_prem.id,
                        'jugada_id': p_prem.jugada_id,
                        'boleta_id': boleta.id,
                        'boleta_ref': str(boleta.referencia),
                        'cancelacion': True,
                        'motivo': motivo or '',
                    },
                )
        p_prem.estado = 'rechazado'
        p_prem.cobrado = False
        p_prem.save(update_fields=['estado', 'cobrado'])
    # ═══ FIN FIX_CANCELAR_REVIERTE_PREMIOS_V1 ═══

    for j in jugadas:
        j.estado = 'cancelada'
        j.save(update_fields=['estado', 'actualizado_en'])

    boleta.estado = 'cancelada'
    boleta.cancelada_en = timezone.now()
    boleta.cancelada_por = user
    boleta.motivo_cancelacion = motivo
    boleta.save(update_fields=[
        'estado', 'cancelada_en', 'cancelada_por',
        'motivo_cancelacion', 'actualizado_en',
    ])
    boleta.recalcular_totales()

    detalle['total'] = reintegr_total
    return True, detalle, None

# ═══════════════════════════════════════════════════════════════
# ACTUALIZACIÓN DINÁMICA DE RESULTADOS (Sin Tasks, sin Tarpit)
# ═══════════════════════════════════════════════════════════════
def _intentar_actualizar_loteria():
    archivo_lock = '/tmp/ultima_actualizacion_loteria.txt'
    necesita_actualizar = True

    # Candado de 5 minutos
    if os.path.exists(archivo_lock):
        ultima_mod = os.path.getmtime(archivo_lock)
        if timezone.now().timestamp() - ultima_mod < 300:
            necesita_actualizar = False

    if necesita_actualizar:
        with open(archivo_lock, 'w') as f:
            f.write(str(timezone.now()))

        def actualizar():
            try:
                call_command('load_results')
            except Exception as e:
                logger.error(f"Error en actualización dinámica: {e}")

        # Hilo en segundo plano para que la página cargue rápido
        threading.Thread(target=actualizar).start()

# ============================================================
# VISTAS
# ============================================================
@login_required
def superparlet(request):
    user = request.user
    es_superadmin = user.is_superuser or user.roles.filter(tipo='superadmin', activo=True).exists()
    es_banco = user.roles.filter(tipo='banco', activo=True).exists()
    es_comercial = user.roles.filter(tipo='comercial', activo=True).exists()
    es_autorizador = es_superadmin or es_banco or es_comercial

    # ← REFACTOR: una sola línea
    clientes = _construir_clientes_visibles(user)

    formas_pago = FormaPago.objects.filter(activo=True)
    sorteos_disponibles = _obtener_sorteos_cuba_estricto()
    if not (es_superadmin or es_banco):
        _aux = []
        for _s in sorteos_disponibles:
            _s2 = calcular_estado_sorteo(_s, timezone.now())
            if True:  # Filtro de 10 min desactivado
                _aux.append(_s)
        sorteos_disponibles = _aux

    if es_autorizador:
        total_fondos = 0
        total_bonos = 0
    else:
        total_fondos = Fondo.objects.filter(usuario=user, activo=True).aggregate(total=Sum('monto'))['total'] or 0
        bonos_activos = Bono.objects.filter(usuario=user, estado='activo')
        total_bonos = sum(b.saldo_restante for b in bonos_activos)

    context = {
        'clientes': clientes,
        'formas_pago': formas_pago,
        'sorteos': sorteos_disponibles,
        'es_autorizador': es_autorizador,
        'es_cliente': not es_autorizador,
        'es_superadmin': es_superadmin,
        'es_banco': es_banco,
        'es_comercial': es_comercial,
        'user': user,
        'hoy': timezone.now(),
        'saldo_total': float(total_fondos),
        'saldo_bonos': float(total_bonos),
        'rol': user.roles.filter(activo=True).first().tipo if user.roles.filter(activo=True).exists() else 'cliente',
    }
    return render(request, 'jugadas/superparlet.html', context)


@login_required
def apostar(request):
    user = request.user
    _intentar_actualizar_loteria() # <--- AGREGA ESTA LÍNEA AQUÍ
    # ═══════════════════════════════════════════════════════════════
    # BLOQUEO PARA AUDITORES: no pueden apostar, solo supervisar
    # ═══════════════════════════════════════════════════════════════
    if user.roles.filter(tipo='auditor', activo=True).exists():
        from django.contrib import messages
        from django.shortcuts import redirect
        messages.warning(request, "Los auditores no pueden realizar apuestas. Solo tienen permisos de supervisión.")
        return redirect('jugadas:mis_apuestas')

    if request.method != 'GET':
        return JsonResponse({'error': 'Método no permitido en esta URL'}, status=405)

    # FIX_APOSTAR_PRESELECT: params para preseleccion de cliente y aviso de recarga
    cliente_preseleccionado_id = request.GET.get('cliente_id', '').strip()
    recarga_ok = request.GET.get('recarga_ok', '').strip() == '1'

    edit_mode = 'edit' in request.GET
    jugada_id = request.GET.get('edit') or request.GET.get('duplicar')
    modo_edicion = ''
    if 'reasignar' in request.GET:
        modo_edicion = 'reasignar'
    elif 'cambiar_sorteo' in request.GET:
        modo_edicion = 'cambiar_sorteo'
    elif 'duplicar' in request.GET:
        modo_edicion = 'duplicar'

    edit_boleta_id = request.GET.get('edit_boleta')
    edit_boleta_data = None
    # Modo editar vs reenviar (viene por URL)
    es_modo_editar = request.GET.get('modo_editar') == '1'
    es_modo_reenviar = request.GET.get('modo_reenviar') == '1'

    if edit_boleta_id and edit_boleta_id.isdigit():
        try:
            b = Boleta.objects.get(id=int(edit_boleta_id))
            es_superadmin_x = user.is_superuser or user.roles.filter(tipo='superadmin', activo=True).exists()
            es_banco_x = user.roles.filter(tipo='banco', activo=True).exists()
            es_comercial_x = user.roles.filter(tipo='comercial', activo=True).exists()
            es_autorizador_x = es_superadmin_x or es_banco_x or es_comercial_x

            if b.usuario_id == user.id or b.destinatario_id == user.id or es_autorizador_x:
                lineas = []
                sorteo_ids_set = set()
                for j in b.jugadas.exclude(estado='cancelada'):
                    tipo = (j.forma_juego.nombre if j.forma_juego else '').lower()
                    # POSICION_PRELOAD_V1
                    _meta_orig = (j.metadata or {}).get('original', {}) or {}
                    lineas.append({
                        'tipo': tipo,
                        'numero': j.numero,
                        'monto': float(j.monto),
                        'sorteo_id': j.sorteo_id,
                        'posicion': _meta_orig.get('posicion'),
                    })
                    sorteo_ids_set.add(j.sorteo_id)

                edit_boleta_data = {
                    'boleta_id': b.id,
                    'referencia': b.referencia,
                    'cliente_id': b.usuario_id,
                    'cliente_nombre': (b.usuario.username if b.usuario else ''),
                    'destinatario_id': b.destinatario_id,
                    'forma_pago_id': b.forma_pago_id,
                    'fecha_sorteo': (
                        b.fecha_sorteo.strftime('%Y-%m-%d')
                        if b.fecha_sorteo else timezone.localdate().strftime('%Y-%m-%d')
                    ),
                    'lineas': lineas,
                    'sorteo_ids': list(sorteo_ids_set),
                }
        except Boleta.DoesNotExist:
            pass
        except Exception as e:
            logger.warning(f"No se pudo precargar boleta {edit_boleta_id}: {e}")

    es_superadmin = user.is_superuser or user.roles.filter(tipo='superadmin', activo=True).exists()
    es_banco = user.roles.filter(tipo='banco', activo=True).exists()
    es_comercial = user.roles.filter(tipo='comercial', activo=True).exists()
    es_autorizador = es_superadmin or es_banco or es_comercial
    es_gestor = es_comercial or es_banco

    # ═══ NUEVO: selector "Bajo cuenta de" ═══
    gestor_cuenta_id = (request.GET.get('gestor_cuenta') or '').strip()
    if gestor_cuenta_id and not gestor_cuenta_id.isdigit():
        gestor_cuenta_id = ''
    if gestor_cuenta_id and str(gestor_cuenta_id) == str(user.id):
        gestor_cuenta_id = ''

    clientes = _construir_clientes_visibles(user, gestor_cuenta_id=gestor_cuenta_id)

    gestor_cuenta_opciones = []
    if es_superadmin:
        # Grupo General
        gestor_cuenta_opciones.append({
            'grupo': 'General',
            'opciones': [{'id': '', 'label': 'Todos'}],
        })
        # Cada banco + sus comerciales
        for banco in User.objects.filter(
            roles__tipo='banco', roles__activo=True, is_active=True
        ).distinct().order_by('username'):
            gestor_cuenta_opciones.append({
                'grupo': f'Banco: {banco.username}',
                'opciones': [{'id': str(banco.id), 'label': banco.username}],
            })
            comerciales_qs = User.objects.filter(
                is_active=True,
                roles__tipo='comercial', roles__activo=True,
                jefes__jefe=banco, jefes__activo=True,
            ).distinct().order_by('username')
            comerciales_list = [{'id': str(u.id), 'label': u.username} for u in comerciales_qs]
            if comerciales_list:
                gestor_cuenta_opciones.append({
                    'grupo': f'Comerciales de {banco.username}',
                    'opciones': comerciales_list,
                })
    elif es_banco:
        gestor_cuenta_opciones.append({
            'grupo': 'Propio',
            'opciones': [{'id': '', 'label': f'Yo ({user.username})'}],
        })
        comerciales_qs = User.objects.filter(
            is_active=True,
            roles__tipo='comercial', roles__activo=True,
            jefes__jefe=user, jefes__activo=True,
        ).distinct().order_by('username')
        comerciales_list = [{'id': str(u.id), 'label': u.username} for u in comerciales_qs]
        if comerciales_list:
            gestor_cuenta_opciones.append({
                'grupo': 'Mis comerciales',
                'opciones': comerciales_list,
            })

    fecha_actual = timezone.localdate()
    sorteos_disponibles = _obtener_sorteos_cuba_estricto()
    if not (es_superadmin or es_banco):
        _aux = []
        for _s in sorteos_disponibles:
            _s2 = calcular_estado_sorteo(_s, timezone.now())
            if True:  # Filtro de 10 min desactivado
                _aux.append(_s)
        sorteos_disponibles = _aux

    formas_juego = FormaJuego.objects.filter(activo=True)
    formas_pago = FormaPago.objects.filter(activo=True)

    # ─── Formas de pago para recarga/postpago: TODAS las activas ───
    from pagos.utils import get_formas_pago_activas
    formas_pago_recarga = list(get_formas_pago_activas())

    if es_autorizador:
        total_fondos = 0
        total_bonos = 0
    else:
        total_fondos = Fondo.objects.filter(usuario=user, activo=True).aggregate(total=Sum('monto'))['total'] or 0
        bonos_activos = Bono.objects.filter(usuario=user, estado='activo')
        total_bonos = sum(b.saldo_restante for b in bonos_activos)

    context = {
        'sorteos': sorteos_disponibles,
        'formas_juego': formas_juego,
        'formas_pago': formas_pago,
        'formas_pago_recarga': formas_pago_recarga,
        'clientes': clientes,
        'gestor_cuenta_opciones': gestor_cuenta_opciones,
        'gestor_cuenta_seleccionado': gestor_cuenta_id,
        'es_autorizador': es_autorizador,
        'es_cliente': not es_autorizador,
        'es_superadmin': es_superadmin,
        'es_banco': es_banco,
        'es_comercial': es_comercial,
        'es_gestor': es_gestor,
        'saldo_total': float(total_fondos),
        'saldo_bonos': float(total_bonos),
        'rol': user.roles.filter(activo=True).first().tipo if user.roles.filter(activo=True).exists() else 'cliente',
        'user': user,
        'hoy': timezone.now(),
        'edit_mode': edit_mode,
        'jugada_id': jugada_id,
        'modo_edicion': modo_edicion,
        'edit_boleta_id': edit_boleta_id,
        'edit_boleta_data': edit_boleta_data,
        # FIX_APOSTAR_PRESELECT
        'cliente_preseleccionado_id': cliente_preseleccionado_id,
        'recarga_ok': recarga_ok,
        'es_modo_editar': es_modo_editar,
        'es_modo_reenviar': es_modo_reenviar,
    }
    return render(request, 'jugadas/apostar.html', context)


# ═══════════════════════════════════════════════════════════════
# Helper · ¿El banco aún puede insertar (dentro de 24h post-cierre)?
# ═══════════════════════════════════════════════════════════════
def _dentro_ventana_banco(estado_sorteo, ahora=None, horas=24):
    """
    Devuelve True si:
      - el sorteo tiene hora_cierre calculada, y
      - no han pasado más de `horas` desde ese cierre.
    Caso especial: si aún está abierto (hora_cierre futura) → True.
    """
    from datetime import timedelta
    if ahora is None:
        from django.utils import timezone as _tz
        ahora = _tz.now()
    hc = getattr(estado_sorteo, 'hora_cierre', None)
    if hc is None:
        return False
    # Si el cierre es futuro, obviamente puede
    if hc >= ahora:
        return True
    # Sino, verificar que no hayan pasado más de `horas` horas
    return (ahora - hc) <= timedelta(hours=horas)

# ═══════════════════════════════════════════════════════════════
# GUARD_POOL_BACKEND_V1
# Réplica server-side de _getPoolYConsumido (frontend) + endpoint
# api_disponible_por_numero. Agrupa items por (sorteo, forma, numero),
# suma montos, y compara contra (pool - consumido).
# ═══════════════════════════════════════════════════════════════
def _norm_nombre_forma(s):
    """Normaliza nombre: lowercase + sin acentos."""
    import unicodedata
    s = (s or '').lower().strip()
    s = unicodedata.normalize('NFD', s)
    return ''.join(c for c in s if unicodedata.category(c) != 'Mn')


def _validar_pool_items(gestor, fecha, forma_pago, items, excluir_jugada_ids=None):
    """Devuelve lista de errores (vacía si todo OK).
    Cada error: {sorteo_id, forma, numero, pedido, disponible, falta}.
    """
    from jugadas.models import Jugada, FormaJuego
    from sorteos.models import Sorteo
    from django.db.models import Sum

    excluir_jugada_ids = excluir_jugada_ids or []

    formas_map = {}
    for fj in FormaJuego.objects.filter(activo=True):
        formas_map[_norm_nombre_forma(fj.nombre)] = fj

    # Agrupar items por (sorteo_id, fj_id, numero) sumando montos
    grupos = {}
    for it in items:
        try:
            sid = int(it.get('sorteo_id') or 0)
        except (ValueError, TypeError):
            continue
        if not sid:
            continue
        tipo = _norm_nombre_forma(it.get('tipo', ''))
        fj = formas_map.get(tipo)
        if not fj:
            continue
        numero = str(it.get('numero', '')).strip().upper()
        if not numero:
            continue
        try:
            monto = float(it.get('monto', 0) or 0)
        except (ValueError, TypeError):
            monto = 0.0
        if monto <= 0:
            continue
        key = (sid, fj.id, numero)
        grupos[key] = grupos.get(key, 0.0) + monto

    if not grupos:
        return []

    pool_cache = {}
    def _pool(sorteo_id, fj):
        key = (sorteo_id, fj.id)
        if key not in pool_cache:
            try:
                sorteo = Sorteo.objects.get(id=sorteo_id)
                pool_cache[key] = float(get_pool_gestor(gestor, sorteo, fj, forma_pago))
            except Exception:
                pool_cache[key] = 0.0
        return pool_cache[key]

    errores = []
    for (sid, fj_id, numero), pedido in grupos.items():
        fj = FormaJuego.objects.filter(id=fj_id).first()
        if not fj:
            continue
        pool = _pool(sid, fj)
        if pool <= 0:
            continue  # sin pool configurado → no validar

        qs = Jugada.objects.filter(
            destinatario=gestor,
            sorteo_id=sid,
            forma_juego=fj,
            forma_pago=forma_pago,
            fecha_sorteo=fecha,
            numero=numero,
            estado__in=['confirmada', 'pendiente'],
        )
        if excluir_jugada_ids:
            qs = qs.exclude(id__in=excluir_jugada_ids)

        consumido = float(qs.aggregate(total=Sum('monto'))['total'] or 0)
        disponible = max(0.0, pool - consumido)

        if pedido > disponible + 0.001:
            errores.append({
                'sorteo_id': sid,
                'forma': fj.nombre,
                'numero': numero,
                'pedido': round(pedido, 2),
                'disponible': round(disponible, 2),
                'falta': round(pedido - disponible, 2),
            })

    return errores


def _log_400_apuesta(view_func):
    """FIX_LOG_400_V1 (2026-10-14): loguea cualquier JsonResponse 400 que
    devuelva el guardar-apuesta. Antes los 400 por validacion no dejaban
    rastro y hacia perder horas de diagnostico (caso Vany)."""
    def wrapper(request, *args, **kwargs):
        response = view_func(request, *args, **kwargs)
        try:
            if hasattr(response, 'status_code') and response.status_code == 400:
                import json as _json
                try:
                    data = _json.loads(response.content)
                    msg = data.get('message') or data.get('error') or ''
                except Exception:
                    msg = (response.content[:200] if hasattr(response, 'content') else '') or ''
                logger.warning(
                    '[guardar_apuesta 400] user=%s ip=%s msg=%r',
                    request.user.username if getattr(request, 'user', None) and request.user.is_authenticated else 'anon',
                    request.META.get('REMOTE_ADDR', '?'),
                    msg,
                )
        except Exception as _e:
            logger.error('[guardar_apuesta 400 log] %s', _e)
        return response
    return wrapper

@_log_400_apuesta
def _guardar_apuesta_impl(request):
    # ─── (cuerpo sin cambios, se mantiene tal cual lo tenías) ───
    try:
        carrito_data = request.POST.get('carrito_data')
        super_data = request.POST.get('superparlet_data')
        sorteos_str = request.POST.get('sorteos')
        super_sorteos_str = request.POST.get('superparlet_sorteos')
        fecha_sorteo = request.POST.get('fecha')
        cliente_id = request.POST.get('cliente_id')
        destinatario_id = request.POST.get('destinatario_id')
        forma_pago_id = request.POST.get('forma_pago')
        jugada_id = request.POST.get('jugada_id')
        modo_edicion = request.POST.get('modo_edicion', '')
        boleta_origen_id = request.POST.get('boleta_origen_id', '')

        if not fecha_sorteo:
            return JsonResponse({'success': False, 'message': 'La fecha de la apuesta es obligatoria.'}, status=400)

        try:
            fecha_apuesta = datetime.strptime(fecha_sorteo, '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({'success': False, 'message': 'Formato de fecha inválido. Use YYYY-MM-DD.'}, status=400)

        # ═══ FIX ZONA HORARIA CUBA (Para evitar que clientes de España envíen fecha de mañana) ═══
        CUBA_TZ = ZoneInfo('America/Havana')
        ahora_cuba = timezone.now().astimezone(CUBA_TZ)
        hoy = ahora_cuba.date()

        # Si la fecha enviada por el navegador es el día de hoy o mañana (por el desfase),
        # la forzamos a la fecha real de Cuba.
        # Definir si el usuario es admin (banco o superadmin)
        _es_admin_f = request.user.is_superuser or request.user.roles.filter(tipo__in=['banco', 'superadmin'], activo=True).exists()

        if not _es_admin_f and abs((fecha_apuesta - hoy).days) <= 1:
            fecha_apuesta = hoy
        # ══════════════════════════════════════════════════════════════════════════════════════

        limite_futuro = hoy + timedelta(days=365)  # FIX_FUTURO_1ANO_V1

        # FIX_FUTURO_1ANO_V1 + FIX_USUARIO_URGENTE_V1
        _u = request.user
        _es_admin_f = _u.is_superuser or _u.roles.filter(tipo__in=['superadmin','banco'], activo=True).exists()
        _sids_early = []
        try:
            _sstr = request.POST.get('sorteos', '[]')
            _sids_early = json.loads(_sstr) if _sstr else []
        except Exception:
            pass
        _georgia_late = False
        _now_cuba = timezone.now().astimezone(ZoneInfo('America/Havana'))
        if _now_cuba.hour == 0 and _now_cuba.minute < 25 and _sids_early:
            for _sid in _sids_early:
                if Sorteo.objects.filter(id=int(_sid), nombre='Georgia 11:34 PM').exists():
                    _georgia_late = True
                    if fecha_apuesta == hoy:
                        fecha_apuesta = hoy - timedelta(days=1)
                    break
        if fecha_apuesta < hoy and not _es_admin_f and not _georgia_late:
            return JsonResponse({'success': False, 'message': 'Los clientes y comerciales solo pueden apostar desde hoy en adelante.'}, status=400)
        if fecha_apuesta > limite_futuro:
            return JsonResponse({'success': False, 'message': 'La fecha de la apuesta no puede ser superior a 6 meses en el futuro.'}, status=400)

        if not cliente_id or not cliente_id.isdigit():
            return JsonResponse({'success': False, 'message': 'ID de cliente inválido'}, status=400)

        if not carrito_data and not super_data:
            return JsonResponse({'success': False, 'message': 'No hay jugadas'}, status=400)

        try:
            items_normales = json.loads(carrito_data) if carrito_data else []
            items_super = json.loads(super_data) if super_data else []
            sorteos_ids = json.loads(sorteos_str) if sorteos_str else []
            super_sorteos_ids = json.loads(super_sorteos_str) if super_sorteos_str else []
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            return JsonResponse({'success': False, 'message': f'Error en formato de datos: {str(e)}'}, status=400)

        # FIX_TRIPLETA_V1
        items_normales = _consolidar_tripletas(items_normales)
        items_super = _consolidar_tripletas(items_super)

        if not all(str(sid).isdigit() for sid in sorteos_ids):
            return JsonResponse({'success': False, 'message': 'IDs de sorteos inválidos'}, status=400)
        if not all(str(sid).isdigit() for sid in super_sorteos_ids):
            return JsonResponse({'success': False, 'message': 'IDs de sorteos para Superparlet inválidos'}, status=400)

        if items_normales and not sorteos_ids:
            return JsonResponse({'success': False, 'message': 'Selecciona al menos un sorteo'}, status=400)
        if items_super and (len(super_sorteos_ids) < 2 or not all(super_sorteos_ids)):
            return JsonResponse({'success': False, 'message': 'Superparlet requiere dos sorteos'}, status=400)

                # ═══ VALIDACIÓN ESTRICTA DE CIERRE (ZONA HORARIA CUBA) ═══
        # Excepción: bancos y superadmins pueden saltarse el cierre para cargar jugadas retroactivas
        _es_banco_o_super = (
            request.user.is_superuser
            or request.user.roles.filter(tipo__in=['superadmin','banco'], activo=True).exists()
        )
        if not _es_banco_o_super:
            try:
                CUBA_TZ = ZoneInfo('America/Havana')
                ahora_cuba = timezone.now().astimezone(CUBA_TZ)

                _todos_ids = list(set(list(sorteos_ids) + list(super_sorteos_ids)))
                _cerrados = []

                for _sid in _todos_ids:
                    _sorteo_chk = Sorteo.objects.filter(id=int(_sid)).first()
                    if not _sorteo_chk: continue

                    temp_chk = 'verano' if es_verano_cuba(fecha_apuesta) else 'invierno'
                    dia_chk = {0: 'lunes', 1: 'martes', 2: 'miercoles', 3: 'jueves', 4: 'viernes', 5: 'sabado', 6: 'domingo'}[fecha_apuesta.weekday()]

                    hs_chk = _sorteo_chk.hora_salida
                    if _sorteo_chk.horarios and temp_chk in _sorteo_chk.horarios and dia_chk in _sorteo_chk.horarios[temp_chk]:
                        hh, mm = _sorteo_chk.horarios[temp_chk][dia_chk].split(':')
                        hs_chk = time(int(hh), int(mm))

                    dt_sal = datetime.combine(fecha_apuesta, hs_chk).replace(tzinfo=CUBA_TZ)

                    if hs_chk.hour < 6:
                        dt_sal += timedelta(days=1)

                    dt_cie = dt_sal - timedelta(minutes=(_sorteo_chk.minutos_cierre or 60))

                    if ahora_cuba >= dt_cie:
                        _cerrados.append(_sorteo_chk.nombre)

                if _cerrados:
                    return JsonResponse({
                        'success': False,
                        'sorteo_cerrado': True,
                        'sorteos_cerrados': _cerrados,
                        'message': '⛔ Operación rechazada. El sorteo ya cerró en Cuba: ' + ', '.join(_cerrados),
                    }, status=400)
            except Exception as e:
                logger.error(f"Error validando cierre estricto: {e}")
        # ═══ FIN VALIDACIÓN ESTRICTA ═══

        usuario = request.user
        try:
            cliente = User.objects.get(id=int(cliente_id))
        except (User.DoesNotExist, ValueError) as e:
            logger.error(f"Cliente no encontrado: {e}")
            return JsonResponse({'success': False, 'message': 'Cliente no encontrado'}, status=404)

        # FIX_CLIENTE_SIN_DEUDA_V2: si el usuario es cliente autenticado, debe tener forma_pago
        _es_cliente_puro = (
            not usuario.is_superuser
            and not usuario.roles.filter(tipo__in=['superadmin', 'banco', 'comercial'], activo=True).exists()
            and usuario.roles.filter(tipo='cliente', activo=True).exists()
        )
        if _es_cliente_puro and (not forma_pago_id or not str(forma_pago_id).isdigit()):
            return JsonResponse({
                'success': False,
                'message': 'Los clientes no pueden apostar en deuda o bono. Elige una forma de pago con saldo.'
            }, status=400)

        forma_pago = None
        if forma_pago_id and forma_pago_id.isdigit():
            try:
                forma_pago = FormaPago.objects.get(id=int(forma_pago_id))
            except FormaPago.DoesNotExist as e:
                logger.error(f"Forma de pago no encontrada: {e}")
                return JsonResponse({'success': False, 'message': 'Forma de pago no válida'}, status=400)
        elif forma_pago_id and not forma_pago_id.isdigit():
            return JsonResponse({'success': False, 'message': 'ID de forma de pago inválido'}, status=400)

        sorteos_obj = Sorteo.objects.filter(id__in=sorteos_ids)
        if items_normales and len(sorteos_obj) != len(sorteos_ids):
            return JsonResponse({'success': False, 'message': 'Algunos sorteos no existen'}, status=404)

        super_sorteos_obj = Sorteo.objects.filter(id__in=super_sorteos_ids)
        if items_super and len(super_sorteos_obj) != 2:
            return JsonResponse({'success': False, 'message': 'Sorteos para Superparlet no válidos'}, status=404)

        if items_normales:
            try:
                from django.apps import apps
                NumeroRestringidoModel = apps.get_model('roles', 'NumeroRestringido')
                numeros_apostados = []
                for item in items_normales:
                    numero = item.get('numero', '').strip()
                    if numero:
                        if 'x' in numero:
                            for p in numero.split('x'):
                                numeros_apostados.append(p)
                        else:
                            numeros_apostados.append(numero)
                numeros_apostados = list(set(numeros_apostados))

                if numeros_apostados:
                    for sorteo_id in sorteos_ids:
                        sorteo = Sorteo.objects.get(id=sorteo_id)
                        restringidos = NumeroRestringidoModel.objects.filter(
                            sorteo=sorteo, valor__in=numeros_apostados
                        ).values_list('valor', flat=True)
                        if restringidos:
                            return JsonResponse({
                                'success': False,
                                'message': f'⛔ Números restringidos para "{sorteo.nombre}": {", ".join(restringidos)}.'
                            }, status=400)
            except Exception as e:
                logger.warning(f"Validación de números restringidos omitida: {e}")

        # FIX_RELAJAR_FONDO_V1: banco/comercial/superadmin pueden apostar
        # si el cliente tiene CUALQUIER relación con el gestor (Fondo, Postpago
        # o Subordinación). Si no hay Fondo, la deuda se acumula en Postpago.
        def _tiene_relacion_gestor(_cliente, _gestor):
            if Fondo.objects.filter(usuario=_cliente, asignado_por=_gestor, activo=True).exists():
                return True
            try:
                from roles.models import Postpago as _PP
                if _PP.objects.filter(cliente=_cliente, gestor=_gestor, activo=True).exists():
                    return True
            except Exception:
                pass
            if Subordinacion.objects.filter(subordinado=_cliente, jefe=_gestor, activo=True).exists():
                return True
            return False

        destinatario = None

        if destinatario_id and str(destinatario_id).isdigit():
            try:
                destinatario = User.objects.get(id=int(destinatario_id))
            except User.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'message': 'Gestor (destinatario) no encontrado.'
                }, status=404)

            es_superadmin = usuario.is_superuser or usuario.roles.filter(tipo='superadmin', activo=True).exists()
            es_banco = usuario.roles.filter(tipo='banco', activo=True).exists()
            es_comercial = usuario.roles.filter(tipo='comercial', activo=True).exists()

            if es_superadmin:
                pass
            elif (es_banco or es_comercial) and destinatario.id == usuario.id:
                # FIX_RELAJAR_FONDO_V1: permitir si hay relacion con Postpago o Subordinacion
                if not _tiene_relacion_gestor(cliente, usuario):
                    return JsonResponse({
                        'success': False,
                        'message': 'No tienes relacion asignada con este cliente (fondo, postpago o subordinacion).'
                    }, status=400)
            else:
                # FIX_GUARDAR_COMERCIAL_V1 + FIX_RELAJAR_FONDO_V1
                if not _tiene_relacion_gestor(cliente, destinatario):
                    return JsonResponse({
                        'success': False,
                        'message': f'El cliente no tiene relacion con {destinatario.username} (fondo, postpago o subordinacion).'
                    }, status=400)
        else:
            if usuario.is_superuser or usuario.roles.filter(tipo__in=['banco', 'comercial'], activo=True).exists():
                destinatario = usuario
                if not usuario.is_superuser:
                    # FIX_RELAJAR_FONDO_V1
                    if not _tiene_relacion_gestor(cliente, usuario):
                        return JsonResponse({
                            'success': False,
                            'message': 'No tienes relacion asignada con este cliente (fondo, postpago o subordinacion).'
                        }, status=400)
            else:
                sub = Subordinacion.objects.filter(subordinado=cliente, activo=True).first()
                if sub:
                    destinatario = sub.jefe
                else:
                    fondo = Fondo.objects.filter(usuario=cliente, forma_pago=forma_pago, activo=True).first()
                    if fondo and fondo.asignado_por:
                        destinatario = fondo.asignado_por
                    else:
                        return JsonResponse({
                            'success': False,
                            'message': 'El cliente no tiene gestor asignado para esta forma de pago.'
                        }, status=400)

        if not destinatario:
            return JsonResponse({'success': False, 'message': 'No se encontró un gestor para este cliente.'}, status=400)

        es_edicion_pura = bool(jugada_id) and modo_edicion not in ('duplicar', 'editar_boleta')
        es_edicion_boleta = (
            modo_edicion == 'editar_boleta'
            and boleta_origen_id and boleta_origen_id.isdigit()
        )

        # Validar suma igual si modo_operacion == 'editar'
        modo_operacion = request.POST.get('modo_operacion', '')

        es_solo_editar = (es_edicion_boleta and modo_operacion == 'editar')
        es_banco_o_admin_edit = usuario.is_superuser or usuario.roles.filter(tipo__in=['superadmin', 'banco'], activo=True).exists()
        if es_edicion_boleta and modo_operacion == 'editar' and not es_banco_o_admin_edit:
            try:
                orig_b = Boleta.objects.get(id=int(boleta_origen_id))
                suma_orig = sum((j.monto for j in orig_b.jugadas.exclude(estado='cancelada')), Decimal('0.00'))
                suma_nueva = sum((Decimal(str(it.get('monto', 0))) for it in (items_normales + items_super)), Decimal('0.00'))
                if abs(suma_nueva - suma_orig) > Decimal('0.01'):
                    return JsonResponse({
                        'success': False,
                        'message': 'Modo Editar: la suma debe ser igual. Original: $' + str(suma_orig) + ', Nueva: $' + str(suma_nueva) + '. Usa Reenviar para cambiar el total.'
                    }, status=400)
            except Boleta.DoesNotExist:
                pass

        # ════ Check de BOLETA DUPLICADA — ANTES de crear cualquier jugada ════
        if not es_edicion_boleta and not es_edicion_pura and forma_pago and cliente:
            try:
                _items_check = []
                for _it in (items_normales + items_super):
                    _sid = _it.get('sorteo_id')
                    if not _sid:
                        continue
                    _items_check.append({
                        'sorteo_id': int(_sid),
                        'tipo': (_it.get('tipo') or '').strip().lower(),
                        'numero': _it.get('numero') or '',
                        'monto': _it.get('monto') or 0,
                    })
                if _items_check:
                    _dups_pre = _boleta_duplicada(cliente.id, forma_pago.id, fecha_apuesta, _items_check)
                    if _dups_pre:
                        _refs = ', '.join([d.get('boleta_ref', '?') for d in _dups_pre])
                        return JsonResponse({
                            'success': False,
                            'message': '⚠️ Ya existe una boleta identica para este cliente/sorteo/fecha/forma de pago (' + _refs + '). Modifica numeros, montos o forma de pago para continuar.',
                            'advertencias': ['Duplicado con: ' + _refs],
                        }, status=400)
            except Exception as _e:
                logger.warning('[dup check pre] ERROR: ' + str(_e))

        # ═══ GUARD_POOL_BACKEND_V1 ═══
        try:
            if items_normales and destinatario and forma_pago:
                _excluir_jugada_ids = []
                if es_edicion_pura and jugada_id and str(jugada_id).isdigit():
                    _excluir_jugada_ids.append(int(jugada_id))
                _errores_pool = _validar_pool_items(
                    gestor=destinatario,
                    fecha=fecha_apuesta,
                    forma_pago=forma_pago,
                    items=items_normales,
                    excluir_jugada_ids=_excluir_jugada_ids,
                )
                if _errores_pool:
                    _msg = '\u26d4 ' + str(len(_errores_pool)) + ' jugada(s) exceden el disponible del gestor'
                    _detalle = ' \u00b7 '.join([
                        e['forma'] + ' ' + e['numero'] + ' (falta $' + str(e['falta']) + ')'
                        for e in _errores_pool[:5]
                    ])
                    return JsonResponse({
                        'success': False,
                        'message': _msg,
                        'detalle': _detalle,
                        'errores': _errores_pool,
                    }, status=400)
        except Exception as _ePool:
            # Fail-open: si la validación falla por bug interno,
            # permitimos pasar pero dejamos rastro en logs.
            import traceback as _tb; logger.warning('[GUARD_POOL_BACKEND_V1] error interno: ' + str(_ePool) + '\n' + _tb.format_exc())
        # ═══ FIN GUARD_POOL_BACKEND_V1 ═══

        with transaction.atomic():

            # Asegurar que 'boleta' este siempre definida
            boleta = None

            if es_edicion_boleta:
                orig = Boleta.objects.select_for_update().filter(id=int(boleta_origen_id)).first()
                if not orig:
                    raise ValueError('Boleta original no encontrada')
                if orig.estado != 'activa':
                    raise ValueError(f'La boleta original está en estado {orig.estado}, no se puede editar')

                if es_solo_editar:
                    # FIX_REENVIAR_Y_BANCO_EDIT_V1: Revertir premios antes de borrar
                    premios_ant = Premio.objects.filter(jugada__boleta=orig, estado='pagado', cobrado=True)
                    for p in premios_ant:
                        f = Fondo.objects.filter(usuario=orig.usuario, forma_pago=p.jugada.forma_pago).first()
                        if f:
                            f.monto -= p.monto_premio
                            f.save(update_fields=['monto'])
                        p.estado = 'anulado'
                        p.cobrado = False
                        p.save(update_fields=['estado', 'cobrado'])
                    orig.jugadas.all().delete()
                    orig.forma_pago = forma_pago
                    orig.fecha_sorteo = fecha_apuesta
                    orig.save(update_fields=['forma_pago', 'fecha_sorteo', 'actualizado_en'])
                    boleta = orig
                else:
                    # FIX_REENVIAR_Y_BANCO_EDIT_V1: Reenviar NO cancela la original.
                    boleta = Boleta.objects.create(
                        usuario=cliente,
                        destinatario=destinatario,
                        comercial=usuario if usuario != cliente else None,
                        creado_por=usuario,
                        forma_pago=forma_pago,
                        fecha_sorteo=fecha_apuesta,
                        metadata={
                            'origen': 'reenviar',
                            'modo': 'reenviar',
                            'boleta_origen_id': int(boleta_origen_id),
                        },
                    )

            # FIX_1_BOLETA_POR_SORTEO_V1: preparar diccionarios de boletas
            # (se crearán bajo demanda en el loop para no dejar boletas huérfanas)
            boletas_por_sorteo = {}   # {sorteo_id: Boleta}
            boletas_super = []        # [Boleta] - 1 por cada superparlet

            if not es_edicion_pura and boleta is None:
                # Nueva apuesta: NO crear boleta aquí. Se creará por sorteo.
                pass

            jugadas_creadas = []
            total_apostado = Decimal('0.00')
            advertencias = []
            consumo_memoria = defaultdict(Decimal)

            tipo_a_forma = {}
            for item in items_normales + items_super:
                nombre_tipo = item.get('tipo', '').strip()
                if not nombre_tipo:
                    return JsonResponse({'success': False, 'message': 'Tipo de juego vacío'}, status=400)
                if nombre_tipo not in tipo_a_forma:
                    # Buscar con case-insensitive para evitar crear duplicados 'Fijo'/'fijo'
                    forma = FormaJuego.objects.filter(nombre__iexact=nombre_tipo).first()
                    if not forma:
                        forma = FormaJuego.objects.create(nombre=nombre_tipo.lower(), digitos_esperados=2, activo=True)
                    tipo_a_forma[nombre_tipo] = forma

            for item in items_normales:
                # FIX_STRIP_TIPO_V1: aplicar strip para coincidir con la clave del dict
                _tipo_key = (item.get('tipo') or '').strip()
                forma_juego = tipo_a_forma.get(_tipo_key) or tipo_a_forma.get(item.get('tipo'))
                if not forma_juego:
                    logger.warning(f'[DEBUG_APUESTA] item SKIP: forma_juego no encontrada para tipo={item.get("tipo")!r} (strip={_tipo_key!r}, keys_disponibles={list(tipo_a_forma.keys())})')
                    continue
                numero = item.get('numero', '').strip()
                if not numero:
                    continue
                try:
                    monto = Decimal(str(item.get('monto', 0)))
                except Exception:
                    continue

                sorteo_item_id = item.get('sorteo_id')
                if sorteo_item_id:
                    sorteos_iter = [s for s in sorteos_obj if s.id == int(sorteo_item_id)]
                else:
                    sorteos_iter = list(sorteos_obj)

                for sorteo in sorteos_iter:
                    formas_sorteo = [f.lower() for f in (sorteo.formas_juego or [])]
                    if item.get('tipo', '').lower() not in formas_sorteo:
                        continue

                    estado_sorteo = calcular_estado_sorteo(sorteo, timezone.now(), fecha_apuesta)
                    esta_abierto = getattr(estado_sorteo, 'estado_actual', 'cerrado') == 'abierto'

                    if not esta_abierto:
                        es_superadmin_ = usuario.is_superuser or usuario.roles.filter(tipo='superadmin', activo=True).exists()
                        es_banco_ = usuario.roles.filter(tipo='banco', activo=True).exists()
                        # FIX_VENTANA_BANCO_V2 (2026-10-14):
                        # - superadmin y banco: pueden cargar fuera de tiempo sin limite.
                        # - resto: bloqueado.
                        permitido = es_superadmin_ or es_banco_
                        if not permitido:
                            advertencias.append(
                                f'El sorteo "{sorteo.nombre}" está cerrado. Solo banco y superadmin pueden cargar jugadas fuera de tiempo.'
                            )
                            continue

                    pool_total = get_pool_gestor(destinatario, sorteo, forma_juego, forma_pago)
                    if pool_total <= 0:
                        advertencias.append(f'Sin pool configurado para {sorteo.nombre} - {forma_juego.nombre} - {forma_pago.nombre}.')
                        continue

                    key_mem = (sorteo.id, forma_juego.id, getattr(forma_pago, 'id', 0), numero)  # FIX_FORMA_PAGO_NONE_V1
                    consumido_db = Jugada.objects.filter(
                        destinatario=destinatario, sorteo=sorteo, forma_juego=forma_juego,
                        forma_pago=forma_pago, fecha_sorteo=fecha_apuesta, numero=numero,
                        estado__in=['confirmada', 'pendiente']
                    ).aggregate(total=Sum('monto'))['total'] or Decimal('0')

                    consumido = consumido_db + consumo_memoria[key_mem]
                    disponible = pool_total - consumido

                    if disponible <= 0:
                        advertencias.append(f'El número {numero} en {sorteo.nombre} - {forma_juego.nombre} está agotado para el gestor.')
                        continue

                    monto_final = monto
                    if monto > disponible:
                        advertencias.append(
                            f'El número {numero} en {sorteo.nombre} - {forma_juego.nombre} solo admitía ${disponible:.2f}. Se ajustó a ${disponible:.2f}.'
                        )
                        monto_final = disponible

                    if jugada_id and modo_edicion not in ('duplicar', 'editar_boleta'):
                        try:
                            jugada = Jugada.objects.get(id=jugada_id)
                            jugada.usuario = cliente
                            jugada.destinatario = destinatario
                            jugada.comercial = usuario if usuario != cliente else None
                            jugada.forma_juego = forma_juego
                            jugada.sorteo = sorteo
                            jugada.forma_pago = forma_pago
                            jugada.numero = numero
                            jugada.monto = monto_final
                            jugada.fecha_sorteo = fecha_apuesta
                            jugada.fecha = timezone.now()
                            jugada.estado = 'confirmada'
                            jugada.metadata = {'original': item, 'editado': True, 'editado_por': usuario.username}
                            jugada.save()
                            jugadas_creadas.append(jugada)
                            total_apostado += monto_final
                            consumo_memoria[key_mem] += monto_final
                            continue
                        except Jugada.DoesNotExist:
                            pass

                    # FIX_1_BOLETA_POR_SORTEO_V1: obtener/crear boleta para este sorteo
                    if boleta is not None:
                        boleta_de_esta_jugada = boleta
                    else:
                        if sorteo.id not in boletas_por_sorteo:
                            boletas_por_sorteo[sorteo.id] = Boleta.objects.create(
                                usuario=cliente,
                                destinatario=destinatario,
                                comercial=usuario if usuario != cliente else None,
                                creado_por=usuario,
                                forma_pago=forma_pago,
                                fecha_sorteo=fecha_apuesta,
                                metadata={
                                    'origen': 'guardar_apuesta',
                                    'tipo': 'normal',
                                    'sorteo_id': sorteo.id,
                                    'sorteo_nombre': sorteo.nombre,
                                },
                            )
                        boleta_de_esta_jugada = boletas_por_sorteo[sorteo.id]

                    jugada = Jugada(
                        usuario=cliente, destinatario=destinatario,
                        comercial=usuario if usuario != cliente else None,
                        forma_juego=forma_juego, sorteo=sorteo, forma_pago=forma_pago,
                        boleta=boleta_de_esta_jugada,
                        numero=numero, monto=monto_final, fecha_sorteo=fecha_apuesta,
                        fecha=timezone.now(), estado='confirmada',
                        metadata={'original': item, 'duplicado': True} if modo_edicion == 'duplicar' else {'original': item}
                    )
                    jugada.save()
                    jugadas_creadas.append(jugada)
                    total_apostado += monto_final
                    consumo_memoria[key_mem] += monto_final

            super_sorteos_list = list(super_sorteos_obj)
            if items_super and len(super_sorteos_list) != 2:
                advertencias.append('Superparlet requiere exactamente 2 sorteos.')
            elif items_super:
                sorteo_principal = super_sorteos_list[0]
                sorteo_ids_meta = [s.id for s in super_sorteos_list]

                for item in items_super:
                    forma_juego = tipo_a_forma.get('superparlet')
                    if not forma_juego:
                        forma_juego, _ = FormaJuego.objects.get_or_create(
                            nombre='superparlet', defaults={'digitos_esperados': 2, 'activo': True}
                        )
                        tipo_a_forma['superparlet'] = forma_juego

                    numero = item.get('numero', '').strip()
                    if not numero:
                        continue
                    try:
                        monto = Decimal(str(item.get('monto', 0)))
                    except Exception:
                        continue

                    # FIX_SUPER_AMBOS_ABIERTOS_V1: verificar AMBOS sorteos, no solo el principal
                    es_superadmin_ = usuario.is_superuser or usuario.roles.filter(tipo='superadmin', activo=True).exists()
                    es_banco_ = usuario.roles.filter(tipo='banco', activo=True).exists()
                    permitido_todos = True
                    for _sorteo_chk in super_sorteos_list:
                        _estado_chk = calcular_estado_sorteo(_sorteo_chk, timezone.now(), fecha_apuesta)
                        _abierto_chk = getattr(_estado_chk, 'estado_actual', 'cerrado') == 'abierto'
                        if not _abierto_chk:
                            _permitido = False
                            if es_superadmin_:
                                _permitido = True
                            elif es_banco_:
                                _permitido = True
                            if not _permitido:
                                advertencias.append(
                                    f'SuperParlet cancelado: el sorteo "{_sorteo_chk.nombre}" no está abierto. Ambos sorteos deben estar abiertos para apostar.'
                                )
                                permitido_todos = False
                                break
                    if not permitido_todos:
                        continue
                    pool_total = get_pool_gestor(destinatario, sorteo_principal, forma_juego, forma_pago)
                    if pool_total <= 0:
                        advertencias.append(f'Sin pool configurado para Superparlet - {forma_pago.nombre}.')
                        continue

                    key_mem = (sorteo_principal.id, forma_juego.id, getattr(forma_pago, 'id', 0), numero)  # FIX_FORMA_PAGO_NONE_V1
                    consumido_db = Jugada.objects.filter(
                        destinatario=destinatario, sorteo=sorteo_principal, forma_juego=forma_juego,
                        forma_pago=forma_pago, fecha_sorteo=fecha_apuesta, numero=numero,
                        estado__in=['confirmada', 'pendiente']
                    ).aggregate(total=Sum('monto'))['total'] or Decimal('0')

                    consumido = consumido_db + consumo_memoria[key_mem]
                    disponible = pool_total - consumido

                    if disponible <= 0:
                        advertencias.append(f'El número {numero} en Superparlet está agotado.')
                        continue

                    monto_final = monto
                    if monto > disponible:
                        advertencias.append(
                            f'El número {numero} en Superparlet solo admitía ${disponible:.2f}. Se ajustó a ${disponible:.2f}.'
                        )
                        monto_final = disponible
                    if jugada_id and modo_edicion not in ('duplicar', 'editar_boleta'):
                        try:
                            jugada = Jugada.objects.get(id=jugada_id)
                            jugada.usuario = cliente
                            jugada.destinatario = destinatario
                            jugada.comercial = usuario if usuario != cliente else None
                            jugada.forma_juego = forma_juego
                            jugada.sorteo = sorteo_principal
                            jugada.forma_pago = forma_pago
                            jugada.numero = numero
                            jugada.monto = monto_final
                            jugada.fecha_sorteo = fecha_apuesta
                            jugada.fecha = timezone.now()
                            jugada.estado = 'confirmada'
                            jugada.metadata = {
                                'superparlet': True,
                                'sorteos': sorteo_ids_meta,
                                'editado': True,
                                'editado_por': usuario.username
                            }
                            jugada.save()
                            jugadas_creadas.append(jugada)
                            total_apostado += monto_final
                            consumo_memoria[key_mem] += monto_final
                            continue
                        except Jugada.DoesNotExist:
                            pass

                    # FIX_1_BOLETA_POR_SORTEO_V1: superparlet → boleta única por jugada
                    if boleta is not None:
                        boleta_de_esta_jugada = boleta
                    else:
                        boleta_de_esta_jugada = Boleta.objects.create(
                            usuario=cliente,
                            destinatario=destinatario,
                            comercial=usuario if usuario != cliente else None,
                            creado_por=usuario,
                            forma_pago=forma_pago,
                            fecha_sorteo=fecha_apuesta,
                            metadata={
                                'origen': 'guardar_apuesta',
                                'tipo': 'superparlet',
                                'sorteos': sorteo_ids_meta,
                            },
                        )
                        boletas_super.append(boleta_de_esta_jugada)

                    jugada = Jugada(
                        usuario=cliente, destinatario=destinatario,
                        comercial=usuario if usuario != cliente else None,
                        forma_juego=forma_juego,
                        sorteo=sorteo_principal,
                        forma_pago=forma_pago,
                        boleta=boleta_de_esta_jugada,
                        numero=numero, monto=monto_final, fecha_sorteo=fecha_apuesta,
                        fecha=timezone.now(), estado='confirmada',
                        metadata={
                            'superparlet': True,
                            'sorteos': sorteo_ids_meta,
                            'duplicado': (modo_edicion == 'duplicar')
                        }
                    )
                    jugada.save()
                    jugadas_creadas.append(jugada)
                    total_apostado += monto_final
                    consumo_memoria[key_mem] += monto_final

            if not jugadas_creadas:
                # Determinar la causa principal
                hay_duplicados = any('ya existe' in adv for adv in advertencias)
                if hay_duplicados:
                    msg = '⚠️ Todas las jugadas ya existen en la base de datos para este cliente/sorteo/fecha. Modifica los números, montos o forma de pago.'
                else:
                    msg = 'No se pudo crear ninguna jugada (todos los números están agotados o sin pool).'
                return JsonResponse({
                    'success': False,
                    'message': msg,
                    'advertencias': advertencias
                }, status=400)

            # FIX_1_BOLETA_POR_SORTEO_V1: cleanup de boletas huérfanas + ref consolidada
            _todas_boletas_nuevas = list(boletas_por_sorteo.values()) + boletas_super
            # Eliminar boletas que no tienen jugadas (sorteos sin pool, etc.)
            for _b in list(_todas_boletas_nuevas):
                if not _b.jugadas.exists():
                    _b.delete()
                    if _b in boletas_super:
                        boletas_super.remove(_b)
                    else:
                        for _sid, _b2 in list(boletas_por_sorteo.items()):
                            if _b2.id == _b.id:
                                del boletas_por_sorteo[_sid]
                                break
            _todas_boletas_nuevas = list(boletas_por_sorteo.values()) + boletas_super

            # Referencia consolidada para MovimientoFondo
            if boleta is not None:
                ref_boleta = boleta.referencia
            elif _todas_boletas_nuevas:
                _refs = [b.referencia for b in _todas_boletas_nuevas]
                ref_boleta = _refs[0] if len(_refs) == 1 else _refs[0] + f' (+{len(_refs)-1} más)'
            else:
                ref_boleta = f"#{jugadas_creadas[0].id}"
            monto_fondo_consumido = Decimal('0.00')
            monto_bono_consumido = Decimal('0.00')
            monto_postpago_consumido = Decimal('0.00')

            # En modo editar NO se recobra (el dinero ya esta pagado)

            if (not es_solo_editar) and forma_pago and total_apostado > 0:

                monto_restante = total_apostado

                fondo = Fondo.objects.filter(
                    usuario=cliente, forma_pago=forma_pago, asignado_por=destinatario, activo=True
                ).first()

                # FIX_BONO_FUSION_V1: si el fondo no cubre la apuesta,
                # fusionar TODOS los bonos activos al fondo antes de gastar.
                if fondo and fondo.monto < monto_restante:
                    from django.utils import timezone as _tz_bf
                    from django.db.models import Q as _Q_bf, F as _F_bf
                    _bonos_fusion = list(Bono.objects.filter(
                        usuario=cliente,
                        asignado_por=destinatario,
                        estado='activo',
                        saldo_restante__gt=0,
                    ).filter(
                        _Q_bf(fecha_vencimiento__isnull=True) |
                        _Q_bf(fecha_vencimiento__gte=_tz_bf.now())
                    ))
                    _fusion_total = Decimal('0.00')
                    for _b in _bonos_fusion:
                        _fusion_total += _b.saldo_restante
                        _b.saldo_restante = Decimal('0.00')
                        _b.estado = 'agotado'
                        _b.save(update_fields=['saldo_restante', 'estado'])
                    if _fusion_total > 0:
                        fondo.monto += _fusion_total
                        fondo.save(update_fields=['monto'])

                if fondo:
                    if fondo.monto >= monto_restante:
                        monto_fondo_consumido = monto_restante
                        fondo.monto -= monto_restante
                        fondo.save()
                        monto_restante = Decimal('0.00')
                        MovimientoFondo.objects.create(
                            emisor=cliente, receptor=destinatario, forma_pago=forma_pago,
                            monto=total_apostado, tipo='apuesta', estado='confirmado',
                            motivo=f"Apuesta {ref_boleta}",
                            datos_transferencia={
                                'referencia': str(ref_boleta),
                                'usuario': usuario.username,
                                'tipo_operacion': 'apuesta',
                            },
                            nota=f"Apuesta realizada por {usuario.username}",
                            saldo_antes=fondo.monto + monto_restante,
                            saldo_despues=fondo.monto,
                        )
                    else:
                        monto_fondo_consumido = fondo.monto
                        monto_descontado = fondo.monto
                        fondo.monto = Decimal('0.00')
                        fondo.save()
                        monto_restante -= monto_descontado
                        MovimientoFondo.objects.create(
                            emisor=cliente, receptor=destinatario, forma_pago=forma_pago,
                            monto=monto_descontado, tipo='apuesta', estado='confirmado',
                            motivo=f"Apuesta parcial {ref_boleta}",
                            datos_transferencia={
                                'referencia': str(ref_boleta),
                                'usuario': usuario.username,
                                'tipo_operacion': 'apuesta_parcial',
                            },
                            nota=f"Apuesta parcial por {usuario.username}",
                            saldo_antes=monto_descontado,
                            saldo_despues=Decimal('0.00'),
                        )

                if monto_restante > 0:
                    # FIX_FIFO_BONOS_V2: filtro de vencidos + orden por vencimiento
                    from django.utils import timezone as _tz_fifo
                    from django.db.models import Q as _Q_fifo, F as _F_fifo
                    bonos_activos = Bono.objects.filter(
                        usuario=cliente,
                        asignado_por=destinatario,
                        estado='activo',
                        saldo_restante__gt=0,
                    ).filter(
                        _Q_fifo(fecha_vencimiento__isnull=True) |
                        _Q_fifo(fecha_vencimiento__gte=_tz_fifo.now())
                    ).order_by(
                        _F_fifo('fecha_vencimiento').asc(nulls_last=True),
                        'creado_en'
                    )
                    for bono in bonos_activos:
                        if monto_restante <= 0:
                            break
                        if bono.saldo_restante >= monto_restante:
                            monto_bono_consumido += monto_restante
                            bono.saldo_restante -= monto_restante
                            bono.save(update_fields=['saldo_restante'])
                            monto_restante = Decimal('0.00')
                        else:
                            monto_bono_consumido += bono.saldo_restante
                            monto_restante -= bono.saldo_restante
                            bono.saldo_restante = Decimal('0.00')
                            bono.estado = 'agotado'
                            bono.save(update_fields=['saldo_restante', 'estado'])

                if monto_restante > 0:
                    # FASE1_POSTPAGO_V1_GUARDAR: al exceder el fondo,
                    # acumular el excedente en el Postpago de esa FP.
                    from roles.models import Postpago
                    pp, _created = Postpago.objects.select_for_update().get_or_create(
                        cliente=cliente,
                        gestor=destinatario,
                        forma_pago=forma_pago,
                        defaults={'saldo': Decimal('0.00'), 'activo': True},
                    )
                    pp.saldo -= monto_restante
                    # FASE1_POSTPAGO_V1: reactivar si vuelve a haber deuda
                    if pp.saldo < 0:
                        pp.activo = True
                    pp.save(update_fields=['saldo', 'activo', 'actualizado_en'])
                    monto_postpago_consumido = monto_restante
                    # El resto se cubre con el postpago (queda como deuda)
                    monto_restante = Decimal('0.00')

            # FASE1_RECONCILIACION_V1_HOOK: si el resultado ya salió,
            # crear premios para jugadas ganadoras insertadas tardíamente.
            try:
                from resultados.reconciliacion import reconciliar_premio_jugada
                from resultados.models import Resultado
                for _j in jugadas_creadas:
                    _r = Resultado.objects.filter(
                        sorteo_id=_j.sorteo_id, fecha=_j.fecha_sorteo
                    ).first()
                    if _r:
                        reconciliar_premio_jugada(_j, resultado=_r, usuario_sistema=usuario)
            except Exception as _e:
                logger.warning(f'Reconciliacion tardia: {_e}')

            if boleta:

                if es_solo_editar:

                    # Modo editar: preservar metadata de pago original (no toca metadata['pago'])

                    pass

                else:

                    boleta.metadata['pago'] = {
                    'fondo': str(monto_fondo_consumido),
                    'bono': str(monto_bono_consumido),
                    'postpago': str(monto_postpago_consumido),
                    'total': str(total_apostado),
                }
                boleta.save(update_fields=['metadata'])
                boleta.recalcular_totales()

        # ── Calcular saldos finales para el resumen ──
        fondo_final    = Decimal('0.00')
        bono_final     = Decimal('0.00')
        postpago_final = Decimal('0.00')
        try:
            if forma_pago and cliente and destinatario:
                _f = Fondo.objects.filter(
                    usuario=cliente, forma_pago=forma_pago,
                    asignado_por=destinatario, activo=True
                ).first()
                fondo_final = _f.monto if _f else Decimal('0.00')

                bono_final = Bono.objects.filter(
                    usuario=cliente, asignado_por=destinatario,
                    estado='activo', saldo_restante__gt=0,
                ).aggregate(t=Sum('saldo_restante'))['t'] or Decimal('0.00')

                from roles.models import Postpago as _PP
                _pp = _PP.objects.filter(
                    cliente=cliente, gestor=destinatario,
                    forma_pago=forma_pago, activo=True,
                ).first()
                postpago_final = abs(_pp.saldo) if _pp and _pp.saldo < 0 else Decimal('0.00')
        except Exception as _eS:
            logger.warning(f'[resumen] calculo saldos finales: {_eS}')

        if boleta:
            mensaje = f'✅ Boleta {boleta.referencia} guardada ({len(jugadas_creadas)} jugadas)'
        else:
            mensaje = f'✅ Apuesta guardada ({len(jugadas_creadas)} jugadas)'

        # Serializar jugadas para el preview (usado en dry_run)
        preview_jugadas = []
        for _j in jugadas_creadas:
            preview_jugadas.append({
                'numero': _j.numero,
                'forma_juego': _j.forma_juego.nombre if _j.forma_juego else '',
                'sorteo': _j.sorteo.nombre if _j.sorteo else '',
                'monto': float(_j.monto),
            })
        _items_originales = len(items_normales) + len(items_super)
        _descartadas = max(0, _items_originales - len(jugadas_creadas))

        # FIX_CASCADE_V1: recomputar cuadres si hubo jugadas retroactivas
        try:
            from roles.cuadre_cascade import cascadear_retroactivas
            cascadear_retroactivas(jugadas_creadas)
        except Exception as _ce:
            import logging
            logging.getLogger(__name__).warning(f"cascadear_retroactivas falló: {_ce}")

        return JsonResponse({
            'success': True,
            'message': mensaje,
            'cantidad': len(jugadas_creadas),
            'boleta_id': boleta.id if boleta else None,
            'boleta_referencia': boleta.referencia if boleta else None,
            'advertencias': advertencias,
            'preview': {
                'jugadas': preview_jugadas,
                'total': float(total_apostado),
                'descartadas': _descartadas,
                'items_originales': _items_originales,
                'desglose': {
                    'fondo':    float(monto_fondo_consumido),
                    'bono':     float(monto_bono_consumido),
                    'postpago': float(monto_postpago_consumido),
                },
                'saldos_finales': {
                    'fondo':    float(fondo_final),
                    'bono':     float(bono_final),
                    'postpago': float(postpago_final),
                },
            },
        })

    except ValueError as e:
        logger.warning(f"Error de validación en guardar_apuesta: {e}")
        return JsonResponse({'success': False, 'message': str(e)}, status=400)
    except Exception as e:
        tb = traceback.format_exc()
        logger.error(f"Error guardando apuesta: {e}\n{tb}")
        return JsonResponse({'success': False, 'message': f'Error interno: {str(e)}'}, status=500)


# ============================================================
# MIS APUESTAS
# ============================================================


def _sorteo_esta_abierto(sorteo, fecha):
    from sorteos.utils import calcular_estado_sorteo
    try:
        est = calcular_estado_sorteo(sorteo, timezone.now(), fecha)
        return getattr(est, "estado_actual", "cerrado") == "abierto"
    except Exception:
        return False


def _calcular_permisos_boleta(user, boleta, es_banco=False, es_superadmin=False):
    es_dueno = (boleta.usuario_id == user.id)
    es_gestor = (boleta.destinatario_id == user.id)
    es_autorizador = es_banco or es_superadmin
    # FIX_N_PLUS_1_PERMS_V1: una sola query + cache de sorteos por sorteo_id
    sorteo_abierto = True
    jugadas_qs = boleta.jugadas.exclude(estado="cancelada").values_list("sorteo_id", "fecha_sorteo").distinct()[:50]
    _sorteos_cache = {}
    for sorteo_id, fecha in jugadas_qs:
        sorteo = _sorteos_cache.get(sorteo_id)
        if sorteo is None:
            sorteo = Sorteo.objects.filter(id=sorteo_id).first()
            _sorteos_cache[sorteo_id] = sorteo
        if not sorteo or not _sorteo_esta_abierto(sorteo, fecha):
            sorteo_abierto = False
            break
    base = {"es_dueno": es_dueno, "es_gestor": es_gestor, "sorteo_abierto": sorteo_abierto}
    if not (es_dueno or es_gestor):
        base.update({"puede_editar": False, "puede_reenviar": False, "puede_eliminar": False})
    elif sorteo_abierto:
        base.update({"puede_editar": True, "puede_reenviar": True, "puede_eliminar": True})
    elif es_gestor and es_autorizador:
        base.update({"puede_editar": True, "puede_reenviar": True, "puede_eliminar": True})
    elif es_gestor:
        base.update({"puede_editar": False, "puede_reenviar": True, "puede_eliminar": False})
    else:
        base.update({"puede_editar": False, "puede_reenviar": False, "puede_eliminar": False})
    return base

@login_required
def mis_apuestas(request):
    user = request.user
    # FIX_ROLES_CACHE_MIS_APUESTAS_V1: una sola query para todos los roles
    _roles_activos = set(user.roles.filter(activo=True).values_list('tipo', flat=True))
    es_superadmin = user.is_superuser or ('superadmin' in _roles_activos)
    es_banco      = ('banco' in _roles_activos)
    es_comercial  = ('comercial' in _roles_activos)
    es_auditor_user = ('auditor' in _roles_activos)
    es_cliente    = not (es_superadmin or es_banco or es_comercial or es_auditor_user)
    es_autorizador = es_superadmin or es_banco or es_comercial or es_auditor_user

    f_banco       = (request.GET.get('banco')        or '').strip()
    f_comercial   = (request.GET.get('comercial')    or '').strip()
    f_cliente     = (request.GET.get('cliente')      or '').strip()
    f_gestor      = (request.GET.get('gestor')       or '').strip()
    f_sorteo      = (request.GET.get('sorteo')       or '').strip()
    f_forma       = (request.GET.get('forma_juego')  or '').strip()
    f_fecha_desde = (request.GET.get('fecha_desde')  or '').strip()
    f_fecha_hasta = (request.GET.get('fecha_hasta')  or '').strip()
    f_estado      = (request.GET.get('estado')       or '').strip()
    f_buscar      = (request.GET.get('buscar')       or '').strip()

    hoy = timezone.localdate()
    if not f_fecha_desde and not f_fecha_hasta:
        f_fecha_desde = hoy.strftime('%Y-%m-%d')
        f_fecha_hasta = hoy.strftime('%Y-%m-%d')

    # ─── Base queryset según rol ───
    if es_superadmin:
        base_qs = Jugada.objects.all()
    elif es_banco:
        comerciales_ids = list(Subordinacion.objects.filter(
            jefe=user, activo=True
        ).values_list('subordinado_id', flat=True))
        clientes_ids = list(Fondo.objects.filter(
            Q(asignado_por=user) | Q(asignado_por__in=comerciales_ids),
            activo=True
        ).values_list('usuario_id', flat=True).distinct())
        base_qs = Jugada.objects.filter(
            Q(usuario__in=clientes_ids) | Q(usuario=user) |
            Q(destinatario=user) | Q(destinatario__in=clientes_ids)
        )
    elif es_comercial:
        # FIX_MIS_APUESTAS_COMERCIAL_V1 (2026-10-17): incluir subordinados y clientes sin fondo activo
        clientes_ids = set(Fondo.objects.filter(
            asignado_por=user
        ).values_list('usuario_id', flat=True).distinct())
        sub_ids = set(Subordinacion.objects.filter(
            jefe=user, activo=True
        ).values_list('subordinado_id', flat=True).distinct())
        todos_clientes_ids = list(clientes_ids | sub_ids)

        base_qs = Jugada.objects.filter(
            Q(usuario__in=todos_clientes_ids) | Q(usuario=user) | Q(destinatario=user)
        )
    elif es_auditor_user:
        from roles.utils import get_red_del_auditor
        red = get_red_del_auditor(user)
        base_qs = Jugada.objects.filter(
            Q(destinatario_id__in=red['todos_ids']) |
            Q(usuario_id__in=red['todos_ids'])
        )
    else:
        base_qs = Jugada.objects.filter(Q(usuario=user) | Q(destinatario=user))

    # ═══════════════════════════════════════════════════════════════
    # OPCIONES DE FILTROS (en cascada)
    # ═══════════════════════════════════════════════════════════════
    bancos_opciones      = []
    comerciales_opciones = []
    clientes_opciones    = []
    gestores_opciones    = []

    if es_superadmin:
        bancos_opciones = list(User.objects.filter(
            roles__tipo='banco', roles__activo=True, is_active=True
        ).distinct().order_by('username'))

    if es_superadmin:
        com_qs = User.objects.filter(
            roles__tipo='comercial', roles__activo=True, is_active=True
        ).distinct()
        if f_banco.isdigit():
            ids_com_b = Subordinacion.objects.filter(
                jefe_id=int(f_banco), activo=True
            ).values_list('subordinado_id', flat=True)
            com_qs = com_qs.filter(id__in=ids_com_b)
        comerciales_opciones = list(com_qs.order_by('username'))
    elif es_banco:
        ids_com = Subordinacion.objects.filter(
            jefe=user, activo=True
        ).values_list('subordinado_id', flat=True)
        comerciales_opciones = list(
            User.objects.filter(id__in=ids_com, is_active=True).order_by('username')
        )

    if es_superadmin:
        cli_qs = User.objects.filter(is_active=True).exclude(
            Q(roles__tipo__in=['superadmin', 'banco', 'comercial']) | Q(is_superuser=True)
        ).distinct()
        if f_comercial.isdigit():
            ids_cli = Fondo.objects.filter(
                asignado_por_id=int(f_comercial), activo=True
            ).values_list('usuario_id', flat=True)
            cli_qs = cli_qs.filter(id__in=ids_cli)
        elif f_banco.isdigit():
            ids_com_b = Subordinacion.objects.filter(
                jefe_id=int(f_banco), activo=True
            ).values_list('subordinado_id', flat=True)
            ids_cli = Fondo.objects.filter(
                Q(asignado_por_id=int(f_banco)) | Q(asignado_por__in=ids_com_b),
                activo=True
            ).values_list('usuario_id', flat=True)
            cli_qs = cli_qs.filter(id__in=ids_cli)
        clientes_opciones = list(cli_qs.order_by('username'))
    elif es_banco:
        ids_com = Subordinacion.objects.filter(
            jefe=user, activo=True
        ).values_list('subordinado_id', flat=True)
        if f_comercial.isdigit():
            ids_cli = Fondo.objects.filter(
                asignado_por_id=int(f_comercial), activo=True
            ).values_list('usuario_id', flat=True)
        else:
            ids_cli = Fondo.objects.filter(
                Q(asignado_por=user) | Q(asignado_por__in=ids_com),
                activo=True
            ).values_list('usuario_id', flat=True)
        clientes_opciones = list(
            User.objects.filter(id__in=ids_cli, is_active=True).distinct().order_by('username')
        )
    elif es_comercial:
        # FIX_MIS_APUESTAS_COMERCIAL_V1: incluir subordinados en el filtro
        ids_cli = set(Fondo.objects.filter(
            asignado_por=user
        ).values_list('usuario_id', flat=True))
        sub_ids = set(Subordinacion.objects.filter(
            jefe=user, activo=True
        ).values_list('subordinado_id', flat=True))
        todos_ids = list(ids_cli | sub_ids)
        clientes_opciones = list(
            User.objects.filter(id__in=todos_ids, is_active=True).distinct().order_by('username')
        )

    if es_cliente:
        ids_gest = set()
        for f in Fondo.objects.filter(usuario=user, activo=True):
            if f.asignado_por_id:
                ids_gest.add(f.asignado_por_id)
        for b in Bono.objects.filter(usuario=user, estado='activo'):
            if b.asignado_por_id:
                ids_gest.add(b.asignado_por_id)
        gestores_opciones = list(
            User.objects.filter(id__in=ids_gest, is_active=True).order_by('username')
        )

    # ═══════════════════════════════════════════════════════════════
    # APLICAR FILTROS
    # ═══════════════════════════════════════════════════════════════
    # FIX_OCULTAR_CANCELADAS_V1: en "Mis apuestas" solo se ven
    # jugadas confirmadas, premiadas (ganadora) y no ganadoras (perdedora).
    # Se excluyen canceladas y anuladas.
    qs = base_qs.exclude(estado__in=['cancelada', 'anulada'])

    if es_superadmin and f_banco.isdigit():
        b_id = int(f_banco)
        ids_com_b = list(Subordinacion.objects.filter(
            jefe_id=b_id, activo=True
        ).values_list('subordinado_id', flat=True))
        ids_cli_b = list(Fondo.objects.filter(
            Q(asignado_por_id=b_id) | Q(asignado_por__in=ids_com_b),
            activo=True
        ).values_list('usuario_id', flat=True).distinct())
        qs = qs.filter(
            Q(usuario__in=ids_cli_b) |
            Q(destinatario_id=b_id) |
            Q(destinatario__in=ids_com_b) |
            Q(comercial__in=ids_com_b)
        )

    if (es_superadmin or es_banco) and f_comercial.isdigit():
        c_id = int(f_comercial)
        ids_cli_c = list(Fondo.objects.filter(
            asignado_por_id=c_id, activo=True
        ).values_list('usuario_id', flat=True).distinct())
        qs = qs.filter(
            Q(usuario__in=ids_cli_c) |
            Q(destinatario_id=c_id) |
            Q(comercial_id=c_id)
        )

    if es_autorizador and f_cliente.isdigit():
        cid = int(f_cliente)
        qs = qs.filter(Q(usuario_id=cid) | Q(destinatario_id=cid))

    if es_cliente and f_gestor.isdigit():
        qs = qs.filter(destinatario_id=int(f_gestor))

    if f_sorteo.isdigit():
        qs = qs.filter(sorteo_id=int(f_sorteo))
    if f_forma:
        qs = qs.filter(forma_juego__nombre__iexact=f_forma)
    if f_fecha_desde:
        qs = qs.filter(fecha_sorteo__gte=f_fecha_desde)
    if f_fecha_hasta:
        qs = qs.filter(fecha_sorteo__lte=f_fecha_hasta)
    if f_estado:
        qs = qs.filter(estado=f_estado)
    if f_buscar:
        # FIX_BUSQUEDA_FLEXIBLE_V1
        q_filter = (
            Q(numero__icontains=f_buscar) |
            Q(usuario__username__icontains=f_buscar) |
            Q(usuario__email__icontains=f_buscar)
        )
        if str(f_buscar).isdigit():
            q_filter |= Q(usuario__id=int(f_buscar))
        qs = qs.filter(q_filter)

    # FIX_SELECT_RELATED_MIS_APUESTAS_V1: precargar FKs para evitar N+1 en agrupar_jugadas
    qs = qs.select_related(
        'boleta', 'sorteo', 'forma_juego', 'forma_pago',
        'usuario', 'destinatario', 'comercial'
    )
    # ─── Agrupar primero ───
    sorteos_agrupados_normales, sorteos_agrupados_superparlet = agrupar_jugadas(qs)








    for _b in sorteos_agrupados_normales + sorteos_agrupados_superparlet:
        if _b.get("boletas_count", 0) > 1:
            _b["perms"] = {"puede_editar": False, "puede_reenviar": False, "puede_eliminar": False}
        elif _b.get("boleta"):
            _b["perms"] = _calcular_permisos_boleta(user, _b["boleta"], es_banco=es_banco, es_superadmin=es_superadmin)
        else:
            _b["perms"] = {"puede_editar": False, "puede_reenviar": False, "puede_eliminar": False}

    # ─── Stats por BOLETA ───
    def _stats_boletas(boletas_list):
        total_boletas = len(boletas_list)
        apostado = sum((b['total_apostado'] for b in boletas_list), Decimal('0.00'))
        premios  = sum((b['total_premios']  for b in boletas_list), Decimal('0.00'))
        ganadoras = sum(1 for b in boletas_list if b['estado_general'] == 'ganadora')
        tasa = (ganadoras / total_boletas * 100) if total_boletas > 0 else 0
        return {
            'total_jugadas':  total_boletas,
            'total_boletas':  total_boletas,
            'total_apostado': apostado,
            'total_premios':  premios,
            'ganadas':        ganadoras,
            'tasa_acierto':   tasa,
        }

    est_normales = _stats_boletas(sorteos_agrupados_normales)
    est_super    = _stats_boletas(sorteos_agrupados_superparlet)
    est_total    = _stats_boletas(
        sorteos_agrupados_normales + sorteos_agrupados_superparlet
    )

    # FIX_FILTROS_FINALES_MIS_APUESTAS_V1: una sola pasada al qs
    _sorteo_ids = set()
    _forma_ids = set()
    for _sid, _fid in qs.values_list('sorteo_id', 'forma_juego_id').distinct():
        if _sid: _sorteo_ids.add(_sid)
        if _fid: _forma_ids.add(_fid)

    sorteos_filtro = list(Sorteo.objects.filter(
        id__in=_sorteo_ids
    ).order_by('nombre')) if _sorteo_ids else []

    formas_juego_filtro = list(FormaJuego.objects.filter(
        id__in=_forma_ids
    ).order_by('nombre')) if _forma_ids else []

    context = {
        'sorteos_agrupados_normales': sorteos_agrupados_normales,
        'sorteos_agrupados_superparlet': sorteos_agrupados_superparlet,
        'estadisticas': est_total,
        'estadisticas_normales': est_normales,
        'estadisticas_super': est_super,
        'sorteos_filtro': sorteos_filtro,
        'formas_juego_filtro': formas_juego_filtro,
        'bancos_opciones': bancos_opciones,
        'comerciales_opciones': comerciales_opciones,
        'clientes_opciones': clientes_opciones,
        'gestores_opciones': gestores_opciones,
        'filtro_banco': f_banco,
        'filtro_comercial': f_comercial,
        'filtro_cliente': f_cliente,
        'filtro_gestor': f_gestor,
        'filtro_sorteo': f_sorteo,
        'filtro_forma': f_forma,
        'filtro_fecha_desde': f_fecha_desde,
        'filtro_fecha_hasta': f_fecha_hasta,
        'filtro_estado': f_estado,
        'filtro_buscar': f_buscar,
        'es_superadmin': es_superadmin,
        'es_banco': es_banco,
        'es_comercial': es_comercial,
        'es_cliente': es_cliente,
        'es_autorizador': es_autorizador,
        'rol_actual': (
            'superadmin' if es_superadmin else
            'banco'      if es_banco else
            'comercial'  if es_comercial else
            'cliente'
        ),
        'user': user,
        'hoy': timezone.now(),
    }
    # FIX_M2_CARTEL_PREMIO_V1: carteles rojos de premios no vistos
    try:
        from roles.models import Notificacion as _NotifM2
        context['carteles_premio'] = _NotifM2.objects.filter(
            usuario=request.user, tipo='premio', leido=False,
        ).order_by('-creado_en')[:3]
    except Exception:
        context['carteles_premio'] = []

    return render(request, 'jugadas/mis_apuestas.html', context)

# ============================================================
# MIS FONDOS
# ============================================================
@login_required
def mis_fondos(request):
    user = request.user
    fondos = Fondo.objects.filter(usuario=user, activo=True).select_related('forma_pago')
    bonos = Bono.objects.filter(usuario=user, estado='activo')
    total_fondos = sum(f.monto for f in fondos)
    total_bonos = sum(b.saldo_restante for b in bonos)

    context = {
        'fondos': fondos, 'bonos': bonos,
        'total_fondos': total_fondos, 'total_bonos': total_bonos,
        'saldo_total': total_fondos + total_bonos,
    }
    # Antes
    return render(request, 'usuarios/mis_fondos.html', context)


# ============================================================
# CREAR CLIENTE OFFLINE
# ============================================================
@login_required
@require_POST
@csrf_exempt
def api_crear_cliente(request):
    # AUTO_APPLIED_POSTPAGO
    """Crea User + ClienteOffline con recarga y/o postpago inicial."""
    from django.db import IntegrityError
    user = request.user
    es_superadmin = user.is_superuser or user.roles.filter(tipo='superadmin', activo=True).exists()
    es_banco      = user.roles.filter(tipo='banco', activo=True).exists()
    es_comercial  = user.roles.filter(tipo='comercial', activo=True).exists()
    if not (es_superadmin or es_banco or es_comercial):
        return JsonResponse({'success': False, 'error': 'Sin permiso'}, status=403)

    username        = (request.POST.get('username') or '').strip()
    email           = (request.POST.get('email') or '').strip().lower()
    password        = (request.POST.get('password') or '').strip()
    telefono_custom = (request.POST.get('telefono') or '').strip()
    recarga_monto_raw  = (request.POST.get('recarga_monto') or '').strip()
    recarga_fp_id_raw  = (request.POST.get('recarga_forma_pago_id') or '').strip()
    # FASE1_POSTPAGO_V1: ya no se asigna postpago al crear cliente

    if not username or len(username) < 3 or len(username) > 30:
        return JsonResponse({'success': False, 'error': 'Usuario invalido (3-30)'}, status=400)
    if not all(c.isalnum() or c in '._-' for c in username):
        return JsonResponse({'success': False, 'error': 'Usuario: solo alfanumericos . _ -'}, status=400)
    if not password or len(password) < 6:
        return JsonResponse({'success': False, 'error': 'Password minimo 6'}, status=400)
    if email:
        try:
            validate_email(email)
        except ValidationError:
            return JsonResponse({'success': False, 'error': 'Email invalido'}, status=400)
    else:
        email = f"{username.lower()}@offline.local"
    if telefono_custom:
        d = re.sub(r'\D', '', telefono_custom)
        if len(d) < 5 or len(d) > 15:
            return JsonResponse({'success': False, 'error': 'Telefono invalido'}, status=400)
        if ClienteOffline.objects.filter(telefono_offline=telefono_custom).exists():
            return JsonResponse({'success': False, 'error': 'Telefono ya usado'}, status=400)

    recarga_monto = None; recarga_fp = None
    if recarga_monto_raw or recarga_fp_id_raw:
        if not recarga_monto_raw or not recarga_fp_id_raw:
            return JsonResponse({'success': False, 'error': 'Recarga: monto y FP requeridos'}, status=400)
        try:
            recarga_monto = Decimal(recarga_monto_raw)
        except Exception:
            return JsonResponse({'success': False, 'error': 'Monto recarga invalido'}, status=400)
        if recarga_monto <= 0:
            return JsonResponse({'success': False, 'error': 'Monto recarga > 0'}, status=400)
        if not recarga_fp_id_raw.isdigit():
            return JsonResponse({'success': False, 'error': 'FP invalida'}, status=400)
        try:
            recarga_fp = FormaPago.objects.get(id=int(recarga_fp_id_raw), activo=True)
        except FormaPago.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'FP no valida'}, status=400)
        if recarga_fp.nombre.lower() == 'bono':
            return JsonResponse({'success': False, 'error': 'No se recarga con bono'}, status=400)


    try:
        with transaction.atomic():
            if User.objects.filter(username__iexact=username).exists():
                return JsonResponse({'success': False, 'error': 'Usuario ya existe'}, status=400)
            if email and not email.endswith('@offline.local'):
                if User.objects.filter(email__iexact=email).exists():
                    return JsonResponse({'success': False, 'error': 'Email ya registrado'}, status=400)

            nuevo = User.objects.create_user(username=username, email=email, password=password)
            telefono = telefono_custom if telefono_custom else _siguiente_telefono_offline()
            try:
                nuevo.telefono = telefono
                nuevo.save(update_fields=['telefono'])
            except Exception as e:
                logger.warning(f"No se guardo telefono: {e}")
                try:
                    if hasattr(nuevo, 'perfil'):
                        nuevo.perfil.telefono = telefono
                        nuevo.perfil.save(update_fields=['telefono'])
                except Exception as e2:
                    logger.warning(f"Tampoco en perfil: {e2}")

            co = ClienteOffline.objects.create(
                user=nuevo, creado_por=user, telefono_offline=telefono,
                metadata={'origen': 'crear_cliente', 'creado_por_username': user.username},
            )
            co.set_password_cifrada(password)
            Subordinacion.objects.get_or_create(jefe=user, subordinado=nuevo, defaults={'activo': True})
            Rol.objects.get_or_create(
                usuario=nuevo, tipo='cliente',
                defaults={'activo': True, 'fondo': 0}
            )

            if recarga_monto and recarga_fp:
                # FIX_ANTI_DUP_CREACION (2026-10-18)
                from roles.utils import verificar_recarga_duplicada
                if verificar_recarga_duplicada(user, nuevo, recarga_fp, recarga_monto, segundos=60):
                    # Es un cliente nuevo, si falla es un error de la red, pero lo blindamos
                    pass
                # FASE1_POSTPAGO_V1: helper (aunque un cliente nuevo no debería tener postpago)
                from roles.utils import _aplicar_ingreso_a_fondo
                _aplicar_ingreso_a_fondo(
                    cliente=nuevo, gestor=user,
                    forma_pago=recarga_fp, monto=recarga_monto,
                )
                _f4 = Fondo.objects.filter(
                    usuario=nuevo, forma_pago=recarga_fp, activo=True
                ).first()
                _saldo_c4 = _f4.monto if _f4 else Decimal('0.00')
                MovimientoFondo.objects.create(
                    emisor=user, receptor=nuevo, forma_pago=recarga_fp,
                    monto=recarga_monto, tipo='recarga', estado='confirmado',
                    motivo=f"Recarga inicial · {recarga_fp.nombre}",
                    datos_transferencia={
                        'cliente_nuevo': nuevo.username,
                        'forma_pago': recarga_fp.nombre,
                        'tipo_operacion': 'recarga_inicial',
                    },
                    nota="Recarga inicial al crear cliente " + nuevo.username,
                    saldo_antes=_saldo_c4 - recarga_monto,
                    saldo_despues=_saldo_c4,
                )


    except IntegrityError as e:
        logger.error("IntegrityError: " + str(e), exc_info=True)
        return JsonResponse({'success': False, 'error': 'Conflicto: usuario/email/telefono ya existen.'}, status=400)
    except ValueError as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
    except RuntimeError as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
    except Exception as e:
        logger.exception("Error creando cliente")
        return JsonResponse({'success': False, 'error': "Error interno: " + str(e)}, status=500)

    payload = {
        'success': True,
        'message': 'Cliente "' + nuevo.username + '" creado',
        'cliente': {'id':nuevo.id,'nombre':nuevo.username,'email':nuevo.email,
                    'telefono':telefono,'es_offline':True,'saldo':0.0},
    }
    partes = []
    if recarga_monto and recarga_fp:
        payload['cliente']['saldo'] = float(recarga_monto)
        payload['recarga'] = {'monto':float(recarga_monto),
                              'forma_pago_id':recarga_fp.id,'forma_pago':recarga_fp.nombre}
        partes.append("recargado con $" + str(recarga_monto) + " en " + recarga_fp.nombre)
    if partes:
        payload['message'] = 'Cliente "' + nuevo.username + '" creado y ' + ' + '.join(partes)
    return JsonResponse(payload)

# ============================================================
# CREAR CLIENTE OFFLINE
# ============================================================
# ============================================================
# VER PASSWORD DE CLIENTE OFFLINE
# ============================================================
@login_required
def api_ver_password_cliente(request, cliente_id):
    user = request.user

    try:
        co = ClienteOffline.objects.select_related('user', 'creado_por').get(user_id=cliente_id)
    except ClienteOffline.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'No es un cliente offline'}, status=404)

    es_superadmin = user.is_superuser or user.roles.filter(tipo='superadmin', activo=True).exists()
    es_creador = co.creado_por_id == user.id
    es_banco_del_creador = (
        co.creado_por_id and _get_banco_de(co.creado_por) == user
    )

    if not (es_superadmin or es_creador or es_banco_del_creador):
        return JsonResponse({'success': False, 'error': 'Sin permiso'}, status=403)

    if co.password_cambiada_por_cliente:
        return JsonResponse({
            'success': True,
            'disponible': False,
            'motivo': 'El cliente ya cambió su contraseña',
        })

    pwd = co.get_password_cifrada()
    if not pwd:
        return JsonResponse({
            'success': False,
            'error': 'No hay contraseña guardada para este cliente'
        }, status=400)

    return JsonResponse({
        'success': True,
        'disponible': True,
        'password': pwd,
        'username': co.user.username,
    })


# ============================================================
# RESTO DE APIs (sin cambios — se mantienen tal cual)
# ============================================================
@login_required
def api_verificar_sorteo(request, sorteo_id):
    try:
        sorteo = get_object_or_404(Sorteo, id=sorteo_id)
        ahora = timezone.now()
        hoy = timezone.localdate()
        sorteo = calcular_estado_sorteo(sorteo, ahora, hoy)
        esta_abierto = getattr(sorteo, 'estado_actual', 'cerrado') == 'abierto'
        return JsonResponse({
            'abierto': esta_abierto, 'id': sorteo.id,
            'estado': getattr(sorteo, 'estado_actual', None),
            'segundos_restantes': getattr(sorteo, 'segundos_restantes', 0),
            'hora_salida': sorteo.hora_salida.strftime('%I:%M %p').lstrip('0') if sorteo.hora_salida else None,
            'hora_cierre': sorteo.hora_cierre.strftime('%H:%M') if getattr(sorteo, 'hora_cierre', None) else None,
        })
    except Sorteo.DoesNotExist:
        return JsonResponse({'error': 'Sorteo no encontrado'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def api_verificar_saldo(request):
    try:
        usuario_id = request.GET.get('usuario_id')
        if not usuario_id or not str(usuario_id).isdigit():
            return JsonResponse({'error': 'usuario_id inválido'}, status=400)

        try:
            seleccionado = User.objects.get(id=int(usuario_id))
        except User.DoesNotExist:
            return JsonResponse({'error': 'Usuario no encontrado'}, status=404)

        user = request.user
        es_superadmin = user.is_superuser or user.roles.filter(tipo='superadmin', activo=True).exists()
        gestor_id_raw = (request.GET.get('gestor_id') or '').strip()

        if es_superadmin:
            fondos_qs = Fondo.objects.filter(
                usuario=seleccionado, activo=True
            ).select_related('forma_pago')
            filtro_bono = Q(usuario=seleccionado)
            # CONSISTENCIA_POSTPAGO_V1: si viene gestor_id, filtrar por gestor especifico
            if gestor_id_raw.isdigit():
                filtro_postpago = Q(cliente=seleccionado, gestor_id=int(gestor_id_raw))
            else:
                filtro_postpago = Q(cliente=seleccionado)
        elif user.id == seleccionado.id:
            # FIX_SELFVIEW_V2: el cliente se ve a sí mismo → TODOS sus fondos
            fondos_qs = Fondo.objects.filter(
                usuario=seleccionado, activo=True
            ).select_related('forma_pago')
            filtro_bono = Q(usuario=seleccionado)
            if gestor_id_raw.isdigit():
                filtro_postpago = Q(cliente=seleccionado, gestor_id=int(gestor_id_raw))
            else:
                filtro_postpago = Q(cliente=seleccionado)
        else:
            fondos_qs = Fondo.objects.filter(
                Q(usuario=user, asignado_por=seleccionado) |
                Q(usuario=seleccionado, asignado_por=user),
                activo=True
            ).select_related('forma_pago')
            filtro_bono = (
                Q(usuario=user, asignado_por=seleccionado) |
                Q(usuario=seleccionado, asignado_por=user)
            )
            # CONSISTENCIA_POSTPAGO_V1: si viene gestor_id, filtrar por gestor especifico
            if gestor_id_raw.isdigit():
                filtro_postpago = Q(cliente=seleccionado, gestor_id=int(gestor_id_raw))
            else:
                filtro_postpago = (
                    Q(cliente=user, gestor=seleccionado) |
                    Q(cliente=seleccionado, gestor=user)
                )

        saldos = {}
        total_fondos = 0
        for f in fondos_qs:
            monto = float(f.monto) if f.monto is not None else 0.0
            total_fondos += monto
            if f.forma_pago:
                saldos[f.forma_pago.id] = saldos.get(f.forma_pago.id, 0.0) + monto

        # FIX_FP_BONO_POSTPAGO_V1: bonos agrupados por FP
        bonos_qs = Bono.objects.filter(filtro_bono, estado='activo', saldo_restante__gt=0)
        bonos_por_fp = {}
        bonos_sin_fp = 0.0
        for b in bonos_qs:
            monto_b = float(b.saldo_restante or 0)
            if b.forma_pago_id:
                bonos_por_fp[b.forma_pago_id] = bonos_por_fp.get(b.forma_pago_id, 0.0) + monto_b
            else:
                bonos_sin_fp += monto_b
        saldo_bonos = sum(bonos_por_fp.values()) + bonos_sin_fp

        from roles.models import Postpago
        # FASE1_POSTPAGO_V1_CHIP: deuda = abs(saldo) cuando saldo < 0
        postpagos_qs = Postpago.objects.filter(
            filtro_postpago, activo=True, saldo__lt=0
        )
        postpagos_por_fp = {}
        postpagos_sin_fp = 0.0
        for p in postpagos_qs:
            monto_p = float(abs(p.saldo) if p.saldo else 0)
            if p.forma_pago_id:
                postpagos_por_fp[p.forma_pago_id] = postpagos_por_fp.get(p.forma_pago_id, 0.0) + monto_p
            else:
                postpagos_sin_fp += monto_p
        postpago_pendiente = sum(postpagos_por_fp.values()) + postpagos_sin_fp

        # FIX_POSTPAGO_TARJETA_V1 (2026-10-18): Si Tarjeta > 0, ocultar postpago
        from pagos.models import FormaPago
        fp_tarjeta = FormaPago.objects.filter(nombre__iexact='Tarjeta').first()
        if fp_tarjeta and saldos.get(fp_tarjeta.id, 0.0) > 0:
            postpago_pendiente = 0.0
            postpagos_por_fp = {}
            postpagos_sin_fp = 0.0

        return JsonResponse({
            'saldos': saldos,
            'total_fondos': total_fondos,
            'total_bonos': saldo_bonos,
            'saldo_total': total_fondos + saldo_bonos,
            'postpago_pendiente': postpago_pendiente,
            'bonos_por_fp': bonos_por_fp,
            'bonos_sin_fp': bonos_sin_fp,
            'postpagos_por_fp': postpagos_por_fp,
            'postpagos_sin_fp': postpagos_sin_fp,
        })
    except Exception as e:
        logger.error(f"Error en api_verificar_saldo: {e}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def api_forma_pago_cliente(request):
    try:
        cliente_id = request.GET.get('cliente_id')
        if not cliente_id or not str(cliente_id).isdigit():
            return JsonResponse({'formas_pago': []})

        try:
            seleccionado = User.objects.get(id=int(cliente_id))
        except User.DoesNotExist:
            return JsonResponse({'formas_pago': []})

        user = request.user
        es_superadmin = user.is_superuser or user.roles.filter(tipo='superadmin', activo=True).exists()

        if es_superadmin or user.id == seleccionado.id:
            # FIX_SELFVIEW_V1: self-view o superadmin → todos sus fondos
            fondos_qs = Fondo.objects.filter(
                usuario=seleccionado, activo=True
            ).select_related('forma_pago', 'asignado_por')
        else:
            fondos_qs = Fondo.objects.filter(
                Q(usuario=user, asignado_por=seleccionado) |
                Q(usuario=seleccionado, asignado_por=user),
                activo=True
            ).select_related('forma_pago', 'asignado_por')

        formas_pago = []
        visto = set()

        # 1. Agregar las FPs de los fondos existentes
        for f in fondos_qs:
            if not f.forma_pago:
                continue
            key = (f.forma_pago.id, f.asignado_por_id)
            if key in visto:
                continue
            visto.add(key)
            formas_pago.append({
                'id': f.forma_pago.id,
                'nombre': f.forma_pago.nombre,
                'gestor_id': f.asignado_por_id,
                'gestor_username': f.asignado_por.username if f.asignado_por else None,
            })

        # 2. FIX_FP_NUEVAS_V1 (2026-10-18): Si el usuario es gestor, agregar las FPs que tiene asignadas
        if not (es_superadmin or user.id == seleccionado.id):
            from roles.models import RecursoAsignado
            # Buscamos recursos asignados al gestor actual (o a su banco si es comercial)
            recursos_qs = RecursoAsignado.objects.filter(
                Q(banco=user) | Q(comercial=user),
                tipo='forma_pago',
                activo=True
            ).select_related('forma_pago')

            for r in recursos_qs:
                if not r.forma_pago:
                    continue
                key = (r.forma_pago.id, user.id)
                if key in visto:
                    continue
                visto.add(key)
                formas_pago.append({
                    'id': r.forma_pago.id,
                    'nombre': r.forma_pago.nombre,
                    'gestor_id': user.id,
                    'gestor_username': user.username,
                })
        return JsonResponse({'formas_pago': formas_pago})
    except Exception as e:
        logger.error(f"Error en api_forma_pago_cliente: {e}", exc_info=True)
        return JsonResponse({'formas_pago': [], 'error': str(e)}, status=500)

@login_required
def api_sorteos_disponibles(request):
    from zoneinfo import ZoneInfo
    try:
        CUBA_TZ = ZoneInfo('America/Havana')
    except Exception:
        CUBA_TZ = pytz.timezone(settings.TIME_ZONE)

    ahora = timezone.now().astimezone(CUBA_TZ)
    # FIX_FECHA_SORTEOS_V1 (2026-10-18): respetar la fecha enviada por el frontend
    _req_fecha = request.GET.get('fecha')
    if _req_fecha:
        try:
            hoy = datetime.strptime(_req_fecha, '%Y-%m-%d').date()
        except ValueError:
            hoy = ahora.date()
    else:
        hoy = ahora.date()

    def _hora_salida_hoy(sorteo):
        dia_es = {0: 'lunes', 1: 'martes', 2: 'miercoles', 3: 'jueves',
                  4: 'viernes', 5: 'sabado', 6: 'domingo'}[hoy.weekday()]
        temp = 'verano' if es_verano_cuba(hoy) else 'invierno'
        if sorteo.horarios:
            hora_str = (sorteo.horarios.get(temp) or {}).get(dia_es)
            if not hora_str:
                return None
            try:
                hh, mm = hora_str.split(':')
                return datetime.strptime(f"{hh}:{mm}", "%H:%M").time()
            except Exception:
                return None
        return sorteo.hora_salida

    def _calcular_estado(sorteo, hora_salida):
        minutos = sorteo.minutos_cierre if sorteo.minutos_cierre is not None else 60
        dt_salida = datetime.combine(hoy, hora_salida)
        if hasattr(CUBA_TZ, 'localize'):
            dt_salida = CUBA_TZ.localize(dt_salida)
        else:
            dt_salida = dt_salida.replace(tzinfo=CUBA_TZ)
        dt_cierre = dt_salida - timedelta(minutes=minutos)

        if ahora < dt_cierre:
            return 'abierto', int((dt_cierre - ahora).total_seconds()), dt_cierre
        elif ahora < dt_salida:
            return 'cerrado', int((dt_salida - ahora).total_seconds()), dt_cierre
        else:
            # FIX_PROXIMO_DIA_V1: el sorteo ya salió hoy. Calculamos el countdown
            # hasta la próxima salida (mañana o el día que corresponda).
            seg_prox = _seg_hasta_prox(sorteo, ahora)
            return 'salido', (seg_prox or 0), dt_cierre

    sorteos_data = []
    for s in Sorteo.objects.filter(activo=True).order_by('id'):
        hora_salida = _hora_salida_hoy(s)

        if not hora_salida:
            sorteos_data.append({
                'id': s.id,
                'nombre': s.nombre,
                'origen': s.origen or 'otro',
                'estado': 'no_programado',
                'esta_abierto': False,
                'hora_salida': '—',
                'hora_salida_sort': '99:99',
                'hora_cierre': '—',
                'segundos_restantes': 0,
                'minutos_restantes': 0,
                'formas_juego': s.formas_juego or [],
            })
            continue

        estado, segundos, dt_cierre = _calcular_estado(s, hora_salida)
        minutos = max(0, segundos // 60)

        sorteos_data.append({
            'id': s.id,
            'nombre': s.nombre,
            'origen': s.origen or 'otro',
            'estado': estado,
            'esta_abierto': estado == 'abierto',
            'hora_salida': hora_salida.strftime('%I:%M %p').lstrip('0'),
            'hora_salida_sort': hora_salida.strftime('%H:%M'),
            'hora_cierre': dt_cierre.strftime('%I:%M %p').lstrip('0') if dt_cierre else '',
            'segundos_restantes': segundos,
            'minutos_restantes': minutos,
            'es_proximo_dia': (estado == 'salido' and segundos > 0),
            'formas_juego': s.formas_juego or [],
        })

    orden_estado = {'abierto': 0, 'cerrado': 1, 'salido': 2, 'no_programado': 3}
    sorteos_data.sort(key=lambda x: (
        orden_estado.get(x['estado'], 9),
        x.get('hora_salida_sort', '99:99')
    ))

    return JsonResponse(sorteos_data, safe=False)

@login_required
@login_required
def api_sorteos_con_boleta(request):
    """
    FIX_MARCAS_SORTEOS_V1: devuelve los sorteo_ids donde el cliente
    ya tiene una boleta activa para esa fecha + forma de pago.
    """
    try:
        cliente_id = request.GET.get('cliente_id')
        forma_pago_id = request.GET.get('forma_pago_id')
        fecha = request.GET.get('fecha')
        if not cliente_id or not forma_pago_id or not fecha:
            return JsonResponse({'sorteo_ids': []})
        try:
            cliente_id = int(cliente_id)
            forma_pago_id = int(forma_pago_id)
            from datetime import datetime as _dt
            fecha_d = _dt.strptime(fecha, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            return JsonResponse({'sorteo_ids': []})

        sorteo_ids = list(Boleta.objects.filter(
            usuario_id=cliente_id,
            forma_pago_id=forma_pago_id,
            fecha_sorteo=fecha_d,
            estado='activa',
        ).values_list('jugadas__sorteo_id', flat=True).distinct())
        sorteo_ids = [s for s in sorteo_ids if s]
        return JsonResponse({'sorteo_ids': sorteo_ids})
    except Exception as e:
        return JsonResponse({'sorteo_ids': [], 'error': str(e)})


def api_configuracion_sorteo(request):
    try:
        sorteo_id = request.GET.get('sorteo_id')
        if not sorteo_id:
            return JsonResponse({'success': False, 'error': 'Falta sorteo_id'})
        sorteo = Sorteo.objects.get(id=int(sorteo_id), activo=True)
        config_data = obtener_configuracion_sorteo(sorteo)

        # FIX_CIERRE_V1: formas efectivas (incluye derivadas por config)
        # FIX_VS_CON_PARLET_V1: incluir 'vs' derivada cuando parlet está activo
        formas_efectivas = list(sorteo.formas_juego or [])
        formas_lower = [str(f).strip().lower() for f in formas_efectivas]
        cfg = config_data['config']
        for derivada in ('candado', 'vs'):
            if cfg.get(derivada, False) and derivada not in formas_lower:
                formas_efectivas.append(derivada)

        return JsonResponse({
            'success': True,
            'config': cfg,
            'tablas_visibles': config_data['tablas_visibles'],
            'superparlet_visible': config_data['superparlet_visible'],
            'columnas_tradicional': config_data['columnas_tradicional'],
            'formas_juego': formas_efectivas,
        })
    except Sorteo.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Sorteo no encontrado'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@csrf_exempt
def api_verificar_password(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    try:
        data = json.loads(request.body)
        password = data.get('password')
        if not password:
            return JsonResponse({'success': False, 'error': 'Contraseña requerida'})
        # FIX_VERIFICAR_PWD_V1 (2026-10-14):
        # Antes se usaba authenticate(), que durante una sesion activa
        # puede rotar la sesion o devolver None aunque la pwd sea correcta.
        # check_password() valida sin tocar la sesion.
        if request.user.check_password(password):
            return JsonResponse({'success': True})
        return JsonResponse({'success': False, 'error': 'Contraseña incorrecta'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def api_jugada_detalle(request):
    try:
        jugada_id = request.GET.get('id')
        if not jugada_id:
            return JsonResponse({'success': False, 'error': 'Falta ID'}, status=400)
        jugada = Jugada.objects.select_related('usuario', 'destinatario', 'sorteo', 'forma_juego', 'forma_pago').get(id=jugada_id)
        user = request.user
        es_autorizado = (
            user.is_superuser or
            user.roles.filter(tipo__in=['superadmin', 'banco', 'comercial'], activo=True).exists() or
            jugada.usuario == user or jugada.destinatario == user
        )
        if not es_autorizado:
            return JsonResponse({'success': False, 'error': 'No tienes permiso'}, status=403)

        return JsonResponse({
            'success': True,
            'jugada': {
                'id': jugada.id,
                'boleta_id': jugada.boleta_id,
                'boleta_referencia': jugada.boleta.referencia if jugada.boleta else None,
                'sorteo_nombre': jugada.sorteo.nombre if jugada.sorteo else 'N/A',
                'sorteo_id': jugada.sorteo.id if jugada.sorteo else None,
                'forma_juego_nombre': jugada.forma_juego.nombre if jugada.forma_juego else 'N/A',
                'forma_juego_id': jugada.forma_juego.id if jugada.forma_juego else None,
                'numero': jugada.numero, 'monto': float(jugada.monto),
                'forma_pago_nombre': jugada.forma_pago.nombre if jugada.forma_pago else None,
                'estado': jugada.estado, 'estado_display': jugada.get_estado_display(),
                'monto_premio': float(jugada.monto_premio) if jugada.monto_premio else None,
                'fecha': jugada.fecha.strftime('%d/%m/%Y %H:%M'),
                'usuario_username': jugada.usuario.username if jugada.usuario else 'N/A',
                'destinatario_username': jugada.destinatario.username if jugada.destinatario else 'N/A',
                'metadata': jugada.metadata,
            }
        })
    except Jugada.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Jugada no encontrada'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_POST
@csrf_exempt
def api_duplicar_boleta(request, boleta_id):
    try:
        original = Boleta.objects.get(id=boleta_id)
    except Boleta.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Boleta no encontrada'}, status=404)

    user = request.user
    es_superadmin = user.is_superuser or user.roles.filter(tipo='superadmin', activo=True).exists()
    es_banco = user.roles.filter(tipo='banco', activo=True).exists()
    es_comercial = user.roles.filter(tipo='comercial', activo=True).exists()
    es_autorizador = es_superadmin or es_banco or es_comercial

    if not (original.usuario_id == user.id or original.destinatario_id == user.id or es_autorizador):
        return JsonResponse({'success': False, 'error': 'No tienes permiso'}, status=403)

    fecha_str = request.POST.get('fecha')
    if fecha_str:
        try:
            fecha_apuesta = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({'success': False, 'error': 'Formato de fecha inválido'}, status=400)
    else:
        fecha_apuesta = timezone.localdate()

    hoy = timezone.localdate()
    # FIX_FUTURO_1ANO_V1
    _es_admin_d = user.is_superuser or user.roles.filter(tipo__in=['superadmin','banco'], activo=True).exists()
    if fecha_apuesta < hoy and not _es_admin_d:
        return JsonResponse({'success': False, 'error': 'Los clientes y comerciales solo pueden duplicar desde hoy en adelante.'}, status=400)
    _limite_d = hoy + timedelta(days=365)
    if fecha_apuesta > _limite_d:
        return JsonResponse({'success': False, 'error': 'No puedes duplicar a más de 1 año en el futuro.'}, status=400)

    cliente = original.usuario
    destinatario = original.destinatario
    forma_pago = original.forma_pago

    if not forma_pago:
        return JsonResponse({'success': False, 'error': 'La boleta original no tiene forma de pago'}, status=400)

    jugadas_originales = list(original.jugadas.exclude(estado='cancelada'))
    if not jugadas_originales:
        return JsonResponse({'success': False, 'error': 'La boleta no tiene jugadas para duplicar'}, status=400)

    puede_override_cierre = es_superadmin or es_banco

    lineas_ok = []
    advertencias = []
    consumo_memoria = defaultdict(Decimal)

    for j in jugadas_originales:
        sorteo = j.sorteo
        forma_juego = j.forma_juego
        numero = j.numero
        monto = j.monto

        estado_sorteo = calcular_estado_sorteo(sorteo, timezone.now(), fecha_apuesta)
        esta_abierto = getattr(estado_sorteo, 'estado_actual', 'cerrado') == 'abierto'

        if not esta_abierto and not puede_override_cierre:
            advertencias.append(f'Sorteo "{sorteo.nombre}" cerrado — línea {numero} omitida.')
            continue

        pool_total = get_pool_gestor(destinatario, sorteo, forma_juego, forma_pago)
        if pool_total <= 0:
            advertencias.append(f'Sin pool para {sorteo.nombre} - {forma_juego.nombre}.')
            continue

        key_mem = (sorteo.id, forma_juego.id, getattr(forma_pago, 'id', 0), numero)  # FIX_FORMA_PAGO_NONE_V1
        consumido_db = Jugada.objects.filter(
            destinatario=destinatario, sorteo=sorteo, forma_juego=forma_juego,
            forma_pago=forma_pago, fecha_sorteo=fecha_apuesta, numero=numero,
            estado__in=['confirmada', 'pendiente']
        ).aggregate(total=Sum('monto'))['total'] or Decimal('0')

        consumido = consumido_db + consumo_memoria[key_mem]
        disponible = pool_total - consumido

        if disponible <= 0:
            advertencias.append(f'Número {numero} en {sorteo.nombre} agotado.')
            continue

        monto_final = monto
        if monto > disponible:
            advertencias.append(f'Número {numero}: ${monto} → ${disponible} por pool.')
            monto_final = disponible

        lineas_ok.append({
            'sorteo': sorteo,
            'forma_juego': forma_juego,
            'numero': numero,
            'monto': monto_final,
            'metadata': dict(j.metadata or {}),
            'key_mem': key_mem,
        })
        consumo_memoria[key_mem] += monto_final

    if not lineas_ok:
        return JsonResponse({
            'success': False,
            'error': 'Ninguna línea se pudo duplicar (sorteos cerrados o números agotados).',
            'advertencias': advertencias,
        }, status=400)

    with transaction.atomic():
        nueva = Boleta.objects.create(
            usuario=cliente,
            destinatario=destinatario,
            comercial=user if user != cliente else None,
            creado_por=user,
            forma_pago=forma_pago,
            fecha_sorteo=fecha_apuesta,
            metadata={
                'origen': 'duplicar_boleta',
                'boleta_origen_id': original.id,
                'boleta_origen_ref': original.referencia,
            },
        )

        total_apostado = Decimal('0.00')
        jugadas_creadas = []

        for li in lineas_ok:
            j = Jugada(
                usuario=cliente,
                destinatario=destinatario,
                comercial=user if user != cliente else None,
                forma_juego=li['forma_juego'],
                sorteo=li['sorteo'],
                forma_pago=forma_pago,
                boleta=nueva,
                numero=li['numero'],
                monto=li['monto'],
                fecha_sorteo=fecha_apuesta,
                fecha=timezone.now(),
                estado='confirmada',
                metadata={**li['metadata'], 'duplicado_de_boleta': original.referencia},
            )
            j.save()
            jugadas_creadas.append(j)
            total_apostado += li['monto']

        ref_nueva = nueva.referencia

        monto_fondo_consumido = Decimal('0.00')
        monto_bono_consumido = Decimal('0.00')
        monto_postpago_consumido = Decimal('0.00')

        if total_apostado > 0:
            monto_restante = total_apostado

            fondo = Fondo.objects.filter(
                usuario=cliente, forma_pago=forma_pago, asignado_por=destinatario, activo=True
            ).first()
            if fondo:
                if fondo.monto >= monto_restante:
                    monto_fondo_consumido = monto_restante
                    fondo.monto -= monto_restante
                    fondo.save()
                    monto_restante = Decimal('0.00')
                    MovimientoFondo.objects.create(
                        emisor=cliente, receptor=destinatario, forma_pago=forma_pago,
                        monto=total_apostado, tipo='apuesta', estado='confirmado',
                        motivo=f"Duplicado {ref_nueva}",
                        datos_transferencia={
                            'referencia': str(ref_nueva),
                            'usuario': user.username,
                            'tipo_operacion': 'duplicado_total',
                        },
                        nota=f"Duplicado por {user.username}",
                        saldo_antes=fondo.monto + monto_restante,
                        saldo_despues=fondo.monto,
                    )
                else:
                    monto_fondo_consumido = fondo.monto
                    monto_descontado = fondo.monto
                    fondo.monto = Decimal('0.00')
                    fondo.save()
                    monto_restante -= monto_descontado
                    MovimientoFondo.objects.create(
                        emisor=cliente, receptor=destinatario, forma_pago=forma_pago,
                        monto=monto_descontado, tipo='apuesta', estado='confirmado',
                        motivo=f"Duplicado parcial {ref_nueva}",
                        datos_transferencia={
                            'referencia': str(ref_nueva),
                            'usuario': user.username,
                            'tipo_operacion': 'duplicado_parcial',
                        },
                        nota=f"Duplicado parcial por {user.username}",
                        saldo_antes=monto_descontado,
                        saldo_despues=Decimal('0.00'),
                    )

            if monto_restante > 0:
                # FIX_FIFO_BONOS_V2: filtro de vencidos + orden por vencimiento
                from django.utils import timezone as _tz_fifo
                from django.db.models import Q as _Q_fifo, F as _F_fifo
                bonos_activos = Bono.objects.filter(
                    usuario=cliente, asignado_por=destinatario,
                    estado='activo', saldo_restante__gt=0,
                ).filter(
                    _Q_fifo(fecha_vencimiento__isnull=True) |
                    _Q_fifo(fecha_vencimiento__gte=_tz_fifo.now())
                ).order_by(
                    _F_fifo('fecha_vencimiento').asc(nulls_last=True),
                    'creado_en'
                )
                for bono in bonos_activos:
                    if monto_restante <= 0:
                        break
                    if bono.saldo_restante >= monto_restante:
                        monto_bono_consumido += monto_restante
                        bono.saldo_restante -= monto_restante
                        bono.save(update_fields=['saldo_restante'])
                        monto_restante = Decimal('0.00')
                    else:
                        monto_bono_consumido += bono.saldo_restante
                        monto_restante -= bono.saldo_restante
                        bono.saldo_restante = Decimal('0.00')
                        bono.estado = 'agotado'
                        bono.save(update_fields=['saldo_restante', 'estado'])

            if monto_restante > 0:
                # FASE1_POSTPAGO_V1: acumular en Postpago.saldo
                from roles.models import Postpago
                pp, _created = Postpago.objects.select_for_update().get_or_create(
                    cliente=cliente, gestor=destinatario, forma_pago=forma_pago,
                    defaults={'saldo': Decimal('0.00'), 'activo': True},
                )
                pp.saldo -= monto_restante
                if pp.saldo < 0:
                    pp.activo = True
                pp.save(update_fields=['saldo', 'activo', 'actualizado_en'])
                monto_postpago_consumido = monto_restante

        nueva.metadata['pago'] = {
            'fondo': str(monto_fondo_consumido),
            'bono': str(monto_bono_consumido),
            'postpago': str(monto_postpago_consumido),
            'total': str(total_apostado),
        }
        nueva.save(update_fields=['metadata'])
        nueva.recalcular_totales()

    # FIX_CASCADE_V1: recomputar cuadres si hubo jugadas retroactivas
    try:
        from roles.cuadre_cascade import cascadear_retroactivas
        cascadear_retroactivas(jugadas_creadas)
    except Exception as _ce:
        import logging
        logging.getLogger(__name__).warning(f"cascadear_retroactivas falló: {_ce}")

    return JsonResponse({
        'success': True,
        'message': f'✅ Boleta duplicada como {nueva.referencia} ({len(jugadas_creadas)} líneas)',
        'boleta_id': nueva.id,
        'boleta_referencia': nueva.referencia,
        'boleta_origen': original.referencia,
        'cantidad': len(jugadas_creadas),
        'advertencias': advertencias,
    })

@login_required
@require_POST
@csrf_exempt
def api_cancelar_boleta(request, boleta_id):
    try:
        boleta = Boleta.objects.get(id=boleta_id)
    except Boleta.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Boleta no encontrada'}, status=404)

    user = request.user
    es_superadmin = user.is_superuser or user.roles.filter(tipo='superadmin', activo=True).exists()
    es_banco = user.roles.filter(tipo='banco', activo=True).exists()

    perms = _calcular_permisos_boleta(user, boleta, es_banco=es_banco, es_superadmin=es_superadmin)
    if not perms.get('puede_eliminar'):
        return JsonResponse({'success': False, 'error': 'No puedes eliminar esta boleta (sorteo cerrado o sin permiso)'}, status=403)

    motivo = (request.POST.get('motivo') or '').strip()
    ok, detalle, err = _do_cancelar_boleta(boleta, user, motivo=motivo)

    if not ok:
        return JsonResponse({'success': False, 'error': err}, status=400)

    try:
        crear_notificacion(
            usuario=boleta.destinatario, tipo='info',
            mensaje=f"🔄 Boleta {boleta.referencia} cancelada por {user.username}. Reintegro: ${detalle['total']}",
            datos={
                'boleta_id': boleta.id,
                'referencia': boleta.referencia,
                'monto': float(detalle['total']),
                'detalle': {k: float(v) for k, v in detalle.items() if k != 'total'},
            },
        )
    except Exception as e:
        logger.warning(f"No se pudo crear notificación: {e}")

    return JsonResponse({
        'success': True,
        'message': f'✅ Boleta {boleta.referencia} cancelada. Reintegrado: ${detalle["total"]}',
        'boleta_referencia': boleta.referencia,
        'reintegr_total': float(detalle['total']),
        'detalle': {k: float(v) for k, v in detalle.items() if k != 'total'},
    })

@login_required
def api_cancelar_jugada(request, jugada_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)
    try:
        jugada = Jugada.objects.get(id=jugada_id)
        user = request.user
        es_autorizador = user.is_superuser or user.roles.filter(tipo__in=['superadmin', 'banco', 'comercial'], activo=True).exists()
        if not (jugada.usuario == user or jugada.destinatario == user or es_autorizador):
            return JsonResponse({'success': False, 'error': 'No tienes permiso'}, status=403)
        if jugada.estado != 'pendiente':
            return JsonResponse({'success': False, 'error': 'La jugada ya no está pendiente'}, status=400)
        if not jugada.puede_modificar():
            return JsonResponse({'success': False, 'error': 'El sorteo ya ha cerrado'}, status=400)

        if jugada.forma_pago:
            fondo = Fondo.objects.filter(
                usuario=jugada.usuario, forma_pago=jugada.forma_pago,
                asignado_por=jugada.destinatario, activo=True
            ).first()
            if fondo:
                fondo.monto += jugada.monto
                fondo.save()
                MovimientoFondo.objects.create(
                    emisor=jugada.destinatario, receptor=jugada.usuario,
                    forma_pago=jugada.forma_pago, monto=jugada.monto,
                    tipo='ajuste', estado='confirmado',
                    motivo=f"Cancelación jugada #{jugada.id}",
                    datos_transferencia={
                        'jugada_id': jugada.id,
                        'cancelacion': True,
                        'cancelado_por': user.username,
                    },
                    nota=f"Cancelación por {user.username}",
                    saldo_antes=fondo.monto - jugada.monto,
                    saldo_despues=fondo.monto,
                )

        jugada.estado = 'cancelada'
        jugada.save()

        crear_notificacion(
            usuario=jugada.destinatario, tipo='info',
            mensaje=f"🔄 La jugada #{jugada.id} del sorteo {jugada.sorteo.nombre} ha sido cancelada por {user.username}.",
            datos={'jugada_id': jugada.id, 'monto': float(jugada.monto)}
        )
        return JsonResponse({'success': True, 'message': 'Jugada cancelada correctamente'})
    except Jugada.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Jugada no encontrada'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def api_info_apuesta(request):
    try:
        cliente_id = request.GET.get('cliente_id')
        sorteo_id = request.GET.get('sorteo_id')
        forma_pago_id = request.GET.get('forma_pago_id')
        forma_juego_id = request.GET.get('forma_juego_id')
        fecha_str = request.GET.get('fecha')

        if not all([cliente_id, sorteo_id, forma_pago_id]):
            return JsonResponse({'error': 'Faltan parámetros obligatorios'}, status=400)

        cliente = get_object_or_404(User, id=cliente_id)
        sorteo = get_object_or_404(Sorteo, id=sorteo_id)
        forma_pago = get_object_or_404(FormaPago, id=forma_pago_id)

        fecha_apuesta = datetime.strptime(fecha_str, '%Y-%m-%d').date() if fecha_str else timezone.localdate()

        usuario = request.user

        destinatario = None
        if usuario.is_superuser or usuario.roles.filter(tipo__in=['banco', 'comercial'], activo=True).exists():
            fondo_gestor = Fondo.objects.filter(
                usuario=cliente, asignado_por=usuario, forma_pago=forma_pago, activo=True
            ).first()
            if fondo_gestor:
                destinatario = usuario
            else:
                if usuario.is_superuser:
                    fondo = Fondo.objects.filter(usuario=cliente, forma_pago=forma_pago, activo=True).first()
                    if fondo and fondo.asignado_por:
                        destinatario = fondo.asignado_por
                    else:
                        destinatario = User.objects.filter(roles__tipo='superadmin', roles__activo=True).first()
                else:
                    destinatario = usuario
        else:
            sub = Subordinacion.objects.filter(subordinado=cliente, activo=True).first()
            if sub:
                destinatario = sub.jefe
            else:
                fondo = Fondo.objects.filter(usuario=cliente, forma_pago=forma_pago, activo=True).first()
                if fondo and fondo.asignado_por:
                    destinatario = fondo.asignado_por
                else:
                    destinatario = User.objects.filter(roles__tipo='superadmin', roles__activo=True).first()

        if not destinatario:
            destinatario = cliente

        pool_total = Decimal('0')
        dosis_valor = Decimal('1')
        sobrelimite_valor = Decimal('0')

        if forma_juego_id:
            forma_juego = get_object_or_404(FormaJuego, id=forma_juego_id)
            pool_total = get_pool_gestor(destinatario, sorteo, forma_juego, forma_pago)
            dosis_valor = get_dosis_gestor(destinatario, sorteo, forma_juego, forma_pago)
            sobrelimite_valor = get_sobrelimite_gestor(destinatario, sorteo, forma_juego, forma_pago)

        consumido = Jugada.objects.filter(
            usuario=cliente, sorteo=sorteo, forma_pago=forma_pago,
            fecha=fecha_apuesta, estado__in=['confirmada', 'pendiente']
        )
        if forma_juego_id:
            consumido = consumido.filter(forma_juego_id=forma_juego_id)
        total_apostado_hoy = consumido.aggregate(total=Sum('monto'))['total'] or Decimal('0')
        monto_disponible = pool_total - total_apostado_hoy

        restricciones = NumeroRestringido.objects.filter(
            sorteo=sorteo, gestor__in=[destinatario, None], cliente__in=[cliente, None],
            activo=True, fecha_vencimiento__gte=timezone.localdate()
        )
        numeros_limitados = list(restricciones.values_list('valor', flat=True))

        return JsonResponse({
            'success': True,
            'monto_maximo': float(pool_total),
            'monto_sobrelimite': float(sobrelimite_valor),
            'monto_disponible': float(monto_disponible),
            'dosis': float(dosis_valor),
            'numeros_limitados': numeros_limitados,
            'numeros_no_vendidos': [],
        })
    except Exception as e:
        logger.error(f"Error en api_info_apuesta: {str(e)}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_POST
def otorgar_postpago_view(request):
    try:
        data = json.loads(request.body)
        cliente_id = data.get('cliente_id')
        monto = data.get('monto')
        notas = data.get('notas', '')

        if not cliente_id or not monto:
            return JsonResponse({'success': False, 'error': 'Faltan datos'}, status=400)

        try:
            monto = Decimal(str(monto))
        except Exception:
            return JsonResponse({'success': False, 'error': 'Monto inválido'}, status=400)

        gestor = request.user
        cliente = get_object_or_404(User, id=int(cliente_id))

        if not (gestor.is_superuser or gestor.roles.filter(tipo__in=['superadmin', 'banco', 'comercial'], activo=True).exists()):
            return JsonResponse({'success': False, 'error': 'No tienes permiso'}, status=403)

        postpago = otorgar_postpago(gestor, cliente, monto, notas)
        return JsonResponse({
            'success': True,
            'message': f'Postpago de ${monto} otorgado a {cliente.username}',
            'postpago_id': postpago.id,
            'monto_pendiente': float(postpago.monto_pendiente)
        })
    except ValueError as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
    except Exception as e:
        logger.error(f"Error otorgando postpago: {e}", exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_POST
def liquidar_postpago_view(request):
    try:
        data = json.loads(request.body)
        cliente_id = data.get('cliente_id')
        monto = data.get('monto')
        origen = data.get('origen', 'manual')
        referencia_id = data.get('referencia_id', 0)

        if not cliente_id or not monto:
            return JsonResponse({'success': False, 'error': 'Faltan datos'}, status=400)

        try:
            monto = Decimal(str(monto))
        except Exception:
            return JsonResponse({'success': False, 'error': 'Monto inválido'}, status=400)

        cliente = get_object_or_404(User, id=int(cliente_id))
        es_superadmin = (
            request.user.is_superuser
            or request.user.roles.filter(tipo='superadmin', activo=True).exists()
        )

        excedente = liquidar_postpago(
            cliente, monto, origen, referencia_id,
            gestor=None if es_superadmin else request.user,
        )
        return JsonResponse({
            'success': True,
            'message': f'Postpago liquidado con ${monto}. Excedente: ${excedente}',
            'excedente': float(excedente)
        })
    except Exception as e:
        logger.error(f"Error liquidando postpago: {e}", exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def api_postpago_cliente(request):
    try:
        cliente_id = request.GET.get('cliente_id')
        if not cliente_id:
            return JsonResponse({'error': 'Falta cliente_id'}, status=400)

        cliente = get_object_or_404(User, id=int(cliente_id))
        user = request.user
        es_superadmin = user.is_superuser or user.roles.filter(tipo='superadmin', activo=True).exists()

        filtro = Q(cliente=cliente, estado__in=['activo', 'parcial'])

        if es_superadmin:
            pass
        elif user.id == cliente.id:
            pass
        else:
            filtro &= Q(gestor=user)

        # FASE1_POSTPAGO_V1: usar saldo < 0 como deuda
        from roles.models import Postpago
        postpagos = Postpago.objects.filter(filtro, saldo__lt=0).select_related('gestor', 'forma_pago').order_by('fecha_creacion')

        postpagos_data = [{
            'id': p.id,
            'gestor': p.gestor.username if p.gestor else '(sin gestor)',
            'gestor_id': p.gestor.id if p.gestor else None,
            'forma_pago': p.forma_pago.nombre if p.forma_pago else None,
            'forma_pago_id': p.forma_pago_id,
            'monto': float(abs(p.saldo)),
            'monto_pendiente': float(abs(p.saldo)),
            'estado': 'activo' if p.activo else 'liquidado',
            'fecha_creacion': p.fecha_creacion.strftime('%Y-%m-%d %H:%M'),
            'notas': p.concepto,
        } for p in postpagos]

        total_pendiente = sum(abs(p.saldo) for p in postpagos)
        return JsonResponse({
            'success': True,
            'postpagos': postpagos_data,
            'total_pendiente': float(total_pendiente),
        })
    except Exception as e:
        logger.error(f"Error en api_postpago_cliente: {e}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def api_disponible_por_numero(request):
    try:
        gestor_id = request.GET.get('gestor_id')
        sorteo_id = request.GET.get('sorteo_id')
        forma_pago_id = request.GET.get('forma_pago_id')
        fecha_str = request.GET.get('fecha')

        _faltantes = [k for k, v in {
            'gestor_id': gestor_id,
            'sorteo_id': sorteo_id,
            'forma_pago_id': forma_pago_id,
            'fecha': fecha_str,
        }.items() if not v]
        if _faltantes:
            logger.warning('[api_disponible_por_numero] faltan parámetros: %s', _faltantes)
            return JsonResponse({'error': 'Faltan parámetros', 'faltan': _faltantes}, status=400)

        gestor = get_object_or_404(User, id=gestor_id)
        sorteo = get_object_or_404(Sorteo, id=sorteo_id)
        forma_pago = get_object_or_404(FormaPago, id=forma_pago_id)
        fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()

        data = {}
        for fj in FormaJuego.objects.filter(activo=True):
            pool = get_pool_gestor(gestor, sorteo, fj, forma_pago)
            if pool <= 0:
                continue
            consumos = Jugada.objects.filter(
                destinatario=gestor, sorteo=sorteo, forma_juego=fj,
                forma_pago=forma_pago, fecha_sorteo=fecha,
                estado__in=['confirmada', 'pendiente']
            ).values('numero').annotate(total=Sum('monto'))
            data[str(fj.id)] = {
                'forma_nombre': fj.nombre,
                'forma_id': fj.id,
                'pool_total': float(pool),
                'consumido_por_numero': {c['numero']: float(c['total']) for c in consumos}
            }

        return JsonResponse({'success': True, 'data': data})
    except Exception as e:
        logger.error(f"Error en api_disponible_por_numero: {e}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)


# ============================================================
# HELPERS DE ANALYTICS
# ============================================================
def _generar_heatmap_dias(user, jugadas_qs, dias=90):
    hoy = timezone.localdate()
    inicio = hoy - timedelta(days=dias - 1)

    por_dia = (
        jugadas_qs
        .filter(fecha__date__gte=inicio)
        .annotate(d=TruncDate('fecha'))
        .values('d')
        .annotate(
            count=Count('id'),
            apuestas=Sum('monto'),
            premios=Sum('monto_premio'),
        )
    )

    mapa = {row['d']: row for row in por_dia}
    max_count = max((row['count'] or 0 for row in por_dia), default=0) or 1

    result = []
    for i in range(dias):
        fecha = inicio + timedelta(days=i)
        row = mapa.get(fecha)
        if row:
            count = row['count'] or 0
            apuestas = float(row['apuestas'] or 0)
            premios = float(row['premios'] or 0)
            level = min(4, int((count / max_count) * 4) + (1 if count > 0 else 0))
        else:
            count = 0
            apuestas = 0
            premios = 0
            level = 0
        result.append({
            'fecha': fecha,
            'count': count,
            'apuestas': apuestas,
            'premios': premios,
            'level': level,
        })
    return result


def _generar_insights(user, jugadas_qs, dias=30):
    hoy = timezone.localdate()
    hace_30 = hoy - timedelta(days=30)
    hace_60 = hoy - timedelta(days=60)

    insights = []

    periodo_actual = jugadas_qs.filter(fecha__date__gte=hace_30)
    periodo_anterior = jugadas_qs.filter(
        fecha__date__gte=hace_60, fecha__date__lt=hace_30
    )

    total_actual = periodo_actual.aggregate(t=Sum('monto'))['t'] or 0
    total_anterior = periodo_anterior.aggregate(t=Sum('monto'))['t'] or 0

    if total_anterior > 0:
        delta = ((total_actual - total_anterior) / total_anterior) * 100
        if delta > 5:
            insights.append({
                'icono': '📈',
                'texto': f'Apostaste <strong>+{delta:.0f}%</strong> más que el período anterior',
                'tipo': 'pos'
            })
        elif delta < -5:
            insights.append({
                'icono': '📉',
                'texto': f'Apostaste <strong>{delta:.0f}%</strong> menos que el período anterior',
                'tipo': 'warn'
            })

    mejor_dia = (
        periodo_actual
        .filter(estado='ganadora')
        .annotate(d=TruncDate('fecha'))
        .values('d')
        .annotate(premios=Sum('monto_premio'), cant=Count('id'))
        .order_by('-premios')
        .first()
    )
    if mejor_dia and (mejor_dia['premios'] or 0) > 0:
        insights.append({
            'icono': '🔥',
            'texto': f'Tu mejor día fue <strong>{mejor_dia["d"].strftime("%d/%m")}</strong>: ${mejor_dia["premios"]:,.0f} en premios',
            'tipo': 'pos'
        })

    sorteo_top = (
        periodo_actual
        .filter(estado='ganadora')
        .values('sorteo__nombre')
        .annotate(premios=Sum('monto_premio'))
        .order_by('-premios')
        .first()
    )
    if sorteo_top and (sorteo_top['premios'] or 0) > 0:
        insights.append({
            'icono': '⭐',
            'texto': f'El sorteo <strong>{sorteo_top["sorteo__nombre"]}</strong> te ha dado ${sorteo_top["premios"]:,.0f}',
            'tipo': 'info'
        })

    total_ganadoras = periodo_actual.filter(estado='ganadora').count()
    total_jugadas = periodo_actual.count()
    if total_jugadas > 0:
        tasa = (total_ganadoras / total_jugadas) * 100
        insights.append({
            'icono': '🎯',
            'texto': f'Tasa de acierto últimos 30 días: <strong>{tasa:.0f}%</strong> ({total_ganadoras} de {total_jugadas})',
            'tipo': 'info'
        })

    return insights

# ═══════════════════════════════════════════════════════════════
# Wrapper: soporta dry_run para preview de apuesta
# ═══════════════════════════════════════════════════════════════
@login_required
@require_POST
def guardar_apuesta(request):
    """
    Si POST trae dry_run=true: ejecuta la logica completa en una
    transaccion que se REVIERTE al final. Devuelve el preview de lo
    que se guardaria, sin persistir nada.
    Si dry_run es falso: guarda normalmente.
    """
    import traceback as _tb
    from django.db import transaction

    try:
        return _guardar_apuesta_body(request)
    except Exception as _eTop:
        logger.error('[guardar_apuesta TOP] %s\n%s', str(_eTop), _tb.format_exc())
        return JsonResponse({
            'success': False,
            'message': 'Error interno del servidor. Contacta al administrador.',
        }, status=500)


def _guardar_apuesta_body(request):
    from django.db import transaction

    dry_run = (request.POST.get('dry_run', '').lower() == 'true')

    if not dry_run:
        return _guardar_apuesta_impl(request)

    try:
        with transaction.atomic():
            response = _guardar_apuesta_impl(request)
            transaction.set_rollback(True)

            try:
                import json as _json
                data = _json.loads(response.content)
                data['dry_run'] = True
                data['boleta_id'] = None
                return JsonResponse(data, status=response.status_code)
            except Exception:
                return response
    except Exception as e:
        logger.exception(f"[dry_run preview] Error: {e}")
        return JsonResponse({
            'success': False,
            'message': f'Error en preview: {str(e)}'
        }, status=500)



# ═══════════════════════════════════════════════════════════════
# API · Check de duplicados (cliente + sorteo + fecha + numero + forma + monto + FP)
# ═══════════════════════════════════════════════════════════════
@login_required
@require_POST
def api_check_duplicados(request):
    """
    Recibe {items: [...], cliente_id, forma_pago_id, fecha_sorteo}.
    Devuelve lista de items que ya existen en BD para ese cliente+sorteo+fecha+FP.
    Un item es duplicado si coinciden: sorteo, numero, forma_juego, monto.
    """
    from decimal import Decimal, InvalidOperation
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError as e:
        return JsonResponse({'success': False, 'error': 'JSON invalido: ' + str(e)}, status=400)

    items = data.get('items') or []
    cliente_id = data.get('cliente_id')
    forma_pago_id = data.get('forma_pago_id')
    fecha_sorteo_str = data.get('fecha_sorteo')

    if not items or not cliente_id or not forma_pago_id or not fecha_sorteo_str:
        return JsonResponse({'success': True, 'duplicados': [], 'count': 0})

    try:
        cliente_id = int(cliente_id)
        forma_pago_id = int(forma_pago_id)
    except (ValueError, TypeError):
        return JsonResponse({'success': False, 'error': 'cliente_id/forma_pago_id invalidos'}, status=400)

    # Fecha
    try:
        from datetime import datetime as _dt
        fecha_sorteo = _dt.strptime(fecha_sorteo_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return JsonResponse({'success': False, 'error': 'fecha_sorteo invalida'}, status=400)

    # Mapeo tipo → forma_juego_id
    from jugadas.models import FormaJuego
    formas_map = {}
    for fj in FormaJuego.objects.filter(activo=True):
        formas_map[fj.nombre.lower()] = fj.id

    # Recolectar sorteos involucrados
    sorteo_ids = set()
    for it in items:
        sid = it.get('sorteo_id')
        if sid:
            try:
                sorteo_ids.add(int(sid))
            except (ValueError, TypeError):
                pass

    if not sorteo_ids:
        return JsonResponse({'success': True, 'duplicados': [], 'count': 0})

    # Traer existentes (solo los que importan)
    existentes = set()
    qs = Jugada.objects.filter(
        usuario_id=cliente_id,
        sorteo_id__in=sorteo_ids,
        fecha_sorteo=fecha_sorteo,
        forma_pago_id=forma_pago_id,
        estado__in=['confirmada', 'pendiente'],
    ).values_list('sorteo_id', 'numero', 'forma_juego_id', 'monto')

    for sid, num, fj_id, monto in qs:
        # Normalizar numero
        num_norm = str(num).strip().upper() if num is not None else ''
        # Normalizar monto a 2 decimales
        try:
            monto_norm = str(Decimal(str(monto)).quantize(Decimal('0.01')))
        except (InvalidOperation, ValueError, TypeError):
            monto_norm = str(monto)
        existentes.add((sid, num_norm, fj_id, monto_norm))

    # Comparar
    duplicados = []
    for it in items:
        tipo_norm = (it.get('tipo') or '').strip().lower()
        fj_id = formas_map.get(tipo_norm)
        if not fj_id:
            continue
        try:
            sid = int(it.get('sorteo_id') or 0)
        except (ValueError, TypeError):
            continue
        num_norm = str(it.get('numero', '')).strip().upper()
        try:
            monto_norm = str(Decimal(str(it.get('monto', 0))).quantize(Decimal('0.01')))
        except (InvalidOperation, ValueError, TypeError):
            monto_norm = str(it.get('monto', 0))

        key = (sid, num_norm, fj_id, monto_norm)
        if key in existentes:
            duplicados.append({
                'numero': it.get('numero'),
                'tipo': it.get('tipo'),
                'sorteo_id': sid,
                'monto': float(it.get('monto', 0)),
            })

    return JsonResponse({
        'success': True,
        'duplicados': duplicados,
        'count': len(duplicados),
    })

