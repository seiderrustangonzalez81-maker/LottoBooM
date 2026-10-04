# roles/services.py
# -*- coding: utf-8 -*-
"""
Servicio de cuadres diarios.
Incluye lógica de comisión con snapshot: el % aplicado a un cuadre queda
congelado en el momento de su creación y no cambia aunque se modifique
la configuración del usuario después.
"""
from decimal import Decimal
from collections import defaultdict

from django.contrib.auth.models import User
from django.db.models import Sum
from django.utils import timezone
from zoneinfo import ZoneInfo

from .models import (
    CuadreDiario,
    Subordinacion,
    Rol,
    ConfiguracionComision,
)
from jugadas.models import Jugada
from pagos.models import FormaPago

CUBA_TZ = ZoneInfo("America/Havana")


def _hoy_cuba():
    """Fecha actual según hora de Cuba."""
    return timezone.now().astimezone(CUBA_TZ).date()


# ============================================================
# CÁLCULO DE COMISIÓN (LEYENDO CONFIG ACTUAL)
# ============================================================

def calcular_comision_usuario(usuario, fecha, matriz_filas=None):
    """
    Calcula la comisión de un usuario usando la configuración VIGENTE.

    Se usa:
    - Al crear un cuadre por primera vez (para guardar el snapshot).
    - Como fallback cuando un cuadre no tiene snapshot (cuadres viejos).

    Retorna dict:
    {
        'modalidad': 'general' | 'por_grupo' | 'sin_config',
        'porcentaje_general': Decimal | None,
        'comision_total': Decimal,
        'desglose': [ {...}, ... ] or [],
    }
    """
    try:
        config = ConfiguracionComision.objects.get(usuario=usuario, activo=True)
    except ConfiguracionComision.DoesNotExist:
        return {
            'modalidad': 'sin_config',
            'porcentaje_general': None,
            'comision_total': Decimal('0.00'),
            'desglose': [],
        }

    if config.modalidad == 'general':
        if matriz_filas:
            base = sum(
                (Decimal(str(v)) for v in matriz_filas.values() if v is not None),
                Decimal('0.00'),
            )
        else:
            base = Decimal('0.00')
        comision = (base * config.porcentaje_general / Decimal('100')).quantize(Decimal('0.01'))
        return {
            'modalidad': 'general',
            'porcentaje_general': config.porcentaje_general,
            'comision_total': comision,
            'desglose': [],
        }

    # modalidad == 'por_grupo'
    desglose = []
    comision_total = Decimal('0.00')
    for item in config.comisiones_fp.select_related('forma_pago').all():
        base = (matriz_filas or {}).get(item.forma_pago_id, Decimal('0.00')) or Decimal('0.00')
        comision_fp = (base * item.porcentaje / Decimal('100')).quantize(Decimal('0.01'))
        comision_total += comision_fp
        desglose.append({
            'forma_pago_id': item.forma_pago_id,
            'forma_pago_nombre': item.forma_pago.nombre,
            'base': base,
            'porcentaje': item.porcentaje,
            'comision': comision_fp,
        })
    return {
        'modalidad': 'por_grupo',
        'porcentaje_general': None,
        'comision_total': comision_total,
        'desglose': desglose,
    }


# ============================================================
# CÁLCULO DE COMISIÓN (LEYENDO SNAPSHOT DEL CUADRE)
# ============================================================

def _comision_desde_snapshot(cuadre, matriz_filas):
    """
    Reconstruye la info de comisión usando los % guardados en el cuadre.
    Recalcula la comisión con los montos ACTUALES pero los % CONGELADOS.
    """
    modalidad = cuadre.modalidad_comision_snapshot

    if modalidad == 'sin_config' or modalidad is None:
        return {
            'modalidad': 'sin_config',
            'porcentaje_general': None,
            'comision_total': Decimal('0.00'),
            'desglose': [],
        }

    if modalidad == 'general':
        if matriz_filas:
            base = sum(
                (Decimal(str(v)) for v in matriz_filas.values() if v is not None),
                Decimal('0.00'),
            )
        else:
            base = Decimal('0.00')
        porcentaje = cuadre.porcentaje_comision_snapshot or Decimal('0.00')
        comision = (base * porcentaje / Decimal('100')).quantize(Decimal('0.01'))
        return {
            'modalidad': 'general',
            'porcentaje_general': porcentaje,
            'comision_total': comision,
            'desglose': [],
        }

    if modalidad == 'por_grupo':
        desglose_guardado = cuadre.comision_desglose_snapshot or []
        desglose = []
        comision_total = Decimal('0.00')
        for item in desglose_guardado:
            fp_id = item.get('forma_pago_id')
            base = (matriz_filas or {}).get(fp_id, Decimal('0.00')) or Decimal('0.00')
            try:
                porcentaje = Decimal(str(item.get('porcentaje', '0')))
            except Exception:
                porcentaje = Decimal('0.00')
            comision_fp = (base * porcentaje / Decimal('100')).quantize(Decimal('0.01'))
            comision_total += comision_fp
            desglose.append({
                'forma_pago_id': fp_id,
                'forma_pago_nombre': item.get('forma_pago_nombre', ''),
                'base': base,
                'porcentaje': porcentaje,
                'comision': comision_fp,
            })
        return {
            'modalidad': 'por_grupo',
            'porcentaje_general': None,
            'comision_total': comision_total,
            'desglose': desglose,
        }

    # Fallback de seguridad
    return {
        'modalidad': 'sin_config',
        'porcentaje_general': None,
        'comision_total': Decimal('0.00'),
        'desglose': [],
    }


def _serializar_desglose(desglose):
    """Convierte Decimals a strings para guardar en JSONField."""
    if not desglose:
        return []
    return [
        {
            'forma_pago_id': d.get('forma_pago_id'),
            'forma_pago_nombre': d.get('forma_pago_nombre', ''),
            'porcentaje': str(d.get('porcentaje', '0')),
        }
        for d in desglose
    ]


# ============================================================
# SERVICIO PRINCIPAL
# ============================================================

class CuadreService:

    @staticmethod
    def _construir_matriz(jugadas):
        """
        Construye la matriz sorteo × forma de pago esperada por el template.
        """
        filas_dict = defaultdict(lambda: defaultdict(Decimal))
        sorteos = {}
        formas_pago = {}
        totales_por_fp = defaultdict(Decimal)
        totales_por_sorteo = defaultdict(Decimal)
        gran_total = Decimal('0.00')

        for j in jugadas:
            s_id = j.sorteo_id
            fp_id = j.forma_pago_id
            monto = j.monto or Decimal('0.00')
            filas_dict[s_id][fp_id] += monto
            sorteos[s_id] = j.sorteo
            formas_pago[fp_id] = j.forma_pago
            totales_por_fp[fp_id] += monto
            totales_por_sorteo[s_id] += monto
            gran_total += monto

        filas = []
        for s_id, s in sorteos.items():
            montos = {
                fp_id: filas_dict[s_id].get(fp_id, Decimal('0.00'))
                for fp_id in formas_pago
            }
            filas.append({
                'sorteo': s,
                'montos': montos,
                'total': sum(montos.values(), Decimal('0.00')),
            })

        # FIX_CUADRE_DESGLOSE: agrupar ventas y premios por (FP, sorteo)
        ventas_por_fp_sorteo = defaultdict(lambda: defaultdict(Decimal))
        premios_por_fp_sorteo = defaultdict(lambda: defaultdict(Decimal))
        for j in jugadas:
            if j.forma_pago_id:
                if j.monto:
                    ventas_por_fp_sorteo[j.forma_pago_id][j.sorteo_id] += j.monto
                if j.estado == 'ganadora' and j.monto_premio:
                    premios_por_fp_sorteo[j.forma_pago_id][j.sorteo_id] += j.monto_premio

        ventas_por_sorteo = {}
        for fp_id, sort_dict in ventas_por_fp_sorteo.items():
            ventas_por_sorteo[fp_id] = [
                {'sorteo': sorteos.get(sid), 'monto': m}
                for sid, m in sorted(sort_dict.items(), key=lambda x: -x[1])
            ]

        # FIX_PREMIOS_ANIDADO: enriquecer con clientes por sorteo
        premios_por_sorteo = {}
        # Agrupar por (fp, sorteo, cliente)
        premios_por_fp_sorteo_cliente = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
        for j in jugadas:
            if j.estado == 'ganadora' and j.monto_premio and j.forma_pago_id:
                premios_por_fp_sorteo_cliente[j.forma_pago_id][j.sorteo_id][j.usuario_id] += j.monto_premio

        for fp_id, sort_dict in premios_por_fp_sorteo.items():
            items = []
            for sid, m in sorted(sort_dict.items(), key=lambda x: -x[1]):
                if m <= 0:
                    continue
                # Clientes de este sorteo en esta FP
                cli_dict = premios_por_fp_sorteo_cliente.get(fp_id, {}).get(sid, {})
                clientes = []
                for uid, monto_cli in sorted(cli_dict.items(), key=lambda x: -x[1]):
                    u = User.objects.filter(id=uid).first()
                    if u:
                        clientes.append({
                            'cliente': u,
                            'monto': monto_cli,
                        })
                items.append({
                    'sorteo': sorteos.get(sid),
                    'monto': m,
                    'clientes': clientes,
                })
            premios_por_sorteo[fp_id] = items

        return {
            'sorteos': list(sorteos.values()),
            'formas_pago': list(formas_pago.values()),
            'filas': filas,
            'totales_por_fp': dict(totales_por_fp),
            'totales_por_sorteo': dict(totales_por_sorteo),
            'gran_total': gran_total,
            'ventas_por_sorteo': ventas_por_sorteo,
            'premios_por_sorteo': premios_por_sorteo,
        }

    @staticmethod
    def generar_cuadre_completo(usuario, fecha):
        """
        Genera el contexto completo del cuadre diario para un usuario.
        Si el cuadre no existe, lo crea y guarda el snapshot de comisión.
        Si ya existe, respeta el snapshot guardado (no retroactivo).
        """
        # FIX_CUADRE_HERENCIA_V3: heredar fondo inicial del snapshot del día anterior
        from datetime import timedelta as _td
        from pagos.models import FormaPago as _FP

        _fecha_anterior = fecha - _td(days=1)
        _cuadre_anterior = CuadreDiario.objects.filter(
            usuario=usuario, fecha=_fecha_anterior
        ).first()

        # Snapshot heredado: {'Tarjeta': '190.00', 'Saldo móvil': '125.00', ...}
        _snap_heredado = {}
        if _cuadre_anterior and _cuadre_anterior.fondo_final_snapshot:
            _snap_heredado = _cuadre_anterior.fondo_final_snapshot

        # Defaults: envie/recibi/ajuste en 0
        defaults_nuevos = {
            'envie_cash': Decimal('0.00'),
            'envie_saldo': Decimal('0.00'),
            'envie_tarjeta': Decimal('0.00'),
            'recibi_cash': Decimal('0.00'),
            'recibi_saldo': Decimal('0.00'),
            'recibi_tarjeta': Decimal('0.00'),
            'ajuste_cash': Decimal('0.00'),
            'ajuste_saldo': Decimal('0.00'),
            'ajuste_tarjeta': Decimal('0.00'),
            'deuda_total': Decimal('0.00'),
            'pagado': Decimal('0.00'),
            'cerrado': False,
            'notas': '',
        }

        # Heredar iniciales del snapshot (o 0 si primer día)
        for _fp in _FP.objects.filter(activo=True):
            _nombre = _fp.nombre
            _fp_key = _nombre.lower()
            _val = Decimal(str(_snap_heredado.get(_nombre, '0.00')))
            if _fp_key in ('tarjeta', 'saldo', 'cash'):
                defaults_nuevos[f'inicial_{_fp_key}'] = _val

        # Snapshot inicial completo (para cualquier FP)
        defaults_nuevos['fondo_inicial_snapshot'] = {
            _fp.nombre: str(_snap_heredado.get(_fp.nombre, '0.00'))
            for _fp in _FP.objects.filter(activo=True)
        }

        cuadre, created = CuadreDiario.objects.get_or_create(
            usuario=usuario,
            fecha=fecha,
            defaults=defaults_nuevos,
        )

        # ═══════════════════════════════════════════════════════════════
        # FIX_CUADRE_INICIAL_HEREDA_V4
        # REGLA: fondo_inicial(hoy) DEBE SER SIEMPRE fondo_final(ayer)
        # Se aplica incluso si el cuadre ya existía (no solo al crear).
        # ═══════════════════════════════════════════════════════════════
        if _cuadre_anterior and _cuadre_anterior.fondo_final_snapshot:
            _snap_ayer = _cuadre_anterior.fondo_final_snapshot
            if (cuadre.fondo_inicial_snapshot or {}) != _snap_ayer:
                cuadre.fondo_inicial_snapshot = _snap_ayer
                cuadre.save(update_fields=['fondo_inicial_snapshot'])

        jugadas = Jugada.objects.filter(
            destinatario=usuario,
            fecha_sorteo=fecha,
            estado__in=['confirmada', 'ganadora', 'perdedora']
        ).select_related('sorteo', 'forma_juego', 'forma_pago')

        # ----- Totales -----
        total_ventas = jugadas.aggregate(t=Sum('monto'))['t'] or Decimal('0.00')
        total_premios = (
            jugadas.filter(estado='ganadora')
                   .aggregate(t=Sum('monto_premio'))['t'] or Decimal('0.00')
        )
        total_jugadas = jugadas.count()
        total_sobrelimite = (
            jugadas.filter(sobrelimite=True)
                   .aggregate(t=Sum('monto'))['t'] or Decimal('0.00')
        )
        neto = total_ventas - total_premios

        # ----- Matriz -----
        matriz = CuadreService._construir_matriz(jugadas)

        # ----- Comisión (con snapshot) -----
        if cuadre.modalidad_comision_snapshot is None:
            # Primera vez que se procesa este cuadre:
            # calcular con la config actual y guardar snapshot
            comision_info = calcular_comision_usuario(
                usuario, fecha, matriz_filas=matriz['totales_por_fp']
            )
            cuadre.modalidad_comision_snapshot = comision_info['modalidad']
            cuadre.porcentaje_comision_snapshot = comision_info.get('porcentaje_general')
            cuadre.comision_calculada_snapshot = comision_info['comision_total']
            cuadre.comision_desglose_snapshot = _serializar_desglose(
                comision_info.get('desglose')
            )
            cuadre.save(update_fields=[
                'modalidad_comision_snapshot',
                'porcentaje_comision_snapshot',
                'comision_calculada_snapshot',
                'comision_desglose_snapshot',
            ])
        else:
            # Ya existe snapshot → usar los % congelados
            comision_info = _comision_desde_snapshot(cuadre, matriz['totales_por_fp'])

        # ----- Control fondos por forma de pago -----
        # FIX_CUADRE_FORMULA_V2: fórmula correcta
        #   Limpio = Ventas - Comisión - Premios + Recibí - Envié + Ajuste
        #   Fondo Final = Fondo Inicial + Limpio
        formas_pago = FormaPago.objects.filter(activo=True)

        # Ventas por FP (desde matriz ya construida)
        ventas_por_fp = matriz['totales_por_fp']

        # Premios por FP
        premios_por_fp = defaultdict(Decimal)
        for j in jugadas.filter(estado='ganadora'):
            if j.forma_pago_id and j.monto_premio:
                premios_por_fp[j.forma_pago_id] += j.monto_premio

        # Comisión por FP (del comision_info)
        comision_por_fp = defaultdict(Decimal)
        if comision_info.get('modalidad') == 'por_grupo':
            for item in comision_info.get('desglose', []):
                comision_por_fp[item['forma_pago_id']] = Decimal(str(item['comision']))
        elif comision_info.get('modalidad') == 'general':
            # Prorratear la comisión total entre FPs según ventas
            comision_total = Decimal(str(comision_info.get('comision_total', 0)))
            total_ventas_com = sum(ventas_por_fp.values(), Decimal('0.00'))
            if total_ventas_com > 0:
                for fp_id, v in ventas_por_fp.items():
                    proporcion = (Decimal(str(v)) / total_ventas_com)
                    comision_por_fp[fp_id] = (proporcion * comision_total).quantize(Decimal('0.01'))

        control = {
            'fondo_inicial': {},
            'limpio': {},
            'enviado_banco': {},
            'recibido_banco': {},
            'ajuste': {},
            'fondo_final': {},
            'fondo_actual': {},   # alias legacy
            'ventas': {},
            'premios': {},
            'comision': {},
            'deuda_total': cuadre.deuda_total or Decimal('0.00'),
            'pagado': cuadre.pagado or Decimal('0.00'),
            'cerrado': cuadre.cerrado,
            'ventas_por_sorteo': {},
            'premios_por_sorteo': {},
        }

        for fp in formas_pago:
            nombre = fp.nombre
            fp_key = nombre.lower()

            # Leer valores guardados (preferir JSON snapshot si existe)
            _snap_ini = cuadre.fondo_inicial_snapshot or {}
            if nombre in _snap_ini:
                fi = Decimal(str(_snap_ini[nombre]))
            else:
                fi = Decimal(str(getattr(cuadre, f'inicial_{fp_key}', 0) or 0))

            # Envíe/Recibí/Ajuste: si hay lista JSON, sumar; sino, scalar
            _envie_list = (cuadre.envie_lista or {}).get(nombre, [])
            _recibi_list = (cuadre.recibi_lista or {}).get(nombre, [])
            _ajuste_list = (cuadre.ajuste_lista or {}).get(nombre, [])

            env = (sum(Decimal(str(v)) for v in _envie_list)
                   if _envie_list
                   else Decimal(str(getattr(cuadre, f'envie_{fp_key}', 0) or 0)))
            rec = (sum(Decimal(str(v)) for v in _recibi_list)
                   if _recibi_list
                   else Decimal(str(getattr(cuadre, f'recibi_{fp_key}', 0) or 0)))
            ajuste = (sum(Decimal(str(v)) for v in _ajuste_list)
                      if _ajuste_list
                      else Decimal(str(getattr(cuadre, f'ajuste_{fp_key}', 0) or 0)))

            # Ventas/Premios/Comisión por FP
            ventas_fp = Decimal(str(ventas_por_fp.get(fp.id, 0)))
            premios_fp = Decimal(str(premios_por_fp.get(fp.id, 0)))
            comision_fp = Decimal(str(comision_por_fp.get(fp.id, 0)))

            # Fórmula correcta
            limpio = ventas_fp - comision_fp - premios_fp + rec - env + ajuste
            fondo_final = fi + limpio

            control['fondo_inicial'][nombre] = fi
            control['enviado_banco'][nombre] = env
            control['recibido_banco'][nombre] = rec
            control['ajuste'][nombre] = ajuste
            control['ventas'][nombre] = ventas_fp
            control['premios'][nombre] = premios_fp
            control['comision'][nombre] = comision_fp
            control['limpio'][nombre] = limpio
            control['fondo_final'][nombre] = fondo_final
            control['fondo_actual'][nombre] = fondo_final  # alias legacy
            # FIX_CUADRE_DESGLOSE: desglose por sorteo
            control['ventas_por_sorteo'][fp.id] = matriz.get('ventas_por_sorteo', {}).get(fp.id, [])
            control['premios_por_sorteo'][fp.id] = matriz.get('premios_por_sorteo', {}).get(fp.id, [])

        # FIX_CUADRE_HERENCIA_V3: guardar snapshot del fondo final para heredar mañana
        try:
            _snap_final = {
                fp.nombre: str(control['fondo_final'][fp.nombre])
                for fp in formas_pago
            }
            _snap_inicial = {
                fp.nombre: str(control['fondo_inicial'][fp.nombre])
                for fp in formas_pago
            }
            cuadre.fondo_final_snapshot = _snap_final
            cuadre.fondo_inicial_snapshot = _snap_inicial
            cuadre.save(update_fields=['fondo_final_snapshot', 'fondo_inicial_snapshot'])
        except Exception as _e:
            import logging
            logging.getLogger(__name__).warning(f'Error guardando snapshot: {_e}')

        resumen = {
            'total_jugadas': total_jugadas,
            'total_recogido': total_ventas,
            'premios': total_premios,
            'neto': neto,
            'sobrelimites': total_sobrelimite,
        }

        return {
            'cuadre': cuadre,
            'jugadas': jugadas,
            'control': _filtrar_fps_cero(control),
            'totales': resumen,
            'resumen': resumen,
            'formas_pago': formas_pago,
            'matriz': matriz,
            'comision_info': comision_info,
        }

    # ------------------------------------------------------------
    # HELPERS DE RESUMEN
    # ------------------------------------------------------------

    @staticmethod
    def _sumar_tres(queryset, campos):
        """Suma 3 columnas evitando None intermedios."""
        agg = queryset.aggregate(**{f'f{i}': Sum(c) for i, c in enumerate(campos)})
        return sum(
            (agg[f'f{i}'] or Decimal('0.00') for i in range(len(campos))),
            Decimal('0.00'),
        )

    @staticmethod
    def _sumar_comisiones_snapshot(cuadres):
        """Suma las comisiones congeladas en los cuadres dados."""
        total = cuadres.aggregate(t=Sum('comision_calculada_snapshot'))['t']
        return total or Decimal('0.00')

    @staticmethod
    def calcular_resumen_banco(banco, fecha_desde, fecha_hasta):
        """
        Resumen agregado de todos los comerciales de un banco en un rango.
        """
        comerciales_ids = Subordinacion.objects.filter(
            jefe=banco, activo=True
        ).values_list('subordinado_id', flat=True)

        comerciales_data = []
        total_ventas = Decimal('0.00')
        total_premios = Decimal('0.00')
        total_comisiones = Decimal('0.00')
        total_jugadas = 0

        for comercial_id in comerciales_ids:
            cuadres = CuadreDiario.objects.filter(
                usuario_id=comercial_id,
                fecha__gte=fecha_desde,
                fecha__lte=fecha_hasta,
            )
            ventas = CuadreService._sumar_tres(
                cuadres, ['envie_cash', 'envie_saldo', 'envie_tarjeta']
            )
            premios = CuadreService._sumar_tres(
                cuadres, ['recibi_cash', 'recibi_saldo', 'recibi_tarjeta']
            )
            comisiones = CuadreService._sumar_comisiones_snapshot(cuadres)

            comerciales_data.append({
                'comercial_id': comercial_id,
                'ventas': ventas,
                'premios': premios,
                'jugadas': 0,
                'comisiones': comisiones,
                'neto': ventas - premios - comisiones,
            })
            total_ventas += ventas
            total_premios += premios
            total_comisiones += comisiones

        return {
            'comerciales': comerciales_data,
            'total_ventas': total_ventas,
            'total_premios': total_premios,
            'total_jugadas': total_jugadas,
            'total_comisiones': total_comisiones,
            'total_neto': total_ventas - total_premios - total_comisiones,
        }

    @staticmethod
    def calcular_resumen_superadmin(fecha_desde, fecha_hasta):
        """
        Resumen global de todos los bancos.
        """
        bancos_ids = Rol.objects.filter(
            tipo='banco', activo=True
        ).values_list('usuario_id', flat=True)

        bancos_data = []
        total_ventas = Decimal('0.00')
        total_premios = Decimal('0.00')
        total_comisiones = Decimal('0.00')
        total_jugadas = 0

        for banco_id in bancos_ids:
            comerciales_ids = list(Subordinacion.objects.filter(
                jefe_id=banco_id, activo=True
            ).values_list('subordinado_id', flat=True))
            usuarios_ids = [banco_id] + comerciales_ids

            cuadres = CuadreDiario.objects.filter(
                usuario_id__in=usuarios_ids,
                fecha__gte=fecha_desde,
                fecha__lte=fecha_hasta,
            )
            ventas = CuadreService._sumar_tres(
                cuadres, ['envie_cash', 'envie_saldo', 'envie_tarjeta']
            )
            premios = CuadreService._sumar_tres(
                cuadres, ['recibi_cash', 'recibi_saldo', 'recibi_tarjeta']
            )
            comisiones = CuadreService._sumar_comisiones_snapshot(cuadres)

            bancos_data.append({
                'banco_id': banco_id,
                'ventas': ventas,
                'premios': premios,
                'jugadas': 0,
                'comisiones': comisiones,
                'neto': ventas - premios - comisiones,
            })
            total_ventas += ventas
            total_premios += premios
            total_comisiones += comisiones

        return {
            'bancos': bancos_data,
            'total_ventas': total_ventas,
            'total_premios': total_premios,
            'total_jugadas': total_jugadas,
            'total_comisiones': total_comisiones,
            'total_neto': total_ventas - total_premios - total_comisiones,
        }

# FIX_CUADRE_FORMULA_V2: fórmula corregida + herencia de fondo

# FIX_CUADRE_HERENCIA_V3: herencia por snapshot del fondo final

# FIX_CUADRE_FPS_CERO_V1
def _filtrar_fps_cero(control):
    if not control:
        return control
    try:
        fi = control.get('fondo_inicial', {}) or {}
        ve = control.get('ventas', {}) or {}
        fps_visibles = [
            k for k in fi.keys()
            if float(fi.get(k) or 0) != 0 or float(ve.get(k) or 0) != 0
        ]
    except Exception:
        return control
    for key in ('fondo_inicial', 'ventas', 'comision', 'premios',
                'recibido_banco', 'enviado_banco', 'ajuste',
                'limpio', 'fondo_final'):
        if key in control and isinstance(control[key], dict):
            control[key] = {
                k: v for k, v in control[key].items() if k in fps_visibles
            }
    return control
