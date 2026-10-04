# resultados/views.py
# -*- coding: utf-8 -*-
import logging
import re
from decimal import Decimal
from datetime import datetime, timedelta

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Q, Sum, Count
from django.utils import timezone
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST
from django.contrib.auth.models import User

try:
    from django_eventstream import send_event
except ImportError:
    send_event = None

from zoneinfo import ZoneInfo

from .models import Resultado, Premio
from .forms import ResultadoForm
from jugadas.models import Jugada
from sorteos.models import Sorteo
from sorteos.utils import get_hora_salida
from roles.models import Fondo, MovimientoFondo, Notificacion, Rol, Subordinacion
from roles.models import RelacionClienteGestor, RelacionComercialBanco

logger = logging.getLogger(__name__)

# ============================================================
# HELPERS DE PERMISOS
# ============================================================

def _es_superadmin(user):
    if not user or not user.is_authenticated:
        return False
    return user.is_superuser or user.roles.filter(tipo='superadmin', activo=True).exists()

def _es_banco(user):
    if not user or not user.is_authenticated:
        return False
    return user.roles.filter(tipo='banco', activo=True).exists()

def _es_comercial(user):
    if not user or not user.is_authenticated:
        return False
    return user.roles.filter(tipo='comercial', activo=True).exists()

def _es_auditor(user):
    if not user or not user.is_authenticated:
        return False
    return user.roles.filter(tipo='auditor', activo=True).exists()

def _puede_gestionar_resultados(user):
    return (_es_superadmin(user) or _es_banco(user) or _es_auditor(user))

# ============================================================
# NOTIFICACIONES
# ============================================================

def crear_notificacion(usuario, tipo, mensaje, datos=None):
    if not usuario:
        return
    Notificacion.objects.create(
        usuario=usuario,
        tipo=tipo,
        mensaje=mensaje,
        datos=datos or {},
        leido=False,
    )

# ============================================================
# CONFIGURACIÓN POR NOMBRE DE SORTEO
# ============================================================

def obtener_configuracion_por_nombre(sorteo):
    """
    Devuelve la config del sorteo con las claves que usa procesar_resultado.
    """
    if not isinstance(sorteo, Sorteo):
        try:
            sorteo = Sorteo.objects.get(nombre__iexact=sorteo, activo=True)
        except Sorteo.DoesNotExist:
            return {}

    cfg = {}
    try:
        from sorteos.utils import obtener_configuracion_sorteo as _obtener_cfg
        data = _obtener_cfg(sorteo)
        cfg = data.get('config', {}) or {}
    except Exception:
        cfg = {}

    if not cfg and hasattr(sorteo, 'get_configuracion'):
        try:
            cfg = sorteo.get_configuracion() or {}
        except Exception:
            cfg = {}

    return {
        'tiene_pick2': cfg.get('pick2', False),
        'tiene_pick3': cfg.get('pick3', False),
        'tiene_pick4': cfg.get('pick4', False),
        'tiene_pick5': cfg.get('pick5', False),
        'fijo_manual': cfg.get('fijo', False),
        'corrido1_manual': cfg.get('corridos', False),
        'corrido2_manual': cfg.get('corridos', False),
        'pick2': cfg.get('pick2', False),
        'pick3': cfg.get('pick3', False),
        'pick4': cfg.get('pick4', False),
        'pick5': cfg.get('pick5', False),
        'fijo': cfg.get('fijo', False),
        'corridos': cfg.get('corridos', False),
        'pf': cfg.get('pf', False),
        'parlet': cfg.get('parlet', False),
        'posicion': cfg.get('posicion', False),
        'tripleta': cfg.get('tripleta', False),
        'vspf': cfg.get('vspf', False),
        'vspick2': cfg.get('vspick2', False),
        'pick2vspf': cfg.get('pick2vspf', False),
    }

# ============================================================
# DERIVACIONES
# ============================================================

def generar_derivaciones_desde_campos(pick2, pick3, pick4, pick5, fijo, corrido_1, corrido_2):
    derivaciones = {}

    if pick2:
        derivaciones['pick2'] = pick2
    if pick3:
        derivaciones['pick3'] = pick3
    if pick4:
        derivaciones['pick4'] = pick4
    if pick5:
        derivaciones['pick5'] = pick5

    if pick3 and len(pick3) >= 2:
        derivaciones['pf'] = pick3[:2]
    elif pick2 and len(pick2) >= 2:
        derivaciones['pf'] = pick2

    if fijo:
        derivaciones['fijo'] = fijo
    elif pick3 and len(pick3) >= 2:
        derivaciones['fijo'] = pick3[-2:]

    if corrido_1:
        derivaciones['corrido_1'] = corrido_1
    elif pick4 and len(pick4) >= 2:
        derivaciones['corrido_1'] = pick4[:2]

    if corrido_2:
        derivaciones['corrido_2'] = corrido_2
    elif pick4 and len(pick4) >= 4:
        derivaciones['corrido_2'] = pick4[-2:]

    fijos = []
    corridos = []
    if derivaciones.get('fijo'):
        fijos.append(derivaciones['fijo'])
    if derivaciones.get('corrido_1'):
        corridos.append(derivaciones['corrido_1'])
    if derivaciones.get('corrido_2'):
        corridos.append(derivaciones['corrido_2'])

    derivaciones['fijos'] = fijos
    derivaciones['corridos'] = corridos

    parlets = set()
    for f in fijos:
        for c in corridos:
            if f != c:
                parlets.add(f"{f}x{c}")
                parlets.add(f"{c}x{f}")
    for i in range(len(fijos)):
        for j in range(i + 1, len(fijos)):
            parlets.add(f"{fijos[i]}x{fijos[j]}")
            parlets.add(f"{fijos[j]}x{fijos[i]}")
    for i in range(len(corridos)):
        for j in range(i + 1, len(corridos)):
            parlets.add(f"{corridos[i]}x{corridos[j]}")
            parlets.add(f"{corridos[j]}x{corridos[i]}")
    derivaciones['parlet_general'] = sorted(list(parlets))

    vspf = []
    pf = derivaciones.get('pf')
    if pf:
        for num in fijos + corridos:
            if pf != num:
                vspf.append(f"{pf}x{num}")
    derivaciones['vspf'] = sorted(vspf)

    vspick2 = []
    if pick2:
        for num in fijos + corridos:
            if pick2 != num:
                vspick2.append(f"{pick2}x{num}")
    derivaciones['vspick2'] = sorted(vspick2)

    if pf and pick2 and pf != pick2:
        derivaciones['pick2vspf'] = [f"{pf}x{pick2}"]
    else:
        derivaciones['pick2vspf'] = []

    c1 = derivaciones.get('corrido_1', '')
    c2 = derivaciones.get('corrido_2', '')
    if pick3 and len(pick3) == 3:
        if c1:
            derivaciones['centena_corrida_1'] = pick3[2] + c1
        if c2:
            d1 = int(pick3[0])
            d3 = int(pick3[2])
            suma = (d1 + d3) % 10
            derivaciones['centena_corrida_2'] = str(suma) + c2

    if fijos and corridos and len(corridos) >= 2:
        derivaciones['posicion'] = [f"{fijos[0]} {corridos[0]} {corridos[1]}"]
        derivaciones['tripleta'] = [f"{fijos[0]} {corridos[0]} {corridos[1]}"]
    else:
        derivaciones['posicion'] = []
        derivaciones['tripleta'] = []

    derivaciones['superparlet'] = []

    return derivaciones

# ============================================================
# JUGADA GANADORA
# ============================================================

def jugada_es_ganadora(jugada, resultado):
    # FIX_VALIDA_SORTEO_V1: jugada y resultado DEBEN ser del mismo sorteo y fecha
    if not jugada or not resultado:
        return False, 0
    if jugada.sorteo_id != resultado.sorteo_id:
        return False, 0
    if jugada.fecha_sorteo != resultado.fecha:
        return False, 0

    forma_raw = (jugada.forma_juego.nombre if jugada.forma_juego else '').strip().lower()
    forma = re.sub(r'[^a-z0-9]', '', forma_raw)  # normalizar: 'pick 2' -> 'pick2'
    numero = str(jugada.numero or '').strip()
    derivados = resultado.derivados or {}

    if not derivados:
        return False, 0

    from roles.utils import get_dosis_gestor
    try:
        multiplicador = int(get_dosis_gestor(
            jugada.destinatario,
            jugada.sorteo,
            jugada.forma_juego,
            jugada.forma_pago,
        ))
    except Exception:
        multiplicador = 0

    if multiplicador <= 0:
        return False, 0

    def n(v):
        return str(v or '').strip()

    parlet_list = [n(x) for x in (derivados.get('parlet_general') or [])]
    fijos_list = [n(x) for x in (derivados.get('fijos') or [])]
    corridos_list = [n(x) for x in (derivados.get('corridos') or [])]
    posicion_list = [n(x) for x in (derivados.get('posicion') or [])]
    tripleta_list = [n(x) for x in (derivados.get('tripleta') or [])]
    vspf_list = [n(x) for x in (derivados.get('vspf') or [])]
    vspick2_list = [n(x) for x in (derivados.get('vspick2') or [])]
    pick2vspf_list = [n(x) for x in (derivados.get('pick2vspf') or [])]
    superparlet_list = [n(x) for x in (derivados.get('superparlet') or [])]

    pick2_val = n(derivados.get('pick2'))
    pick3_val = n(derivados.get('pick3'))
    pick4_val = n(derivados.get('pick4'))
    pick5_val = n(derivados.get('pick5'))
    pf_val = n(derivados.get('pf'))
    fijo_val = n(derivados.get('fijo'))
    corrido_1_val = n(derivados.get('corrido_1'))
    corrido_2_val = n(derivados.get('corrido_2'))
    centena_1_val = n(derivados.get('centena_corrida_1'))
    centena_2_val = n(derivados.get('centena_corrida_2'))

    # ─── FIJO ───
    if forma in ('fijo', 'fijos'):
        if numero == fijo_val or numero in fijos_list:
            return True, multiplicador
        return False, 0

    # ─── CORRIDOS ───
    if forma in ('corridos', 'corrido1', 'corrido2', 'corrido'):
        if numero == corrido_1_val or numero == corrido_2_val or numero in corridos_list:
            return True, multiplicador

        if numero == fijo_val and numero not in corridos_list:
            try:
                from roles.utils import gestor_paga_fijo_como_corrido
                if gestor_paga_fijo_como_corrido(jugada.destinatario):
                    return True, multiplicador
            except ImportError as e:
                logger.error(
                    f"[CRITICAL] Falta gestor_paga_fijo_como_corrido en roles.utils: {e}",
                    exc_info=True,
                )
            except Exception as e:
                logger.exception(
                    f"[ERROR] evaluando corridos-como-fijo para jugada #{jugada.id}: {e}"
                )

        return False, 0

    # ─── PICK 2 ───
    if forma in ('pick2',):
        if numero == pick2_val:
            return True, multiplicador
        return False, 0

    # ─── PICK 3 ───
    if forma in ('pick3',):
        if numero == pick3_val:
            return True, multiplicador
        return False, 0

    # ─── PICK 4 ───
    if forma in ('pick4',):
        if numero == pick4_val:
            return True, multiplicador
        return False, 0

    # ─── PICK 5 ───
    if forma in ('pick5',):
        if numero == pick5_val:
            return True, multiplicador
        return False, 0

    # ─── PF ───
    if forma in ('pf',):
        if numero == pf_val:
            return True, multiplicador
        return False, 0

    # ─── PARLET (y candado) ───
    if forma in ('parlet', 'candado'):
        if numero in parlet_list:
            return True, multiplicador
        return False, 0

    # ─── SUPER PARLET ───
    if forma in ('superparlet',):
        if numero in superparlet_list:
            return True, multiplicador
        return False, 0

    # ─── POSICIÓN (FIX_POSICION_V1: respeta la posición apostada) ───
    if forma in ('posicion', 'posiciones'):
        meta = jugada.metadata or {}
        orig = meta.get('original') or {}
        pos_apostada = orig.get('posicion') if isinstance(orig, dict) else None
        if pos_apostada is None:
            pos_apostada = meta.get('posicion')

        if pos_apostada is not None:
            try:
                idx = int(pos_apostada) - 1  # 1-based -> 0-based
            except (ValueError, TypeError):
                logger.warning(f'[FIX_POSICION_V1] jugada #{jugada.id} posicion invalida: {pos_apostada!r}')
                return False, 0
            if idx < 0 or idx >= len(posicion_list):
                return False, 0
            if posicion_list[idx] == numero:
                return True, multiplicador
            return False, 0

        # Fallback legacy (sin metadata de posicion)
        logger.warning(f'[FIX_POSICION_V1] jugada #{jugada.id} sin metadata de posicion — fallback legacy')
        if numero in posicion_list:
            return True, multiplicador
        return False, 0

    # ─── TRIPLETA ───
    if forma in ('tripleta',):
        if numero in tripleta_list:
            return True, multiplicador
        return False, 0

    # ─── VS PF ───
    if forma in ('vspf',):
        if numero in vspf_list:
            return True, multiplicador
        return False, 0

    # ─── VS PICK2 ───
    if forma in ('vspick2',):
        if numero in vspick2_list:
            return True, multiplicador
        return False, 0

    # ─── PICK2 VS PF ───
    if forma in ('pick2vspf',):
        if numero in pick2vspf_list:
            return True, multiplicador
        return False, 0

    # ─── CENTENAS CORRIDAS ───
    if forma in ('centenacorrida', 'centenacorrida1', 'centenacorrida2', 'centenascorridas'):
        if numero == centena_1_val or numero == centena_2_val:
            return True, multiplicador
        return False, 0

    return False, 0

# ============================================================
# PROCESAR RESULTADO
# ============================================================

def procesar_resultado(request, datos, resultado_existente=None):
    sorteo = datos['sorteo']
    fecha = datos['fecha']
    hora = datos['hora']
    config = obtener_configuracion_por_nombre(sorteo)

    pick2 = datos.get('pick2', '').strip()
    pick3 = datos.get('pick3', '').strip()
    pick4 = datos.get('pick4', '').strip()
    pick5 = datos.get('pick5', '').strip()
    fijo = datos.get('fijo', '').strip()
    corrido_1 = datos.get('corrido_1', '').strip()
    corrido_2 = datos.get('corrido_2', '').strip()
    pf = datos.get('pf', '').strip()
    centena_corrida_1 = datos.get('centena_corrida_1', '').strip()
    centena_corrida_2 = datos.get('centena_corrida_2', '').strip()
    parlet = datos.get('parlet', '').strip()
    posicion = datos.get('posicion', '').strip()
    tripleta = datos.get('tripleta', '').strip()
    vspf = datos.get('vspf', '').strip()
    vspick2 = datos.get('vspick2', '').strip()
    pick2vspf = datos.get('pick2vspf', '').strip()
    superparlet = datos.get('superparlet', '').strip()

    def validar_pick(valor, longitud, nombre):
        if valor:
            if not valor.isdigit() or len(valor) != longitud:
                raise ValueError(f"{nombre} debe tener exactamente {longitud} dígitos numéricos.")
        return valor

    if config.get('tiene_pick2'):
        pick2 = validar_pick(pick2, 2, "Pick 2")
    if config.get('tiene_pick3'):
        pick3 = validar_pick(pick3, 3, "Pick 3")
    if config.get('tiene_pick4'):
        pick4 = validar_pick(pick4, 4, "Pick 4")
    if config.get('tiene_pick5'):
        pick5 = validar_pick(pick5, 5, "Pick 5")

    if config.get('fijo_manual') and not fijo:
        raise ValueError("El campo Fijo es obligatorio para este sorteo.")
    if config.get('corrido1_manual') and not corrido_1:
        raise ValueError("El campo Corrido 1 es obligatorio para este sorteo.")
    if config.get('corrido2_manual') and not corrido_2:
        raise ValueError("El campo Corrido 2 es obligatorio para este sorteo.")

    if not resultado_existente:
        if Resultado.objects.filter(sorteo=sorteo, fecha=fecha).exists():
            raise ValueError(f"Ya existe un resultado para {sorteo.nombre} en {fecha.strftime('%d/%m/%Y')}.")
    else:
        duplicado = Resultado.objects.filter(sorteo=sorteo, fecha=fecha).exclude(id=resultado_existente.id).exists()
        if duplicado:
            raise ValueError(f"Ya existe otro resultado para {sorteo.nombre} en {fecha.strftime('%d/%m/%Y')}.")

    derivaciones = generar_derivaciones_desde_campos(pick2, pick3, pick4, pick5, fijo, corrido_1, corrido_2)

    if pf and (pick2 or pick3):
        derivaciones['pf'] = pf
    else:
        derivaciones.pop('pf', None)

    if fijo:
        derivaciones['fijo'] = fijo
    if corrido_1:
        derivaciones['corrido_1'] = corrido_1
    if corrido_2:
        derivaciones['corrido_2'] = corrido_2
    if centena_corrida_1:
        derivaciones['centena_corrida_1'] = centena_corrida_1
    if centena_corrida_2:
        derivaciones['centena_corrida_2'] = centena_corrida_2
    if parlet:
        derivaciones['parlet_general'] = [p.strip() for p in parlet.split() if p.strip()]
    if posicion:
        derivaciones['posicion'] = [p.strip() for p in posicion.split() if p.strip()]
    if tripleta:
        derivaciones['tripleta'] = [p.strip() for p in tripleta.split() if p.strip()]
    if vspf:
        derivaciones['vspf'] = [p.strip() for p in vspf.split() if p.strip()]
    if vspick2:
        derivaciones['vspick2'] = [p.strip() for p in vspick2.split() if p.strip()]
    if pick2vspf:
        derivaciones['pick2vspf'] = [p.strip() for p in pick2vspf.split() if p.strip()]

    parlet_value = '  '.join(derivaciones.get('parlet_general', []))
    posicion_value = ' '.join(derivaciones.get('posicion', []))
    tripleta_value = ' '.join(derivaciones.get('tripleta', []))
    vspf_value = '  '.join(derivaciones.get('vspf', []))
    vspick2_value = '  '.join(derivaciones.get('vspick2', []))
    pick2vspf_value = '  '.join(derivaciones.get('pick2vspf', []))

    numero_ganador = pick3 or pick4 or pick2 or pick5 or derivaciones.get('pf') or derivaciones.get('fijo') or '-'

    with transaction.atomic():
        if resultado_existente:
            historial = resultado_existente.metadata.get('historial', [])
            historial.append({
                'fecha': timezone.now().isoformat(),
                'usuario': request.user.username,
                'cambios': {
                    'sorteo_anterior': resultado_existente.sorteo.id,
                    'fecha_anterior': resultado_existente.fecha.isoformat(),
                    'hora_anterior': resultado_existente.hora.isoformat(),
                    'pick2_anterior': resultado_existente.pick2,
                    'pick3_anterior': resultado_existente.pick3,
                    'pick4_anterior': resultado_existente.pick4,
                    'pick5_anterior': resultado_existente.pick5,
                    'fijo_anterior': resultado_existente.fijo,
                    'corrido_1_anterior': resultado_existente.corrido_1,
                    'corrido_2_anterior': resultado_existente.corrido_2,
                },
            })
            resultado_existente.sorteo = sorteo
            resultado_existente.fecha = fecha
            resultado_existente.hora = hora
            resultado_existente.pick2 = pick2
            resultado_existente.pick3 = pick3
            resultado_existente.pick4 = pick4
            resultado_existente.pick5 = pick5
            resultado_existente.pf = derivaciones.get('pf', '')
            resultado_existente.fijo = derivaciones.get('fijo', '')
            resultado_existente.corrido_1 = derivaciones.get('corrido_1', '')
            resultado_existente.corrido_2 = derivaciones.get('corrido_2', '')
            resultado_existente.centena_corrida_1 = derivaciones.get('centena_corrida_1', '')
            resultado_existente.centena_corrida_2 = derivaciones.get('centena_corrida_2', '')
            resultado_existente.parlet = parlet_value
            resultado_existente.posicion = posicion_value
            resultado_existente.tripleta = tripleta_value
            resultado_existente.vspf = vspf_value
            resultado_existente.vspick2 = vspick2_value
            resultado_existente.pick2vspf = pick2vspf_value
            resultado_existente.numero_ganador = numero_ganador
            resultado_existente.derivados = derivaciones
            resultado_existente.metadata['campos_base'] = {
                'pick2': pick2, 'pick3': pick3, 'pick4': pick4, 'pick5': pick5,
                'fijo': derivaciones.get('fijo', ''),
                'corrido_1': derivaciones.get('corrido_1', ''),
                'corrido_2': derivaciones.get('corrido_2', ''),
                'posicion': derivaciones.get('posicion', []),
                'tripleta': derivaciones.get('tripleta', []),
            }
            resultado_existente.metadata['historial'] = historial
            resultado_existente.save()
            resultado = resultado_existente
        else:
            resultado = Resultado.objects.create(
                sorteo=sorteo, fecha=fecha, hora=hora, creado_por=request.user,
                pick2=pick2, pick3=pick3, pick4=pick4, pick5=pick5,
                pf=derivaciones.get('pf', ''),
                fijo=derivaciones.get('fijo', ''),
                corrido_1=derivaciones.get('corrido_1', ''),
                corrido_2=derivaciones.get('corrido_2', ''),
                centena_corrida_1=derivaciones.get('centena_corrida_1', ''),
                centena_corrida_2=derivaciones.get('centena_corrida_2', ''),
                parlet=parlet_value,
                posicion=posicion_value,
                tripleta=tripleta_value,
                vspf=vspf_value,
                vspick2=vspick2_value,
                pick2vspf=pick2vspf_value,
                numero_ganador=numero_ganador,
                derivados=derivaciones,
                metadata={
                    'campos_base': {
                        'pick2': pick2, 'pick3': pick3, 'pick4': pick4, 'pick5': pick5,
                        'fijo': derivaciones.get('fijo', ''),
                        'corrido_1': derivaciones.get('corrido_1', ''),
                        'corrido_2': derivaciones.get('corrido_2', ''),
                        'posicion': derivaciones.get('posicion', []),
                        'tripleta': derivaciones.get('tripleta', []),
                    }
                },
            )

        premios_anteriores = Premio.objects.filter(
            jugada__sorteo=resultado.sorteo,
            metadata__resultado_id=resultado.id,
        )
        for p_ant in premios_anteriores:
            try:
                fp_ant = p_ant.jugada.forma_pago if p_ant.jugada else None
                if fp_ant and p_ant.jugada.usuario:
                    f_ant = Fondo.objects.filter(
                        usuario=p_ant.jugada.usuario,
                        forma_pago=fp_ant,
                        activo=True,
                    ).first()
                    if f_ant:
                        saldo_ant_r = f_ant.monto
                        f_ant.monto -= p_ant.monto_premio
                        f_ant.save(update_fields=['monto', 'actualizado_en'])
                        try:
                            MovimientoFondo.objects.create(
                                emisor=None,
                                receptor=p_ant.jugada.usuario,
                                forma_pago=fp_ant,
                                monto=-p_ant.monto_premio,
                                tipo='ajuste',
                                estado='confirmado',
                                motivo='Reversion premio #' + str(p_ant.id),
                                saldo_antes=saldo_ant_r,
                                saldo_despues=f_ant.monto,
                                datos_transferencia={
                                    'premio_id': p_ant.id,
                                    'resultado_id': resultado.id,
                                    'reversion': True,
                                },
                            )
                        except Exception:
                            pass
            except Exception as e:
                logger.warning(f"No se pudo revertir Fondo del premio #{p_ant.id}: {e}")

        premios_anteriores.delete()

        jugadas = Jugada.objects.filter(
            sorteo=resultado.sorteo,
            fecha_sorteo=resultado.fecha,
            estado__in=['confirmada', 'pendiente'],
        ).select_related('usuario', 'forma_pago', 'forma_juego')

        premios_generados = 0
        for jugada in jugadas:
            es_ganadora, multiplicador = jugada_es_ganadora(jugada, resultado)
            if es_ganadora:
                monto_premio = jugada.monto * Decimal(multiplicador)
                jugada.estado = 'ganadora'
                jugada.monto_premio = monto_premio
                jugada.save(update_fields=['estado', 'monto_premio', 'actualizado_en'])
                premio, created = Premio.objects.get_or_create(
                    jugada=jugada,
                    metadata__resultado_id=resultado.id,
                    defaults={
                        'monto_premio': monto_premio,
                        'multiplicador_aplicado': multiplicador,
                        'estado': 'pendiente',
                        'cobrado': False,
                        'metadata': {'resultado_id': resultado.id},
                    },
                )
                if created:
                    premios_generados += 1

                    cliente = jugada.usuario
                    gestor = jugada.destinatario or cliente
                    forma_pago = jugada.forma_pago
                    descuento_postpago = Decimal('0.00')

                    if forma_pago:
                        from roles.utils import _aplicar_ingreso_a_fondo
                        monto_al_fondo, descuento_postpago = _aplicar_ingreso_a_fondo(
                            cliente=cliente,
                            gestor=gestor,
                            forma_pago=forma_pago,
                            monto=premio.monto_premio,
                        )

                        premio.cobrado = True
                        premio.estado = 'pagado'
                        premio.fecha_pago = timezone.now()
                        premio.pagado_por = request.user
                        premio.save(update_fields=['cobrado', 'estado', 'fecha_pago', 'pagado_por'])

                        _fp_pre = Fondo.objects.filter(
                            usuario=cliente, forma_pago=forma_pago, activo=True
                        ).first()
                        _saldo_pre = _fp_pre.monto if _fp_pre else Decimal('0.00')
                        MovimientoFondo.objects.create(
                            emisor=None, receptor=cliente,
                            forma_pago=forma_pago, monto=premio.monto_premio,
                            tipo='premio', estado='confirmado',
                            motivo=f"Premio {resultado.sorteo.nombre} · jugada #{jugada.id}",
                            saldo_antes=_saldo_pre - monto_al_fondo,
                            saldo_despues=_saldo_pre,
                            datos_transferencia={
                                'tipo': 'premio_automatico',
                                'premio_id': premio.id,
                                'jugada_id': jugada.id,
                                'sorteo': resultado.sorteo.nombre,
                                'postpago_descontado': float(descuento_postpago),
                                'fecha': timezone.now().isoformat(),
                            },
                            nota=(
                                f"Premio automático por jugada #{jugada.id}"
                                + (f" (postpago descontado: ${descuento_postpago})" if descuento_postpago > 0 else "")
                            ),
                        )

                    msg_premio = f"🎉 ¡Has ganado ${premio.monto_premio} en {resultado.sorteo.nombre}!"
                    if descuento_postpago > 0:
                        msg_premio += f" (Se descontaron ${descuento_postpago} de tu postpago)"
                    msg_premio += " El premio ya está en tu saldo."

                    crear_notificacion(
                        usuario=jugada.usuario,
                        tipo='premio',
                        mensaje=msg_premio,
                        datos={
                            'premio_id': premio.id,
                            'monto': float(premio.monto_premio),
                            'postpago_descontado': float(descuento_postpago),
                            'sorteo': resultado.sorteo.nombre,
                            'fecha': timezone.now().isoformat(),
                            'url_detalle': '/resultados/mis-premios/',
                        },
                    )

        if send_event is not None:
            try:
                evento_tipo = 'nuevo_resultado' if not resultado_existente else 'resultado_actualizado'
                send_event('resultados', evento_tipo, {
                    'id': resultado.id,
                    'sorteo': resultado.sorteo.nombre,
                    'numero_ganador': numero_ganador,
                    'fecha': resultado.fecha.strftime('%d/%m/%Y'),
                    'hora': resultado.hora.strftime('%H:%M'),
                })
            except Exception as e:
                logger.warning(f"No se pudo emitir evento: {str(e)}")

        return resultado, premios_generados

# ============================================================
# VISTAS
# ============================================================

@login_required
def crear_resultado(request):
    user = request.user
    if not _puede_gestionar_resultados(user):
        messages.error(request, "No tienes permisos para crear resultados.")
        return redirect('publico:home')

    fecha_actual = timezone.localtime(timezone.now()).date()
    sorteo_id = request.POST.get('sorteo') if request.method == 'POST' else request.GET.get('sorteo')
    sorteo_seleccionado = None
    if sorteo_id:
        try:
            sorteo_seleccionado = Sorteo.objects.get(id=sorteo_id, activo=True)
        except Sorteo.DoesNotExist:
            pass

    if request.method == 'GET':
        sorteos_con_resultado = Resultado.objects.filter(fecha=fecha_actual).values_list('sorteo_id', flat=True)
        sorteos_disponibles = Sorteo.objects.filter(activo=True).exclude(id__in=sorteos_con_resultado).order_by('nombre')

        form = ResultadoForm(initial={'sorteo': sorteo_seleccionado.id if sorteo_seleccionado else None})
        form.fields['sorteo'].queryset = sorteos_disponibles

        context = {
            'form': form,
            'today': fecha_actual,
            'now': timezone.localtime(timezone.now()),
            'sorteo_seleccionado': sorteo_seleccionado,
            'sorteos_disponibles': sorteos_disponibles,
        }
        return render(request, 'resultados/crear_resultado.html', context)

    if request.method == 'POST':
        sorteo_id = request.POST.get('sorteo')
        fecha_str = request.POST.get('fecha')
        hora_str = request.POST.get('hora')

        if not all([sorteo_id, fecha_str, hora_str]):
            messages.error(request, "Todos los campos obligatorios deben estar llenos.")
            form = ResultadoForm(request.POST)
            return render(request, 'resultados/crear_resultado.html', {
                'form': form,
                'today': fecha_actual,
                'now': timezone.localtime(timezone.now()),
                'sorteo_seleccionado': None,
            })

        try:
            with transaction.atomic():
                sorteo = Sorteo.objects.select_for_update().get(id=sorteo_id, activo=True)
                fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
                hora = datetime.strptime(hora_str, '%H:%M').time()

                if fecha > timezone.localtime(timezone.now()).date():
                    messages.error(request, "No se puede crear un resultado para una fecha futura.")
                    form = ResultadoForm(request.POST)
                    return render(request, 'resultados/crear_resultado.html', {
                        'form': form,
                        'today': fecha_actual,
                        'now': timezone.localtime(timezone.now()),
                        'sorteo_seleccionado': sorteo,
                    })

                if Resultado.objects.filter(sorteo=sorteo, fecha=fecha, hora=hora).exists():
                    messages.warning(request, f"⚠️ Ya existe un resultado para {sorteo.nombre} en {fecha.strftime('%d/%m/%Y')} a las {hora.strftime('%H:%M')}.")
                    return redirect('resultados:resultados')

                datos = {
                    'sorteo': sorteo, 'fecha': fecha, 'hora': hora,
                    'pick2': request.POST.get('pick2', ''),
                    'pick3': request.POST.get('pick3', ''),
                    'pick4': request.POST.get('pick4', ''),
                    'pick5': request.POST.get('pick5', ''),
                    'fijo': request.POST.get('fijo', ''),
                    'corrido_1': request.POST.get('corrido_1', ''),
                    'corrido_2': request.POST.get('corrido_2', ''),
                    'pf': request.POST.get('pf', ''),
                    'centena_corrida_1': request.POST.get('centena_corrida_1', ''),
                    'centena_corrida_2': request.POST.get('centena_corrida_2', ''),
                    'parlet': request.POST.get('parlet', ''),
                    'posicion': request.POST.get('posicion', ''),
                    'tripleta': request.POST.get('tripleta', ''),
                    'vspf': request.POST.get('vspf', ''),
                    'vspick2': request.POST.get('vspick2', ''),
                    'pick2vspf': request.POST.get('pick2vspf', ''),
                }

                resultado, premios_generados = procesar_resultado(request, datos)
                messages.success(request, f"✅ Resultado para {sorteo.nombre} creado exitosamente. {premios_generados} premios generados.")
                return redirect('resultados:detalle_resultado', resultado_id=resultado.id)

        except ValueError as e:
            messages.error(request, f"❌ Error de validación: {str(e)}")
            form = ResultadoForm(request.POST)
            return render(request, 'resultados/crear_resultado.html', {
                'form': form,
                'today': fecha_actual,
                'now': timezone.localtime(timezone.now()),
                'sorteo_seleccionado': sorteo_seleccionado,
            })

        except Exception as e:
            logger.error(f"Error al crear resultado: {str(e)}", exc_info=True)
            messages.error(request, f"❌ Error al crear el resultado: {str(e)}")
            form = ResultadoForm(request.POST)
            return render(request, 'resultados/crear_resultado.html', {
                'form': form,
                'today': fecha_actual,
                'now': timezone.localtime(timezone.now()),
                'sorteo_seleccionado': sorteo_seleccionado,
            })

def resultados_view(request):
    resultados = Resultado.objects.all().select_related('sorteo').order_by('fecha', 'sorteo__hora_salida', 'hora')

    sorteo_id = request.GET.get('sorteo')
    if sorteo_id:
        resultados = resultados.filter(sorteo_id=sorteo_id)

    fecha_actual = timezone.localtime(timezone.now()).date()
    fecha_desde_str = request.GET.get('fecha_desde')
    fecha_hasta_str = request.GET.get('fecha_hasta')

    tiene_filtro_fecha = bool(fecha_desde_str or fecha_hasta_str)

    if not tiene_filtro_fecha:
        resultados = resultados.filter(fecha=fecha_actual)
        fecha_desde_obj = fecha_actual
        fecha_hasta_obj = fecha_actual
        mostrando_hoy = True
    else:
        fecha_desde_obj = None
        if fecha_desde_str:
            try:
                fecha_desde_obj = datetime.strptime(fecha_desde_str, '%Y-%m-%d').date()
                resultados = resultados.filter(fecha__gte=fecha_desde_obj)
            except ValueError:
                fecha_desde_obj = None
        fecha_hasta_obj = None
        if fecha_hasta_str:
            try:
                fecha_hasta_obj = datetime.strptime(fecha_hasta_str, '%Y-%m-%d').date()
                resultados = resultados.filter(fecha__lte=fecha_hasta_obj)
            except ValueError:
                fecha_hasta_obj = None
        mostrando_hoy = False

    paginator = Paginator(resultados, 20)
    page = request.GET.get('page')
    resultados_page = paginator.get_page(page)

    sorteos = Sorteo.objects.filter(activo=True).order_by('id')

    user = request.user
    if user.is_authenticated:
        puede_editar = _puede_gestionar_resultados(user)
        puede_eliminar = _puede_gestionar_resultados(user)
    else:
        puede_editar = False
        puede_eliminar = False

    context = {
        'resultados': resultados_page,
        'sorteos': sorteos,
        'sorteo_seleccionado': sorteo_id,
        'fecha_desde': fecha_desde_obj.strftime('%Y-%m-%d') if fecha_desde_obj else '',
        'fecha_hasta': fecha_hasta_obj.strftime('%Y-%m-%d') if fecha_hasta_obj else '',
        'fecha_actual': fecha_actual,
        'tiene_filtro_fecha': tiene_filtro_fecha,
        'total_resultados': resultados.count(),
        'mostrando_hoy': mostrando_hoy,
        'puede_editar': puede_editar,
        'puede_eliminar': puede_eliminar,
    }
    return render(request, 'resultados/resultados.html', context)

def detalle_resultado(request, resultado_id):
    resultado = get_object_or_404(Resultado, id=resultado_id)

    premios = Premio.objects.filter(
        jugada__sorteo=resultado.sorteo,
        metadata__resultado_id=resultado.id,
    ).select_related('jugada', 'jugada__usuario', 'jugada__forma_juego')

    total_ganadores = premios.count()
    monto_total_premios = sum(p.monto_premio for p in premios)

    for premio in premios:
        if request.user.is_authenticated:
            premio.es_mio = (premio.jugada.usuario == request.user)
        else:
            premio.es_mio = False

    puede_editar = _puede_gestionar_resultados(request.user)

    context = {
        'resultado': resultado,
        'premios': premios,
        'total_ganadores': total_ganadores,
        'monto_total_premios': monto_total_premios,
        'puede_editar': puede_editar,
    }
    return render(request, 'resultados/detalle_resultado.html', context)

@login_required
def editar_resultado(request, resultado_id):
    resultado = get_object_or_404(Resultado, id=resultado_id)

    if not _puede_gestionar_resultados(request.user):
        messages.error(request, "No tienes permisos para editar resultados.")
        return redirect('resultados:resultados')

    config = obtener_configuracion_por_nombre(resultado.sorteo)

    if request.method == 'GET':
        todos_sorteos = Sorteo.objects.filter(activo=True).order_by('nombre')
        form = ResultadoForm(instance=resultado)
        context = {
            'form': form,
            'resultado': resultado,
            'config': config,
            'today': timezone.localtime(timezone.now()).date(),
            'now': timezone.localtime(timezone.now()),
            'sorteo_seleccionado': resultado.sorteo,
            'todos_sorteos': todos_sorteos,
            'editando': True,
        }
        return render(request, 'resultados/editar_resultado.html', context)

    if request.method == 'POST':
        try:
            with transaction.atomic():
                nuevo_sorteo_id = request.POST.get('sorteo')
                nueva_fecha_str = request.POST.get('fecha')
                nueva_hora_str = request.POST.get('hora')

                if not all([nuevo_sorteo_id, nueva_fecha_str, nueva_hora_str]):
                    raise ValueError("Todos los campos obligatorios deben estar llenos.")

                nuevo_sorteo = Sorteo.objects.select_for_update().get(id=nuevo_sorteo_id, activo=True)
                nueva_fecha = datetime.strptime(nueva_fecha_str, '%Y-%m-%d').date()
                nueva_hora = datetime.strptime(nueva_hora_str, '%H:%M').time()

                duplicado = Resultado.objects.filter(
                    sorteo=nuevo_sorteo, fecha=nueva_fecha, hora=nueva_hora,
                ).exclude(id=resultado.id).exists()

                if duplicado:
                    raise ValueError(f"Ya existe un resultado para {nuevo_sorteo.nombre} en {nueva_fecha.strftime('%d/%m/%Y')} a las {nueva_hora.strftime('%H:%M')}.")

                datos = {
                    'sorteo': nuevo_sorteo, 'fecha': nueva_fecha, 'hora': nueva_hora,
                    'pick2': request.POST.get('pick2', ''),
                    'pick3': request.POST.get('pick3', ''),
                    'pick4': request.POST.get('pick4', ''),
                    'pick5': request.POST.get('pick5', ''),
                    'fijo': request.POST.get('fijo', ''),
                    'corrido_1': request.POST.get('corrido_1', ''),
                    'corrido_2': request.POST.get('corrido_2', ''),
                    'pf': request.POST.get('pf', ''),
                    'centena_corrida_1': request.POST.get('centena_corrida_1', ''),
                    'centena_corrida_2': request.POST.get('centena_corrida_2', ''),
                    'parlet': request.POST.get('parlet', ''),
                    'posicion': request.POST.get('posicion', ''),
                    'tripleta': request.POST.get('tripleta', ''),
                    'vspf': request.POST.get('vspf', ''),
                    'vspick2': request.POST.get('vspick2', ''),
                    'pick2vspf': request.POST.get('pick2vspf', ''),
                }

                resultado_actualizado, premios_generados = procesar_resultado(
                    request, datos, resultado_existente=resultado,
                )

                messages.success(
                    request,
                    f"✅ Resultado actualizado correctamente. Se regeneraron {premios_generados} premios.",
                )
                return redirect('resultados:detalle_resultado', resultado_id=resultado.id)

        except ValueError as e:
            messages.error(request, f"❌ Error de validación: {str(e)}")
            todos_sorteos = Sorteo.objects.filter(activo=True).order_by('nombre')
            form = ResultadoForm(request.POST, instance=resultado)
            context = {
                'form': form,
                'resultado': resultado,
                'config': config,
                'today': timezone.localtime(timezone.now()).date(),
                'now': timezone.localtime(timezone.now()),
                'sorteo_seleccionado': resultado.sorteo,
                'todos_sorteos': todos_sorteos,
                'editando': True,
            }
            return render(request, 'resultados/editar_resultado.html', context)

        except Exception as e:
            logger.error(f"Error al editar resultado {resultado.id}: {str(e)}", exc_info=True)
            messages.error(request, f"❌ Error al actualizar: {str(e)}")
            return redirect('resultados:detalle_resultado', resultado_id=resultado.id)

@login_required
def eliminar_resultado(request, resultado_id):
    resultado = get_object_or_404(Resultado, id=resultado_id)

    if not _puede_gestionar_resultados(request.user):
        messages.error(request, "No tienes permisos para eliminar resultados.")
        return redirect('resultados:resultados')

    if request.method == 'POST':
        sorteo_nombre = resultado.sorteo.nombre
        Premio.objects.filter(jugada__sorteo=resultado.sorteo, metadata__resultado_id=resultado.id).delete()
        resultado.delete()
        messages.success(request, f"✅ Resultado de {sorteo_nombre} eliminado correctamente.")
        return redirect('resultados:resultados')

    context = {'resultado': resultado}
    return render(request, 'resultados/eliminar_resultado.html', context)

@login_required
def mis_premios(request):
    from collections import OrderedDict
    from datetime import timedelta as _td

    user = request.user
    es_superadmin = _es_superadmin(user)
    es_banco = _es_banco(user)
    es_comercial = _es_comercial(user)
    es_cliente = not (es_superadmin or es_banco or es_comercial)

    premios = Premio.objects.select_related(
        'jugada', 'jugada__sorteo', 'jugada__usuario',
        'jugada__forma_juego', 'jugada__forma_pago',
    ).order_by('-creado_en')

    if es_superadmin:
        pass
    elif es_banco:
        comerciales_ids = list(Subordinacion.objects.filter(
            jefe=user, activo=True,
        ).values_list('subordinado_id', flat=True))
        premios = premios.filter(
            Q(jugada__destinatario=user) |
            Q(jugada__destinatario_id__in=comerciales_ids) |
            Q(jugada__usuario=user)
        )
    elif es_comercial:
        premios = premios.filter(
            Q(jugada__destinatario=user) |
            Q(jugada__usuario=user)
        )
    else:
        mis_gestores = set()
        mis_gestores.update(
            Fondo.objects.filter(usuario=user, activo=True)
            .exclude(asignado_por__isnull=True)
            .values_list('asignado_por_id', flat=True)
        )
        mis_gestores.update(
            Subordinacion.objects.filter(subordinado=user, activo=True)
            .values_list('jefe_id', flat=True)
        )
        mis_gestores.update(
            RelacionClienteGestor.objects.filter(cliente=user, activo=True)
            .values_list('gestor_id', flat=True)
        )
        mis_gestores = list(mis_gestores)
        premios = premios.filter(
            Q(jugada__destinatario_id__in=mis_gestores) |
            Q(jugada__usuario=user)
        )

    sorteo_id = request.GET.get('sorteo')
    fj_id = request.GET.get('forma_juego')
    fp_id = request.GET.get('forma_pago')
    estado = request.GET.get('estado')
    periodo = request.GET.get('periodo', '')
    if not periodo and not request.GET.get('fecha_desde') and not request.GET.get('fecha_hasta'):
        periodo = 'hoy'
    fecha_desde_str = request.GET.get('fecha_desde')
    fecha_hasta_str = request.GET.get('fecha_hasta')

    if sorteo_id:
        premios = premios.filter(jugada__sorteo_id=sorteo_id)
    if fj_id:
        premios = premios.filter(jugada__forma_juego_id=fj_id)
    if fp_id:
        premios = premios.filter(jugada__forma_pago_id=fp_id)
    if estado == 'pendiente':
        premios = premios.filter(cobrado=False)
    elif estado == 'cobrado':
        premios = premios.filter(cobrado=True)

    hoy = timezone.localdate()
    hace_7 = hoy - _td(days=7)
    hace_30 = hoy - _td(days=30)

    if periodo == 'hoy':
        premios = premios.filter(creado_en__date=hoy)
    elif periodo == '7d':
        premios = premios.filter(creado_en__date__gte=hace_7)
    elif periodo == '30d':
        premios = premios.filter(creado_en__date__gte=hace_30)

    if fecha_desde_str:
        try:
            premios = premios.filter(creado_en__date__gte=datetime.strptime(fecha_desde_str, '%Y-%m-%d').date())
        except ValueError:
            pass
    if fecha_hasta_str:
        try:
            premios = premios.filter(creado_en__date__lte=datetime.strptime(fecha_hasta_str, '%Y-%m-%d').date())
        except ValueError:
            pass

    premios_base = Premio.objects.select_related('jugada', 'jugada__usuario')
    if es_superadmin:
        pass
    elif es_banco:
        premios_base = premios_base.filter(
            Q(jugada__destinatario=user) |
            Q(jugada__destinatario_id__in=comerciales_ids) |
            Q(jugada__usuario=user)
        )
    elif es_comercial:
        premios_base = premios_base.filter(
            Q(jugada__destinatario=user) |
            Q(jugada__usuario=user)
        )
    else:
        premios_base = premios_base.filter(
            Q(jugada__destinatario_id__in=mis_gestores) |
            Q(jugada__usuario=user)
        )

    total_hoy = premios_base.filter(creado_en__date=hoy).aggregate(t=Sum('monto_premio'))['t'] or 0
    total_7d = premios_base.filter(creado_en__date__gte=hace_7).aggregate(t=Sum('monto_premio'))['t'] or 0
    total_30d = premios_base.filter(creado_en__date__gte=hace_30).aggregate(t=Sum('monto_premio'))['t'] or 0
    total_historico = premios_base.aggregate(t=Sum('monto_premio'))['t'] or 0
    cantidad_hoy = premios_base.filter(creado_en__date=hoy).count()

    sorteos_dict = OrderedDict()
    for p in premios.order_by('-jugada__fecha_sorteo', 'jugada__sorteo__nombre', 'jugada__usuario__username'):
        sid = p.jugada.sorteo_id
        if sid not in sorteos_dict:
            sorteos_dict[sid] = {
                'sorteo': p.jugada.sorteo,
                'fecha_sorteo': p.jugada.fecha_sorteo,
                'lineas': [],
            }
        sorteos_dict[sid]['lineas'].append({
            'cliente': p.jugada.usuario.username,
            'numero': p.jugada.numero,
            'forma_juego': p.jugada.forma_juego.nombre if p.jugada.forma_juego else '—',
            'forma_pago': p.jugada.forma_pago.nombre if p.jugada.forma_pago else '—',
            'apuesta': p.jugada.monto,
            'premio': p.monto_premio or Decimal('0.00'),
            'cobrado': p.cobrado,
        })

    from collections import OrderedDict as _OD
    _sort_ids = set()
    _fechas = set()
    for _sid, _g in sorteos_dict.items():
        _sort_ids.add(_sid)
        if _g.get('fecha_sorteo'):
            _fechas.add(_g['fecha_sorteo'])
    _res_map = {}
    if _sort_ids and _fechas:
        for _r in Resultado.objects.filter(sorteo_id__in=_sort_ids, fecha__in=_fechas):
            _res_map[(_r.sorteo_id, _r.fecha)] = _r

    grupos_lista = []
    for _k, g in sorteos_dict.items():
        g['total_sorteo'] = sum((l['premio'] for l in g['lineas']), Decimal('0.00'))
        g['cantidad_premios'] = len(g['lineas'])
        g['resultado'] = _res_map.get((_k, g.get('fecha_sorteo')))

        _nums_prem = set()
        for _l in g['lineas']:
            _n = str(_l.get('numero') or '').strip()
            if _n:
                _nums_prem.add(_n)
                if 'x' in _n.lower():
                    for _part in _n.lower().split('x'):
                        _part = _part.strip()
                        if _part:
                            _nums_prem.add(_part)
        g['numeros_premiados'] = _nums_prem

        _gan = _OD()
        for _l in g['lineas']:
            _cid = _l.get('cliente_id') or _l.get('cliente')
            if _cid not in _gan:
                _gan[_cid] = {
                    'cliente': _l.get('cliente'),
                    'formas': [],
                    'total_premio': Decimal('0.00'),
                    'total_apuesta': Decimal('0.00'),
                }
            _gan[_cid]['formas'].append({
                'forma_juego': _l.get('forma_juego'),
                'forma_pago': _l.get('forma_pago'),
                'numero': _l.get('numero'),
                'apuesta': _l.get('apuesta') or Decimal('0.00'),
                'premio': _l.get('premio') or Decimal('0.00'),
            })
            _gan[_cid]['total_premio'] += (_l.get('premio') or Decimal('0.00'))
            _gan[_cid]['total_apuesta'] += (_l.get('apuesta') or Decimal('0.00'))
        g['ganadores'] = list(_gan.values())

        _tf = _OD()
        for _l in g['lineas']:
            _fp = _l.get('forma_pago') or 'Sin FP'
            _tf[_fp] = _tf.get(_fp, Decimal('0.00')) + (_l.get('premio') or Decimal('0.00'))
        g['totales_fp'] = list(_tf.items())

        grupos_lista.append(g)

    total_premios = premios.aggregate(t=Sum('monto_premio'))['t'] or 0
    premios_cobrados = premios.filter(cobrado=True).count()
    premios_pendientes = premios.filter(cobrado=False).count()

    sorteos = Sorteo.objects.filter(activo=True).order_by('nombre')
    try:
        from jugadas.models import FormaJuego
        formas_juego = FormaJuego.objects.filter(activo=True).order_by('nombre')
    except Exception:
        formas_juego = []
    try:
        from pagos.models import FormaPago
        formas_pago = FormaPago.objects.filter(activo=True).order_by('nombre')
    except Exception:
        formas_pago = []

    context = {
        'grupos': grupos_lista,
        'total_premios': total_premios,
        'premios_cobrados': premios_cobrados,
        'premios_pendientes': premios_pendientes,
        'total_hoy': total_hoy,
        'total_7d': total_7d,
        'total_30d': total_30d,
        'total_historico': total_historico,
        'cantidad_hoy': cantidad_hoy,
        'sorteos': sorteos,
        'formas_juego': formas_juego,
        'formas_pago': formas_pago,
        'sorteo_seleccionado': sorteo_id,
        'forma_juego_seleccionada': fj_id,
        'forma_pago_seleccionada': fp_id,
        'estado_seleccionado': estado,
        'periodo_seleccionado': periodo,
        'fecha_desde': fecha_desde_str or '',
        'fecha_hasta': fecha_hasta_str or '',
        'es_superadmin': es_superadmin,
        'es_banco': es_banco,
        'es_comercial': es_comercial,
        'es_cliente': es_cliente,
    }
    return render(request, 'resultados/mis_premios.html', context)

@login_required
def solicitar_cobro(request, premio_id):
    premio = get_object_or_404(Premio, id=premio_id, jugada__usuario=request.user)

    if premio.cobrado or premio.estado == 'pagado':
        messages.info(
            request,
            f"✅ Este premio de ${premio.monto_premio} ya fue acreditado automáticamente a tu saldo."
        )
        return redirect('resultados:mis_premios')

    forma_pago = getattr(premio.jugada, 'forma_pago', None)
    if not forma_pago:
        messages.error(request, "La jugada no tiene forma de pago asociada.")
        return redirect('resultados:mis_premios')

    if request.method == 'POST':
        premio.cobrado = True
        premio.estado = 'pagado'
        premio.fecha_pago = timezone.now()
        premio.pagado_por = request.user
        premio.save()

        from roles.utils import _aplicar_ingreso_a_fondo
        monto_al_fondo, descuento_postpago = _aplicar_ingreso_a_fondo(
            cliente=request.user,
            gestor=request.user,
            forma_pago=forma_pago,
            monto=premio.monto_premio,
        )
        monto_neto = monto_al_fondo

        MovimientoFondo.objects.create(
            emisor=None, receptor=request.user,
            forma_pago=forma_pago, monto=monto_neto,
            tipo='premio', estado='confirmado',
            datos_transferencia={
                'tipo': 'cobro_premio',
                'premio_id': premio.id,
                'monto_bruto': float(premio.monto_premio),
                'postpago_descontado': float(descuento_postpago),
                'monto_neto': float(monto_neto),
                'fecha': timezone.now().isoformat(),
                'mensaje': f"Cobro de premio #{premio.id}",
            },
            nota=f"Premio por jugada #{premio.jugada.id}" + (
                f" (postpago descontado: ${descuento_postpago})" if descuento_postpago > 0 else ""
            ),
        )

        mensaje_premio = f"💰 Has cobrado ${monto_neto} por tu premio en {premio.jugada.sorteo.nombre}."
        if descuento_postpago > 0:
            mensaje_premio += f" (Se descontaron ${descuento_postpago} de postpago pendiente)"

        crear_notificacion(
            usuario=request.user, tipo='premio',
            mensaje=mensaje_premio,
            datos={
                'premio_id': premio.id,
                'monto_bruto': float(premio.monto_premio),
                'monto_neto': float(monto_neto),
                'postpago_descontado': float(descuento_postpago),
                'sorteo': premio.jugada.sorteo.nombre,
                'fecha_pago': premio.fecha_pago.isoformat(),
                'url_detalle': '/resultados/mis-premios/',
            },
        )

        msg_final = f"✅ Premio de ${premio.monto_premio} cobrado exitosamente."
        if descuento_postpago > 0:
            msg_final += f" Postpago descontado: ${descuento_postpago}."
        messages.success(request, msg_final)
        return redirect('resultados:mis_premios')

    context = {'premio': premio}
    return render(request, 'resultados/solicitar_cobro.html', context)

@login_required
def todos_los_ganadores(request):
    user = request.user

    es_superadmin = _es_superadmin(user)
    es_banco = _es_banco(user)
    es_comercial = _es_comercial(user)
    es_cliente = not (es_superadmin or es_banco or es_comercial)

    try:
        from resultados.reconciliacion import reconciliar_premio_jugada
        from resultados.models import Resultado
        from jugadas.models import Jugada
        _hoy = timezone.localdate()
        _hace7 = _hoy - __import__('datetime').timedelta(days=7)
        _q = Jugada.objects.filter(
            fecha_sorteo__gte=_hace7,
            estado__in=['confirmada', 'pendiente'],
        ).exclude(estado='ganadora')[:300]
        for _j in _q:
            _r = Resultado.objects.filter(sorteo_id=_j.sorteo_id, fecha=_j.fecha_sorteo).first()
            if _r:
                reconciliar_premio_jugada(_j, resultado=_r, usuario_sistema=user)
    except Exception as _e:
        logger.warning(f'Reconciliacion en vista: {_e}')

    premios = Premio.objects.select_related(
        'jugada', 'jugada__sorteo', 'jugada__usuario',
        'jugada__forma_juego', 'jugada__forma_pago',
    ).order_by('-creado_en')

    if es_superadmin:
        default_tab = 'todos'
    elif es_banco:
        default_tab = 'clientes'
    elif es_comercial:
        default_tab = 'clientes'
    else:
        default_tab = 'grupo'

    tab = request.GET.get('tab', default_tab)
    asignado_por = request.GET.get('asignado_por')

    sorteo_id = request.GET.get('sorteo')
    if sorteo_id:
        premios = premios.filter(jugada__sorteo_id=sorteo_id)

    forma_juego_id = request.GET.get('forma_juego')
    if forma_juego_id:
        premios = premios.filter(jugada__forma_juego_id=forma_juego_id)

    forma_pago_id = request.GET.get('forma_pago')
    if forma_pago_id:
        premios = premios.filter(jugada__forma_pago_id=forma_pago_id)

    usuario_busqueda = request.GET.get('usuario')
    if usuario_busqueda:
        premios = premios.filter(jugada__usuario__username__icontains=usuario_busqueda)

    hoy = timezone.localdate()
    fecha_desde_str = request.GET.get('fecha_desde')
    fecha_hasta_str = request.GET.get('fecha_hasta')
    mostrando_hoy = False
    if not fecha_desde_str and not fecha_hasta_str:
        fecha_desde_str = hoy.strftime('%Y-%m-%d')
        fecha_hasta_str = hoy.strftime('%Y-%m-%d')
        premios = premios.filter(creado_en__date=hoy)
        mostrando_hoy = True
    else:
        if fecha_desde_str:
            try:
                fecha_desde = datetime.strptime(fecha_desde_str, '%Y-%m-%d').date()
                premios = premios.filter(creado_en__date__gte=fecha_desde)
            except ValueError:
                pass
        if fecha_hasta_str:
            try:
                fecha_hasta = datetime.strptime(fecha_hasta_str, '%Y-%m-%d').date()
                premios = premios.filter(creado_en__date__lte=fecha_hasta)
            except ValueError:
                pass

    estado = request.GET.get('estado')
    if estado == 'pendiente':
        premios = premios.filter(cobrado=False)
    elif estado == 'cobrado':
        premios = premios.filter(cobrado=True)

    if es_superadmin:
        if tab == 'bancos':
            ids = Rol.objects.filter(tipo='banco', activo=True).values_list('usuario_id', flat=True)
            premios = premios.filter(jugada__usuario__id__in=ids)
        elif tab == 'comerciales':
            ids = Rol.objects.filter(tipo='comercial', activo=True).values_list('usuario_id', flat=True)
            premios = premios.filter(jugada__usuario__id__in=ids)
        elif tab == 'clientes':
            ids = Rol.objects.filter(tipo='cliente', activo=True).values_list('usuario_id', flat=True)
            premios = premios.filter(jugada__usuario__id__in=ids)
        elif tab == 'mis_comerciales' and asignado_por:
            ids = RelacionComercialBanco.objects.filter(
                asignado_por_id=asignado_por,
            ).values_list('comercial_id', flat=True)
            premios = premios.filter(jugada__usuario__id__in=ids)

    elif es_banco:
        if tab == 'comerciales':
            ids = RelacionComercialBanco.objects.filter(
                banco=user, activo=True,
            ).values_list('comercial_id', flat=True)
            premios = premios.filter(jugada__usuario__id__in=ids)
        elif tab == 'clientes':
            ids = RelacionClienteGestor.objects.filter(
                gestor=user, tipo_gestor='banco', activo=True,
            ).values_list('cliente_id', flat=True)
            premios = premios.filter(jugada__usuario__id__in=ids)
        else:
            comerciales_ids = RelacionComercialBanco.objects.filter(
                banco=user, activo=True,
            ).values_list('comercial_id', flat=True)
            clientes_ids = RelacionClienteGestor.objects.filter(
                gestor=user, tipo_gestor='banco', activo=True,
            ).values_list('cliente_id', flat=True)
            todos_ids = list(comerciales_ids) + list(clientes_ids) + [user.id]
            premios = premios.filter(jugada__usuario__id__in=todos_ids)

    elif es_comercial:
        if tab == 'clientes':
            ids = RelacionClienteGestor.objects.filter(
                gestor=user, tipo_gestor='comercial', activo=True,
            ).values_list('cliente_id', flat=True)
            premios = premios.filter(jugada__usuario__id__in=ids)
        elif tab == 'propios':
            premios = premios.filter(jugada__usuario=user)
        else:
            ids = RelacionClienteGestor.objects.filter(
                gestor=user, tipo_gestor='comercial', activo=True,
            ).values_list('cliente_id', flat=True)
            premios = premios.filter(jugada__usuario__id__in=ids)

    else:
        if tab == 'propios':
            premios = premios.filter(jugada__usuario=user)
        else:
            mis_gestores_ids = RelacionClienteGestor.objects.filter(
                cliente=user, activo=True,
            ).values_list('gestor_id', flat=True)
            companeros_ids = RelacionClienteGestor.objects.filter(
                gestor_id__in=mis_gestores_ids, activo=True,
            ).values_list('cliente_id', flat=True)
            todos_ids = set(companeros_ids) | {user.id}
            premios = premios.filter(jugada__usuario__id__in=todos_ids)

    por_forma_juego = list(
        premios.values(
            'jugada__forma_juego__id',
            'jugada__forma_juego__nombre',
        ).annotate(
            total=Sum('monto_premio'),
            cantidad=Count('id'),
        ).order_by('-total')
    )

    por_forma_pago = list(
        premios.values(
            'jugada__forma_pago__id',
            'jugada__forma_pago__nombre',
        ).annotate(
            total=Sum('monto_premio'),
            cantidad=Count('id'),
        ).order_by('-total')
    )

    por_cliente = list(
        premios.values(
            'jugada__usuario__id',
            'jugada__usuario__username',
        ).annotate(
            total=Sum('monto_premio'),
            cantidad=Count('id'),
            pendientes=Count('id', filter=Q(cobrado=False)),
            cobrados=Count('id', filter=Q(cobrado=True)),
        ).order_by('-total')
    )

    max_forma_juego = max([f['total'] for f in por_forma_juego], default=0) or 1
    max_forma_pago = max([f['total'] for f in por_forma_pago], default=0) or 1
    max_cliente = max([c['total'] for c in por_cliente], default=0) or 1

    agg_total = premios.aggregate(t=Sum('monto_premio'))['t'] or 0
    total_premios_monto = agg_total
    total_premios_count = premios.count()
    pendientes_count = premios.filter(cobrado=False).count()
    cobrados_count = premios.filter(cobrado=True).count()

    paginator = Paginator(premios, 25)
    premios_page = paginator.get_page(request.GET.get('page'))

    sorteos = Sorteo.objects.filter(activo=True).order_by('nombre')

    try:
        from jugadas.models import FormaJuego
    except ImportError as e:
        logger.warning(f"No se pudo importar FormaJuego: {e}")
        FormaJuego = None

    try:
        from pagos.models import FormaPago
    except ImportError as e:
        logger.warning(f"No se pudo importar FormaPago: {e}")
        FormaPago = None

    formas_juego = []
    formas_pago = []

    if FormaJuego is not None:
        try:
            formas_juego = list(FormaJuego.objects.all().order_by('nombre'))
        except Exception as e:
            logger.warning(f"Error cargando FormaJuego: {e}")

    if FormaPago is not None:
        try:
            formas_pago = list(FormaPago.objects.all().order_by('nombre'))
        except Exception as e:
            logger.warning(f"Error cargando FormaPago: {e}")

    if not formas_juego:
        vistos = set()
        for p in Premio.objects.select_related('jugada__forma_juego')[:500]:
            fj = getattr(p.jugada, 'forma_juego', None)
            if fj and fj.id not in vistos:
                vistos.add(fj.id)
                formas_juego.append(fj)

    if not formas_pago:
        vistos = set()
        for p in Premio.objects.select_related('jugada__forma_pago')[:500]:
            fp = getattr(p.jugada, 'forma_pago', None)
            if fp and fp.id not in vistos:
                vistos.add(fp.id)
                formas_pago.append(fp)

    tabs_available = []
    if es_superadmin:
        tabs_available = [
            {'id': 'todos', 'label': 'Todos'},
            {'id': 'bancos', 'label': 'Bancos'},
            {'id': 'comerciales', 'label': 'Comerciales'},
            {'id': 'clientes', 'label': 'Clientes'},
            {'id': 'mis_comerciales', 'label': 'Mis Comerciales', 'params': {'asignado_por': user.id}},
        ]
    elif es_banco:
        tabs_available = [
            {'id': 'clientes', 'label': 'Mis Clientes Directos'},
            {'id': 'comerciales', 'label': 'Mis Comerciales'},
            {'id': 'todos', 'label': 'Todos'},
        ]
    elif es_comercial:
        tabs_available = [
            {'id': 'clientes', 'label': 'Mis Clientes'},
            {'id': 'propios', 'label': 'Mis Premios'},
        ]
    else:
        tabs_available = [
            {'id': 'grupo', 'label': 'Mi grupo'},
            {'id': 'propios', 'label': 'Mis premios'},
        ]

    context = {
        'premios': premios_page,
        'por_forma_juego': por_forma_juego,
        'por_forma_pago': por_forma_pago,
        'por_cliente': por_cliente,
        'max_forma_juego': max_forma_juego,
        'max_forma_pago': max_forma_pago,
        'max_cliente': max_cliente,
        'total_premios_monto': total_premios_monto,
        'total_premios_count': total_premios_count,
        'pendientes_count': pendientes_count,
        'cobrados_count': cobrados_count,
        'sorteos': sorteos,
        'formas_juego': formas_juego,
        'formas_pago': formas_pago,
        'sorteo_seleccionado': sorteo_id,
        'forma_juego_seleccionada': forma_juego_id,
        'forma_pago_seleccionada': forma_pago_id,
        'fecha_desde': fecha_desde_str,
        'fecha_hasta': fecha_hasta_str,
        'estado_seleccionado': estado,
        'usuario_busqueda': usuario_busqueda,
        'hoy': hoy,
        'mostrando_hoy': mostrando_hoy,
        'tab_actual': tab,
        'tabs_available': tabs_available,
        'es_superadmin': es_superadmin,
        'es_banco': es_banco,
        'es_comercial': es_comercial,
        'es_cliente': es_cliente,
        'asignado_por': asignado_por,
    }
    return render(request, 'resultados/ganadores.html', context)

# ============================================================
# APIS
# ============================================================

def api_sorteos_disponibles(request):
    fecha_str = request.GET.get('fecha')
    if not fecha_str:
        return JsonResponse({'error': 'Fecha requerida'}, status=400)

    try:
        fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'error': 'Fecha inválida'}, status=400)

    CUBA_TZ = ZoneInfo('America/Havana')
    ahora_local = datetime.now(CUBA_TZ)
    hoy = ahora_local.date()
    hora_actual = ahora_local.time()

    ids_con_resultado = Resultado.objects.filter(fecha=fecha).values_list('sorteo_id', flat=True)

    base_qs = Sorteo.objects.filter(
        activo=True,
    ).exclude(id__in=ids_con_resultado).order_by('nombre')

    sorteos_filtrados = []
    for s in base_qs:
        hora_salida = get_hora_salida(s, fecha)
        if not hora_salida:
            continue

        if fecha < hoy:
            sorteos_filtrados.append((s, hora_salida))
        elif fecha == hoy:
            if hora_salida <= hora_actual:
                sorteos_filtrados.append((s, hora_salida))

    sorteos_filtrados.sort(key=lambda x: x[1])

    data = []
    for s, hora in sorteos_filtrados:
        data.append({
            'id': s.id,
            'nombre': s.nombre,
            'hora_salida': hora.strftime('%H:%M'),
        })

    return JsonResponse(data, safe=False)

def api_resultados_recientes(request):
    sorteo_id = request.GET.get('sorteo_id')
    resultados = Resultado.objects.all().order_by('-fecha', '-hora')
    if sorteo_id:
        resultados = resultados.filter(sorteo_id=sorteo_id)
    resultados = resultados[:10]

    data = {'resultados': []}
    for r in resultados:
        numero_ganador = r.derivados.get('pick3') or r.derivados.get('pick4') or r.derivados.get('pick2') or ''
        data['resultados'].append({
            'id': r.id,
            'sorteo': r.sorteo.nombre,
            'numero_ganador': numero_ganador,
            'fecha': r.fecha.isoformat(),
            'hora': r.hora.strftime('%H:%M'),
        })

    return JsonResponse(data, safe=False)

def api_configuracion_sorteo(request):
    sorteo_id = request.GET.get('sorteo_id')
    if not sorteo_id:
        return JsonResponse({'error': 'Falta sorteo_id'}, status=400)

    try:
        sorteo = Sorteo.objects.get(id=sorteo_id, activo=True)
    except Sorteo.DoesNotExist:
        return JsonResponse({'error': 'Sorteo no encontrado'}, status=404)

    config = obtener_configuracion_por_nombre(sorteo)
    return JsonResponse({'success': True, 'config': config})

@login_required
def api_premios_por_resultado(request, resultado_id):
    resultado = get_object_or_404(Resultado, id=resultado_id)
    user = request.user

    premios = Premio.objects.filter(
        jugada__sorteo=resultado.sorteo,
        metadata__resultado_id=resultado.id,
    ).select_related('jugada', 'jugada__usuario', 'jugada__forma_juego')

    es_superadmin = _es_superadmin(user)
    es_banco = _es_banco(user)
    es_comercial = _es_comercial(user)

    if not (es_superadmin or es_banco or es_comercial):
        premios = premios.filter(jugada__usuario=user)
    elif es_comercial:
        clientes_ids = RelacionClienteGestor.objects.filter(
            gestor=user, tipo_gestor='comercial', activo=True,
        ).values_list('cliente_id', flat=True)
        premios = premios.filter(jugada__usuario__id__in=clientes_ids)
    elif es_banco:
        clientes_ids = RelacionClienteGestor.objects.filter(
            gestor=user, tipo_gestor='banco', activo=True,
        ).values_list('cliente_id', flat=True)
        premios = premios.filter(jugada__usuario__id__in=clientes_ids)

    data = []
    for p in premios:
        data.append({
            'id': p.id,
            'usuario': p.jugada.usuario.username,
            'monto': float(p.monto_premio),
            'multiplicador': p.multiplicador_aplicado,
            'numero': p.jugada.numero,
            'forma_juego': p.jugada.forma_juego.nombre,
            'estado': p.estado,
            'cobrado': p.cobrado,
            'fecha': p.creado_en.strftime('%d/%m/%Y %H:%M'),
        })

    return JsonResponse({'success': True, 'premios': data})

@login_required
def api_resumen_resultado(request, resultado_id):
    resultado = get_object_or_404(Resultado, id=resultado_id)

    hora = resultado.sorteo.hora_salida.strftime('%H:%M') if resultado.sorteo.hora_salida else (
        resultado.hora.strftime('%H:%M') if resultado.hora else '—'
    )

    lines = []
    lines.append("🎰 *LOTTOBOOM — RESULTADO* 🎰")
    lines.append("")
    lines.append(f"📅 *{resultado.fecha.strftime('%d/%m/%Y')}*")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"🎯 *{resultado.sorteo.nombre}* · {hora}")
    lines.append("")

    principales = []
    if resultado.pick2: principales.append(f"P2: *{resultado.pick2}*")
    if resultado.pick3: principales.append(f"P3: *{resultado.pick3}*")
    if resultado.pick4: principales.append(f"P4: *{resultado.pick4}*")
    if resultado.pick5: principales.append(f"P5: *{resultado.pick5}*")
    if resultado.pf:    principales.append(f"PF: *{resultado.pf}*")
    if resultado.fijo:  principales.append(f"F: *{resultado.fijo}*")
    if resultado.corrido_1: principales.append(f"C1: *{resultado.corrido_1}*")
    if resultado.corrido_2: principales.append(f"C2: *{resultado.corrido_2}*")

    if principales:
        lines.append("   " + " · ".join(principales))
    else:
        lines.append("   —")

    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("🔗 https://lottoboom.pythonanywhere.com")
    lines.append("🍀 ¡Juega ya en LottoBooM! 🍀")

    return JsonResponse({'success': True, 'resumen': "\n".join(lines)})

@login_required
@require_POST
def api_guardar_resultado(request):
    try:
        if not _puede_gestionar_resultados(request.user):
            return JsonResponse({'success': False, 'error': 'No tienes permisos.'}, status=403)

        sorteo_id = request.POST.get('sorteo')
        fecha_str = request.POST.get('fecha')
        hora_str = request.POST.get('hora')

        if not all([sorteo_id, fecha_str, hora_str]):
            return JsonResponse({'success': False, 'error': 'Faltan campos obligatorios.'}, status=400)

        with transaction.atomic():
            sorteo = Sorteo.objects.select_for_update().get(id=sorteo_id, activo=True)
            fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
            hora = datetime.strptime(hora_str, '%H:%M').time()

            if fecha > timezone.localtime(timezone.now()).date():
                return JsonResponse({'success': False, 'error': 'No se puede crear un resultado para una fecha futura.'}, status=400)

            if Resultado.objects.filter(sorteo=sorteo, fecha=fecha, hora=hora).exists():
                return JsonResponse({'success': False, 'error': f'Ya existe un resultado para {sorteo.nombre} en esta fecha y hora.'}, status=400)

            datos = {
                'sorteo': sorteo, 'fecha': fecha, 'hora': hora,
                'pick2': request.POST.get('pick2', ''),
                'pick3': request.POST.get('pick3', ''),
                'pick4': request.POST.get('pick4', ''),
                'pick5': request.POST.get('pick5', ''),
                'fijo': request.POST.get('fijo', ''),
                'corrido_1': request.POST.get('corrido_1', ''),
                'corrido_2': request.POST.get('corrido_2', ''),
                'pf': request.POST.get('pf', ''),
                'centena_corrida_1': request.POST.get('centena_corrida_1', ''),
                'centena_corrida_2': request.POST.get('centena_corrida_2', ''),
                'parlet': request.POST.get('parlet', ''),
                'posicion': request.POST.get('posicion', ''),
                'tripleta': request.POST.get('tripleta', ''),
                'vspf': request.POST.get('vspf', ''),
                'vspick2': request.POST.get('vspick2', ''),
                'pick2vspf': request.POST.get('pick2vspf', ''),
            }

            resultado, premios_generados = procesar_resultado(request, datos)

            return JsonResponse({
                'success': True,
                'id': resultado.id,
                'message': f'✅ Resultado para {sorteo.nombre} creado exitosamente. {premios_generados} premios generados.',
            })

    except ValueError as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
    except Exception as e:
        logger.error(f"Error al guardar resultado via API: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'error': 'Error interno al guardar el resultado.'}, status=500)

@login_required
def api_resumen_filtrado(request):
    sorteo_id = request.GET.get('sorteo')
    fecha_desde_str = request.GET.get('fecha_desde')
    fecha_hasta_str = request.GET.get('fecha_hasta')

    resultados = Resultado.objects.select_related('sorteo').order_by(
        'fecha', 'sorteo__hora_salida', 'hora'
    )

    if sorteo_id:
        resultados = resultados.filter(sorteo_id=sorteo_id)

    if fecha_desde_str:
        try:
            fecha_desde = datetime.strptime(fecha_desde_str, '%Y-%m-%d').date()
            resultados = resultados.filter(fecha__gte=fecha_desde)
        except ValueError:
            pass

    if fecha_hasta_str:
        try:
            fecha_hasta = datetime.strptime(fecha_hasta_str, '%Y-%m-%d').date()
            resultados = resultados.filter(fecha__lte=fecha_hasta)
        except ValueError:
            pass

    if not (fecha_desde_str or fecha_hasta_str):
        fecha_actual = timezone.localtime(timezone.now()).date()
        resultados = resultados.filter(fecha=fecha_actual)

    if not resultados.exists():
        return JsonResponse({'success': True, 'resumen': '❌ No hay resultados para los filtros seleccionados.'})

    from collections import OrderedDict
    por_fecha = OrderedDict()
    for r in resultados:
        if r.fecha not in por_fecha:
            por_fecha[r.fecha] = []
        por_fecha[r.fecha].append(r)

    lines = []
    lines.append("🎰 *LOTTOBOOM — RESULTADOS* 🎰")
    lines.append("")

    for fecha, rs in por_fecha.items():
        lines.append(f"📅 *{fecha.strftime('%d/%m/%Y')}*")
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        for r in rs:
            hora = r.sorteo.hora_salida.strftime('%H:%M') if r.sorteo.hora_salida else (r.hora.strftime('%H:%M') if r.hora else '—')
            lines.append(f"🎯 *{r.sorteo.nombre}* · {hora}")

            principales = []
            if r.pick2: principales.append(f"P2: *{r.pick2}*")
            if r.pick3: principales.append(f"P3: *{r.pick3}*")
            if r.pick4: principales.append(f"P4: *{r.pick4}*")
            if r.pick5: principales.append(f"P5: *{r.pick5}*")
            if r.pf:    principales.append(f"PF: *{r.pf}*")
            if r.fijo:  principales.append(f"F: *{r.fijo}*")
            if r.corrido_1: principales.append(f"C1: *{r.corrido_1}*")
            if r.corrido_2: principales.append(f"C2: *{r.corrido_2}*")

            if principales:
                lines.append("   " + " · ".join(principales))
            else:
                lines.append("   —")

            lines.append("")

    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("🔗 https://lottoboom.pythonanywhere.com")
    lines.append("🍀 ¡Juega ya en LottoBooM! 🍀")

    resumen = "\n".join(lines)
    return JsonResponse({'success': True, 'resumen': resumen})

@login_required
def api_premios_sorteo(request):
    from collections import OrderedDict
    sorteo_id = request.GET.get('sorteo_id')
    fecha_str = request.GET.get('fecha')

    if not sorteo_id or not fecha_str:
        return JsonResponse({'success': False, 'error': 'Faltan parametros'}, status=400)

    try:
        sorteo = Sorteo.objects.get(id=sorteo_id)
    except Sorteo.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Sorteo no encontrado'}, status=404)

    try:
        fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'success': False, 'error': 'Fecha invalida'}, status=400)

    user = request.user
    es_superadmin = _es_superadmin(user)
    es_banco = _es_banco(user)
    es_comercial = _es_comercial(user)

    premios = Premio.objects.filter(
        jugada__sorteo=sorteo,
        jugada__fecha_sorteo=fecha,
    ).select_related('jugada', 'jugada__usuario', 'jugada__forma_juego', 'jugada__forma_pago')

    if es_superadmin:
        pass
    elif es_banco:
        comerciales_ids = list(Subordinacion.objects.filter(jefe=user, activo=True).values_list('subordinado_id', flat=True))
        premios = premios.filter(
            Q(jugada__destinatario=user) |
            Q(jugada__destinatario_id__in=comerciales_ids)
        )
    elif es_comercial:
        premios = premios.filter(jugada__destinatario=user)
    else:
        mis_gestores = set()
        mis_gestores.update(Fondo.objects.filter(usuario=user, activo=True).exclude(asignado_por__isnull=True).values_list('asignado_por_id', flat=True))
        mis_gestores.update(Subordinacion.objects.filter(subordinado=user, activo=True).values_list('jefe_id', flat=True))
        premios = premios.filter(Q(jugada__usuario=user) | Q(jugada__destinatario_id__in=mis_gestores))

    resultado = Resultado.objects.filter(sorteo=sorteo, fecha=fecha).first()

    por_cliente = OrderedDict()
    for p in premios:
        cid = p.jugada.usuario_id
        if cid not in por_cliente:
            por_cliente[cid] = {
                'cliente': p.jugada.usuario.username,
                'formas': [],
                'total': Decimal('0.00'),
            }
        por_cliente[cid]['formas'].append({
            'forma_juego': p.jugada.forma_juego.nombre if p.jugada.forma_juego else '-',
            'forma_pago': p.jugada.forma_pago.nombre if p.jugada.forma_pago else '-',
            'numero': p.jugada.numero,
            'apuesta': p.jugada.monto,
            'premio': p.monto_premio,
        })
        por_cliente[cid]['total'] += p.monto_premio

    lineas = []
    lineas.append("🎰 *GANADORES - " + sorteo.nombre + "*")
    lineas.append("📅 " + fecha.strftime('%d/%m/%Y'))
    lineas.append("")

    if resultado:
        principales = []
        if resultado.pick2: principales.append("P2: *" + str(resultado.pick2) + "*")
        if resultado.pick3: principales.append("P3: *" + str(resultado.pick3) + "*")
        if resultado.pick4: principales.append("P4: *" + str(resultado.pick4) + "*")
        if resultado.pick5: principales.append("P5: *" + str(resultado.pick5) + "*")
        if not principales:
            if resultado.fijo: principales.append("F: *" + str(resultado.fijo) + "*")
            if resultado.corrido_1: principales.append("C1: *" + str(resultado.corrido_1) + "*")
            if resultado.corrido_2: principales.append("C2: *" + str(resultado.corrido_2) + "*")
        if principales:
            lineas.append("🎯 " + " · ".join(principales))
            lineas.append("")

    lineas.append("━━━━━━━━━━━━━━━━━━━━")
    lineas.append("🏆 *GANADORES*")
    lineas.append("")

    total_general = Decimal('0.00')
    for c in por_cliente.values():
        lineas.append("👤 *" + c['cliente'] + "*")
        for f in c['formas']:
            lineas.append("   " + str(f['numero']) + " · " + str(f['forma_juego']) + " · $" + str(f['apuesta']) + " → $" + str(f['premio']))
        if len(c['formas']) > 1:
            lineas.append("   💰 Total: *$" + str(c['total']) + "*")
        lineas.append("")
        total_general += c['total']

    lineas.append("━━━━━━━━━━━━━━━━━━━━")
    lineas.append("💵 *TOTAL: $" + str(total_general) + "*")
    lineas.append("")
    lineas.append("🔗 https://lottoboom.pythonanywhere.com")

    return JsonResponse({'success': True, 'resumen': "\n".join(lineas)})