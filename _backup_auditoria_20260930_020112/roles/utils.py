# -*- coding: utf-8 -*-
"""
Utilidades para la aplicación roles: notificaciones, recursos, límites, dosis, postpagos y bonos.
"""
from decimal import Decimal
from django.contrib.auth.models import User
from django.contrib.auth.models import User
from django.db.models import Q, Sum, Count
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.db import transaction

from sorteos.models import Sorteo, DosisBase
from jugadas.models import FormaJuego
from pagos.models import FormaPago
from .models import RecursoAsignado, LimiteApuesta, DosisPago
from .models import (
    RecursoAsignado, LimiteApuesta, DosisPago, Notificacion, Fondo, Fondo,
    Subordinacion, Rol, Bono, Postpago, PostpagoDescuento, PostpagoCliente
)

# ✨ Helpers de valores globales (plataforma + superadmin)
from .dosis_default import (
    get_dosis_global,
    get_limites_globales,
    get_pool_global,
    get_pool_global_superadmin,
    get_sobrelimite_global_superadmin,
    MULTIPLICADOR_SUPERADMIN,
)


# ============================================================
# NOTIFICACIONES
# ============================================================

def _debe_sonar(tipo, categoria, mensaje, prioridad='media'):
    """Decide automaticamente si una notificacion debe sonar.
    Suena siempre en:
      - recargas (cualquier evento de recarga)
      - prioridad alta / urgente
      - eventos criticos: postpago, premio, deuda, sobrelimite, apuesta
      - bienvenida / registro
    """
    m = (mensaje or '').lower()
    if tipo == 'recarga' or categoria == 'recarga':
        return True
    if str(prioridad).lower() in ('alta', 'urgente'):
        return True
    if tipo in ('postpago', 'premio', 'deuda', 'sobrelimite', 'apuesta', 'prestamo', 'suscripcion'):
        return True
    if tipo == 'sistema' and ('ascendido' in m or 'ascenso' in m):
        return True
    if 'bienvenido' in m or 'bienvenida' in m or categoria == 'registro':
        return True
    return False

def crear_notificacion(usuario, tipo, mensaje, datos=None, prioridad='media', categoria='sistema'):
    if datos is None:
        datos = {}
    con_sonido = _debe_sonar(tipo, categoria, mensaje, prioridad=prioridad)
    return Notificacion.objects.create(
        usuario=usuario,
        tipo=tipo,
        mensaje=mensaje,
        datos=datos,
        prioridad=prioridad,
        categoria=categoria,
        leido=False,
        con_sonido=con_sonido,
        creado_en=timezone.now()
    )

@login_required
def marcar_notificacion_leida(request, notificacion_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)
    try:
        notificacion = get_object_or_404(Notificacion, id=notificacion_id, usuario=request.user)
        notificacion.marcar_como_leida()
        return JsonResponse({'success': True, 'message': 'Notificación marcada como leída.'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# ============================================================
# RECURSOS VISIBLES
# ============================================================

def get_recursos_visibles(usuario, tipo_recurso=None):
    qs = RecursoAsignado.objects.filter(activo=True)
    es_superadmin = usuario.is_superuser or usuario.roles.filter(tipo='superadmin', activo=True).exists()
    es_banco = usuario.roles.filter(tipo='banco', activo=True).exists()
    es_comercial = usuario.roles.filter(tipo='comercial', activo=True).exists()

    if es_superadmin:
        qs = qs.filter(banco__isnull=True, comercial__isnull=True)
        if not qs.exists():
            qs = RecursoAsignado.objects.filter(activo=True)
    elif es_banco:
        qs = qs.filter(banco=usuario)
    elif es_comercial:
        qs = qs.filter(comercial=usuario)
    else:
        subordinacion = Subordinacion.objects.filter(subordinado=usuario, activo=True).first()
        if subordinacion:
            qs = qs.filter(comercial=subordinacion.jefe)
        else:
            qs = qs.none()

    if tipo_recurso:
        qs = qs.filter(tipo=tipo_recurso)

    return qs.distinct()


def get_banco_asignado(usuario):
    rol = Rol.objects.filter(usuario=usuario, tipo='comercial', activo=True).first()
    if rol and rol.banco_asignado:
        return rol.banco_asignado
    return None


# ============================================================
# MATRIZ DE LÍMITES, SOBELÍMITES Y DOSIS
# ============================================================
def get_matriz_limites_dosis(banco, comercial=None):
    """
    Construye la matriz de límites, sobrelímites y dosis.
    Usa Sorteo.formas_juego (JSONField) como fuente de verdad.

    Reglas:
    - Si no hay recursos de tipo='sorteo' asignados → se muestran TODOS los sorteos activos.
    - Si no hay recursos de tipo='forma_pago' asignados → se muestran TODAS las FPs activas.
    - Superadmin: límites × 50, dosis igual.
    """
    # --- Mapeo de claves cortas → nombre real de FormaJuego en BD ---
    MAPEO_FJ = {
        'pick2': 'Pick 2',
        'pick3': 'Pick 3',
        'pick4': 'Pick 4',
        'pick5': 'Pick 5',
        'fijo': 'Fijo',
        'corridos': 'Corridos',
        'pf': 'PF',
        'vspf': 'VS PF',
        'vspick2': 'VS Pick2',
        'pick2vspf': 'Pick2 vs PF',
        'tripleta': 'Tripleta',
        'posicion': 'Posición',
        'centenas corridas': 'Centenas Corridas',
        'superparlet': 'Superparlet',
        'parlet': 'Parlet',
        'par frontal': 'Par frontal',
        'vs': 'VS',
    }

    usuario_base = comercial if comercial else banco
    if not usuario_base:
        return None

    es_superadmin = (
        usuario_base.is_superuser
        or usuario_base.roles.filter(tipo='superadmin', activo=True).exists()
    )

    # Recursos: del comercial si tiene; si no, del banco; si superadmin, todos
    recursos = RecursoAsignado.objects.filter(activo=True)
    if comercial:
        rc = recursos.filter(comercial=comercial)
        recursos = rc if rc.exists() else recursos.filter(banco=banco)
    elif es_superadmin:
        # Superadmin ve todo → deja el queryset sin filtrar por banco/comercial
        pass
    elif banco:
        recursos = recursos.filter(banco=banco)
    else:
        return None

    sorteos_ids = list(recursos.filter(tipo='sorteo').values_list('sorteo_id', flat=True).distinct())
    formas_pago_ids = list(recursos.filter(tipo='forma_pago').values_list('forma_pago_id', flat=True).distinct())

    # ✨ FIX: si no hay sorteos específicos asignados → mostrar TODOS los activos
    if not sorteos_ids:
        sorteos_ids = list(Sorteo.objects.filter(activo=True).values_list('id', flat=True))

    # ✨ FIX: si no hay formas de pago específicas → mostrar TODAS las activas
    if not formas_pago_ids:
        formas_pago_ids = list(FormaPago.objects.filter(activo=True).values_list('id', flat=True))

    if not sorteos_ids or not formas_pago_ids:
        return {'filas': [], 'formas_pago': FormaPago.objects.none()}

    sorteos = Sorteo.objects.filter(id__in=sorteos_ids, activo=True).order_by('nombre')
    formas_pago = FormaPago.objects.filter(id__in=formas_pago_ids, activo=True).order_by('nombre')

    # Mapa nombre -> FormaJuego
    fj_por_nombre = {fj.nombre.lower(): fj for fj in FormaJuego.objects.filter(activo=True)}

    # Límites y dosis existentes
    limite_map, sobre_map, dosis_map = {}, {}, {}

    if comercial:
        for l in LimiteApuesta.objects.filter(comercial=comercial, activo=True).values(
            'sorteo_id', 'forma_juego_id', 'forma_pago_id', 'monto_maximo', 'monto_sobrelimite'
        ):
            k = (l['sorteo_id'], l['forma_juego_id'], l['forma_pago_id'])
            limite_map[k] = float(l['monto_maximo']) if l['monto_maximo'] is not None else None
            sobre_map[k] = float(l['monto_sobrelimite']) if l['monto_sobrelimite'] is not None else None

        for d in DosisPago.objects.filter(comercial=comercial, activo=True).values(
            'sorteo_id', 'forma_juego_id', 'forma_pago_id', 'monto_por_peso'
        ):
            k = (d['sorteo_id'], d['forma_juego_id'], d['forma_pago_id'])
            dosis_map[k] = float(d['monto_por_peso']) if d['monto_por_peso'] is not None else None

    if banco:
        for l in LimiteApuesta.objects.filter(banco=banco, comercial__isnull=True, activo=True).values(
            'sorteo_id', 'forma_juego_id', 'forma_pago_id', 'monto_maximo', 'monto_sobrelimite'
        ):
            k = (l['sorteo_id'], l['forma_juego_id'], l['forma_pago_id'])
            if k not in limite_map:
                limite_map[k] = float(l['monto_maximo']) if l['monto_maximo'] is not None else None
                sobre_map[k] = float(l['monto_sobrelimite']) if l['monto_sobrelimite'] is not None else None

        for d in DosisPago.objects.filter(banco=banco, comercial__isnull=True, activo=True).values(
            'sorteo_id', 'forma_juego_id', 'forma_pago_id', 'monto_por_peso'
        ):
            k = (d['sorteo_id'], d['forma_juego_id'], d['forma_pago_id'])
            if k not in dosis_map:
                dosis_map[k] = float(d['monto_por_peso']) if d['monto_por_peso'] is not None else None

    # Valores por defecto (por clave corta)
    DEFAULTS = {
        # Valores BASE (los que ve un banco). Superadmin aplica x50 al leer.
        'pick2':              {'dosis': 80.0,   'limite': 1000.0, 'sobre': 1000.0},
        'pf':                 {'dosis': 80.0,   'limite': 1000.0, 'sobre': 1000.0},
        'fijo':               {'dosis': 80.0,   'limite': 1000.0, 'sobre': 1000.0},
        'corridos':           {'dosis': 30.0,   'limite': 1000.0, 'sobre': 1000.0},
        'parlet':             {'dosis': 1000.0, 'limite': 1000.0, 'sobre': 1000.0},
        'candado':            {'dosis': 1000.0, 'limite': 1000.0, 'sobre': 1000.0},
        'pick3':              {'dosis': 400.0,  'limite': 1000.0, 'sobre': 1000.0},
        'pick4':              {'dosis': 2000.0, 'limite': 50.0,   'sobre': 50.0},
        'pick5':              {'dosis': 5000.0, 'limite': 100.0,  'sobre': 100.0},
        'centenas corridas':  {'dosis': 200.0,  'limite': 300.0,  'sobre': 300.0},
        'vs':                 {'dosis': 1000.0, 'limite': 100.0,  'sobre': 100.0},
        'vspf':               {'dosis': 1000.0, 'limite': 100.0,  'sobre': 100.0},
        'vspick2':            {'dosis': 1000.0, 'limite': 100.0,  'sobre': 100.0},
        'pick2vspf':          {'dosis': 1000.0, 'limite': 100.0,  'sobre': 100.0},
        'vs100':              {'dosis': 100.0,  'limite': 500.0,  'sobre': 500.0},
        'posicion':           {'dosis': 80.0,   'limite': 1000.0, 'sobre': 1000.0},
        'tripleta':           {'dosis': 3000.0, 'limite': 100.0,  'sobre': 100.0},
        'superparlet':        {'dosis': 1000.0, 'limite': 1000.0, 'sobre': 1000.0},
        'par frontal':        {'dosis': 100.0,  'limite': 500.0,  'sobre': 500.0},
    }

    filas = []
    for sorteo in sorteos:
        combos = []
        claves = [c.lower() for c in (sorteo.formas_juego or [])]
        for clave in claves:
            nombre_real = MAPEO_FJ.get(clave, clave).lower()
            fj = fj_por_nombre.get(nombre_real) or fj_por_nombre.get(clave)
            if not fj:
                continue

            limites_fp, sobre_fp, dosis_fp = {}, {}, {}
            for fp in formas_pago:
                k = (sorteo.id, fj.id, fp.id)
                lim = limite_map.get(k)
                sob = sobre_map.get(k)
                dos = dosis_map.get(k)

                dflt = DEFAULTS.get(clave, {})
                if lim is None:
                    lim = dflt.get('limite', 0.0)
                if sob is None:
                    sob = dflt.get('sobre', 0.0)
                if dos is None:
                    dos = dflt.get('dosis', 1.0)

                # ✨ Superadmin: límites × MULTIPLICADOR, dosis igual
                if es_superadmin:
                    lim = float(lim) * MULTIPLICADOR_SUPERADMIN
                    sob = float(sob) * MULTIPLICADOR_SUPERADMIN
                    # dos se queda igual

                limites_fp[fp.id] = lim
                sobre_fp[fp.id] = sob
                dosis_fp[fp.id] = dos

            combos.append({
                'forma_juego': fj,
                'limites': limites_fp,
                'sobrelimites': sobre_fp,
                'dosis': dosis_fp,
            })

        if combos:
            filas.append({'sorteo': sorteo, 'comercial': comercial, 'combos': combos})

    return {'filas': filas, 'formas_pago': formas_pago}


# ============================================================
# POSTPAGOS (CRÉDITO ACUMULATIVO)
# ============================================================

# ═══════════════════════════════════════════════════════════════
# POSTPAGO POR GESTOR V2
# Cada Postpago tiene monto_pendiente. Los descuentos son por gestor.
# ═══════════════════════════════════════════════════════════════
def obtener_o_crear_postpago_cliente(cliente):
    """Obtiene o crea el objeto PostpagoCliente para un usuario."""
    obj, _ = PostpagoCliente.objects.get_or_create(cliente=cliente, defaults={'saldo': Decimal('0.00')})
    return obj


def _recalcular_saldo_postpago_cliente(cliente):
    """Recalcula el cache PostpagoCliente.saldo = suma de monto_pendiente de postpagos activos."""
    total = Postpago.objects.filter(
        cliente=cliente, activo=True, monto_pendiente__gt=0
    ).aggregate(t=Sum('monto_pendiente'))['t'] or Decimal('0.00')
    cp, _ = PostpagoCliente.objects.get_or_create(cliente=cliente, defaults={'saldo': Decimal('0.00')})
    cp.saldo = total
    cp.save(update_fields=['saldo'])
    return total


def agregar_postpago(cliente, gestor, monto, concepto='', forma_pago=None):
    """
    Anade un postpago al cliente con el gestor indicado.
    Si el cliente tiene Fondo con ese gestor, descuenta de inmediato lo que alcance.
    El monto descontado no se transfiere al gestor: es un ajuste virtual.
    """
    if monto <= 0:
        return None

    with transaction.atomic():
        # 1. Crear Postpago con monto_pendiente = monto
        postpago = Postpago.objects.create(
            cliente=cliente,
            gestor=gestor,
            monto=monto,
            monto_pendiente=monto,
            concepto=concepto,
            activo=True,
            forma_pago=forma_pago,  # FIX_FP_BONO_POSTPAGO_V1
        )

        # 2. Intentar descontar del Fondo del cliente con ese gestor
        descuento_inmediato = Decimal('0.00')

        fondos_qs = Fondo.objects.select_for_update().filter(
            usuario=cliente, asignado_por=gestor, activo=True,
        )
        if forma_pago:
            fondos_qs = fondos_qs.filter(forma_pago=forma_pago)
        fondos_qs = fondos_qs.order_by('id')

        restante = monto
        for f in fondos_qs:
            if restante <= 0:
                break
            if f.monto <= 0:
                continue
            a_desc = min(f.monto, restante)
            f.monto -= a_desc
            f.save(update_fields=['monto', 'actualizado_en'])
            descuento_inmediato += a_desc
            restante -= a_desc
            MovimientoFondo.objects.create(
                emisor=None,
                receptor=cliente,
                forma_pago=f.forma_pago,
                monto=-a_desc,
                tipo='ajuste',
                estado='confirmado',
                datos_transferencia={
                    'tipo': 'postpago_descuento_inmediato',
                    'postpago_id': postpago.id,
                    'gestor': gestor.username,
                },
                nota=f"Descuento automático por postpago de ${monto} declarado por {gestor.username}",
            )

        # 3. Actualizar monto_pendiente del postpago
        if descuento_inmediato > 0:
            postpago.monto_pendiente = monto - descuento_inmediato
            if postpago.monto_pendiente <= 0:
                postpago.activo = False
            postpago.save(update_fields=['monto_pendiente', 'activo'])

        # 4. Recalcular cache
        _recalcular_saldo_postpago_cliente(cliente)
        saldo_cache = _recalcular_saldo_postpago_cliente(cliente)

        # 5. Notificaciones
        msg_cliente = f"💰 Has recibido un postpago de ${monto:.2f} de {gestor.username}."
        if descuento_inmediato > 0:
            msg_cliente += f" Se descontaron ${descuento_inmediato:.2f} de tu saldo. "
        if postpago.monto_pendiente > 0:
            msg_cliente += f"Pendiente por cubrir: ${postpago.monto_pendiente:.2f}."
        else:
            msg_cliente += " Postpago cubierto en su totalidad."

        crear_notificacion(
            usuario=cliente, tipo='info', mensaje=msg_cliente,
            datos={
                'postpago_id': postpago.id,
                'monto': float(monto),
                'descontado': float(descuento_inmediato),
                'pendiente': float(postpago.monto_pendiente),
                'saldo': float(saldo_cache),
                'gestor': gestor.username,
                'concepto': concepto,
            },
            prioridad='alta', categoria='financiera',
        )

        crear_notificacion(
            usuario=gestor, tipo='info',
            mensaje=f"✅ Has declarado un postpago de ${monto:.2f} a {cliente.username}." + (
                f" Se cubrieron ${descuento_inmediato:.2f} de su Fondo." if descuento_inmediato > 0 else ""
            ),
            datos={
                'cliente': cliente.username,
                'monto': float(monto),
                'descontado': float(descuento_inmediato),
                'pendiente': float(postpago.monto_pendiente),
            },
            prioridad='media', categoria='financiera',
        )

        return postpago


def descontar_postpago(cliente, monto, tipo='ajuste', origen_id=None, concepto='', gestor=None):
    """
    Descuenta un monto de los postpagos PENDIENTES del cliente CON ESE GESTOR.
    FIFO: el postpago mas antiguo primero.
    Retorna el monto realmente descontado.
    """
    if monto <= 0:
        return Decimal('0.00')
    if not gestor:
        # Sin gestor no se descuenta nada (evita cruzar deudas entre gestores)
        return Decimal('0.00')

    with transaction.atomic():
        postpagos = Postpago.objects.select_for_update().filter(
            cliente=cliente,
            gestor=gestor,
            activo=True,
            monto_pendiente__gt=0,
        ).order_by('fecha_creacion')

        if not postpagos.exists():
            return Decimal('0.00')

        restante = monto
        total_descontado = Decimal('0.00')

        for p in postpagos:
            if restante <= 0:
                break
            a_desc = min(p.monto_pendiente, restante)
            p.monto_pendiente -= a_desc
            if p.monto_pendiente <= 0:
                p.activo = False
            p.save(update_fields=['monto_pendiente', 'activo'])
            total_descontado += a_desc
            restante -= a_desc
            # FASE1_POSTPAGO_V1_DESCUENTO: ya no se usa PostpagoDescuento
            # (el nuevo flujo gestiona todo via Postpago.saldo)

        if total_descontado > 0:
            saldo_cache = _recalcular_saldo_postpago_cliente(cliente)
            msg = f"💰 Se descontaron ${total_descontado:.2f} de tu postpago por {concepto}. Saldo pendiente: ${saldo_cache:.2f}"
            crear_notificacion(
                usuario=cliente, tipo='info', mensaje=msg,
                datos={
                    'descuento': float(total_descontado),
                    'saldo_restante': float(saldo_cache),
                    'tipo': tipo,
                    'origen_id': origen_id,
                    'gestor': gestor.username,
                },
                prioridad='alta', categoria='financiera',
            )
            if saldo_cache == 0:
                crear_notificacion(
                    usuario=cliente, tipo='info',
                    mensaje="🎉 ¡Has liquidado completamente tu postpago!",
                    prioridad='alta', categoria='financiera',
                )
        else:
            # Recalcular cache de todas formas (por si acaso)
            _recalcular_saldo_postpago_cliente(cliente)

        return total_descontado


def verificar_postpago_al_recibir_premio(jugada):
    """
    Al procesar un premio, descuenta del postpago del cliente con el gestor
    destinatario de la jugada.
    """
    if not jugada.monto_premio or jugada.monto_premio <= 0:
        return Decimal('0.00')

    cliente = jugada.usuario
    gestor = jugada.destinatario

    return descontar_postpago(
        cliente=cliente,
        monto=jugada.monto_premio,
        tipo='premio',
        origen_id=jugada.id,
        concepto=f"Premio en {jugada.sorteo.nombre} - {jugada.forma_juego.nombre}",
        gestor=gestor,
    )


def verificar_postpago_al_recibir_recarga(cliente, monto_recarga, recarga_id=None, gestor=None):
    """
    Al recibir una recarga, descuenta del postpago del cliente con el gestor
    que origino la recarga.
    """
    if monto_recarga > 0 and gestor:
        return descontar_postpago(
            cliente=cliente,
            monto=monto_recarga,
            tipo='recarga',
            origen_id=recarga_id,
            concepto="Recarga de fondos",
            gestor=gestor,
        )
    return Decimal('0.00')


def enviar_notificacion_postpago_diaria(cliente):
    """
    Envía una notificación diaria al cliente si tiene saldo de postpago positivo.
    Solo envía si no se ha enviado en las últimas 24 horas.
    """
    cliente_postpago = obtener_o_crear_postpago_cliente(cliente)
    if cliente_postpago.saldo <= 0:
        return False

    now = timezone.now()
    if cliente_postpago.ultima_notificacion and (now - cliente_postpago.ultima_notificacion).total_seconds() < 86400:
        return False

    crear_notificacion(
        usuario=cliente,
        tipo='info',
        mensaje=f"📢 Recordatorio: Tienes un saldo de postpago de ${cliente_postpago.saldo:.2f} pendiente de pago. Se descontará automáticamente de tus próximos premios o recargas.",
        datos={'saldo': float(cliente_postpago.saldo)},
        prioridad='media',
        categoria='financiera'
    )
    cliente_postpago.ultima_notificacion = now
    cliente_postpago.save(update_fields=['ultima_notificacion'])
    return True


# ============================================================
# BONOS DE REFERIDO
# ============================================================

def verificar_bono_referido_disponible(usuario):
    try:
        return Bono.objects.filter(
            usuario=usuario,
            tipo='recomendacion',
            estado='pendiente'
        ).exists()
    except Exception:
        return False


# ============================================================
# POOL DE APUESTA POR GESTOR
# ============================================================
def get_pool_gestor(gestor, sorteo, forma_juego, forma_pago):
    """
    Devuelve el pool total (límite + sobrelímite) para un gestor.

    Reglas:
    - Superadmin          → pool global × 50 (o su registro propio si existe).
    - Banco con propio    → su pool.
    - Banco sin propio    → pool global.
    - Comercial con propio→ su pool.
    - Comercial sin propio→ 20% del pool del banco asignado, o global si no hay banco.
    - Cliente / otro      → pool global.
    """
    if not gestor:
        return Decimal('0')

    es_superadmin = (
        gestor.is_superuser
        or gestor.roles.filter(tipo='superadmin', activo=True).exists()
    )
    es_banco = gestor.roles.filter(tipo='banco', activo=True).exists()
    es_comercial = gestor.roles.filter(tipo='comercial', activo=True).exists()

    # ═══════════════════════════════════════════════════════════════
    # SUPERADMIN — pool global × 50 (o propio si existe)
    # ═══════════════════════════════════════════════════════════════
    if es_superadmin:
        propio = LimiteApuesta.objects.filter(
            banco=gestor, comercial__isnull=True,
            sorteo=sorteo, forma_juego=forma_juego, forma_pago=forma_pago,
            activo=True, es_global=False
        ).first()
        if propio:
            return (propio.monto_maximo or Decimal('0')) + (propio.monto_sobrelimite or Decimal('0'))
        return Decimal(str(get_pool_global_superadmin()))

    # ═══════════════════════════════════════════════════════════════
    # COMERCIAL — propio, o 20% del banco, o global
    # ═══════════════════════════════════════════════════════════════
    if es_comercial:
        propio = LimiteApuesta.objects.filter(
            comercial=gestor, sorteo=sorteo, forma_juego=forma_juego,
            forma_pago=forma_pago, activo=True
        ).first()
        if propio:
            return (propio.monto_maximo or Decimal('0')) + (propio.monto_sobrelimite or Decimal('0'))

        banco = get_banco_asignado(gestor)
        if banco:
            lim_banco = LimiteApuesta.objects.filter(
                banco=banco, comercial__isnull=True, sorteo=sorteo,
                forma_juego=forma_juego, forma_pago=forma_pago, activo=True
            ).first()
            if lim_banco:
                total = (lim_banco.monto_maximo or Decimal('0')) + (lim_banco.monto_sobrelimite or Decimal('0'))
                return total * Decimal('0.20')

        return Decimal(str(get_pool_global()))

    # ═══════════════════════════════════════════════════════════════
    # BANCO — propio, o global
    # ═══════════════════════════════════════════════════════════════
    if es_banco:
        propio = LimiteApuesta.objects.filter(
            banco=gestor, comercial__isnull=True, sorteo=sorteo,
            forma_juego=forma_juego, forma_pago=forma_pago, activo=True
        ).first()
        if propio:
            return (propio.monto_maximo or Decimal('0')) + (propio.monto_sobrelimite or Decimal('0'))
        return Decimal(str(get_pool_global()))

    # ═══════════════════════════════════════════════════════════════
    # CUALQUIER OTRO (cliente directo, etc.) → global
    # ═══════════════════════════════════════════════════════════════
    return Decimal(str(get_pool_global()))


# ============================================================
# ✨ DOSIS POR GESTOR
# ============================================================
def get_dosis_gestor(gestor, sorteo, forma_juego, forma_pago):
    """
    Devuelve la dosis (multiplicador monto × dosis = premio) para un gestor.

    Reglas:
    - Superadmin → DOSIS_GLOBAL[nombre] (sin multiplicar).
    - Otros      → su DosisPago propia, o global, o DosisBase como fallback.
    """
    if not gestor or not forma_juego:
        return Decimal('1')

    es_superadmin = (
        gestor.is_superuser
        or gestor.roles.filter(tipo='superadmin', activo=True).exists()
    )

    # Buscar dosis propia (excepto superadmin que siempre usa global)
    if not es_superadmin:
        propia = DosisPago.objects.filter(
            Q(banco=gestor) | Q(comercial=gestor),
            sorteo=sorteo, forma_juego=forma_juego, forma_pago=forma_pago,
            activo=True, es_global=False
        ).first()
        if propia and propia.monto_por_peso:
            return propia.monto_por_peso

    # Global del diccionario
    valor = get_dosis_global(forma_juego.nombre)
    if valor and valor > 0:
        return Decimal(str(valor))

    # Último fallback: DosisBase
    try:
        db = DosisBase.objects.filter(
            sorteo=sorteo, forma_juego=forma_juego, activo=True
        ).first()
        if db and db.dosis_por_peso:
            return db.dosis_por_peso
    except Exception:
        pass

    return Decimal('1')


# ============================================================
# ✨ SOBRELÍMITE POR GESTOR
# ============================================================
def get_sobrelimite_gestor(gestor, sorteo, forma_juego, forma_pago):
    """
    Devuelve el sobredosis (extra sobre el pool base) para un gestor.

    - Superadmin → LIMITES_GLOBAL['sobrelimite'] × 50
    - Otros      → propio o default global
    """
    if not gestor:
        return Decimal('0')

    es_superadmin = (
        gestor.is_superuser
        or gestor.roles.filter(tipo='superadmin', activo=True).exists()
    )
    if es_superadmin:
        return Decimal(str(get_sobrelimite_global_superadmin()))

    propio = LimiteApuesta.objects.filter(
        Q(banco=gestor) | Q(comercial=gestor),
        sorteo=sorteo, forma_juego=forma_juego, forma_pago=forma_pago,
        activo=True
    ).first()
    if propio and propio.monto_sobrelimite is not None:
        return propio.monto_sobrelimite

    return Decimal(str(get_limites_globales().get('sobrelimite', 0)))

# ============================================================
# HELPERS PARA AUDITORES
# ============================================================
def es_auditor(user):
    """¿El usuario tiene rol de auditor activo?"""
    if not user or not user.is_authenticated:
        return False
    return Rol.objects.filter(usuario=user, tipo='auditor', activo=True).exists()


def get_banco_del_auditor(user):
    """Devuelve el banco al que está asignado el auditor (o None)."""
    if not user or not user.is_authenticated:
        return None
    rol = Rol.objects.filter(usuario=user, tipo='auditor', activo=True).first()
    return rol.banco_asignado if rol else None


def get_red_del_auditor(user):
    """
    Red completa del auditor (banco + comerciales + clientes).
    Devuelve dict: {banco, comerciales, clientes, todos_ids}
    """
    banco = get_banco_del_auditor(user)
    if not banco:
        return {
            'banco': None,
            'comerciales': [],
            'clientes': [],
            'todos_ids': [],
        }

    # Comerciales directos del banco
    comerciales_ids = list(
        Subordinacion.objects.filter(jefe=banco, activo=True)
        .values_list('subordinado_id', flat=True)
    )

    # Clientes: por Fondo asignado por el banco o por sus comerciales
    clientes_por_fondo = list(
        Fondo.objects.filter(
            Q(asignado_por=banco) | Q(asignado_por__in=comerciales_ids),
            activo=True
        ).values_list('usuario_id', flat=True).distinct()
    )
    # Clientes: por Subordinación de los comerciales
    clientes_por_sub = list(
        Subordinacion.objects.filter(jefe__in=comerciales_ids, activo=True)
        .values_list('subordinado_id', flat=True)
    )
    clientes_ids = list(set(clientes_por_pago := clientes_por_fondo + clientes_por_sub))

    return {
        'banco': banco,
        'comerciales': list(User.objects.filter(id__in=comerciales_ids)),
        'clientes': list(User.objects.filter(id__in=clientes_ids)),
        'todos_ids': list({banco.id, *comerciales_ids, *clientes_ids}),
    }

# FIX_POSTPAGO_V2: descuento postpago con acreditación al gestor

# FASE1_POSTPAGO_V1_HELPER
def _aplicar_ingreso_a_fondo(cliente, gestor, forma_pago, monto):
    """
    Aplica un ingreso (recarga/premio) al cliente:
    1. Si el cliente tiene Postpago con saldo < 0 para (gestor, forma_pago), paga la deuda.
    2. El resto va al Fondo (get_or_create).
    Devuelve (monto_al_fondo, monto_pagado_postpago).
    """
    from decimal import Decimal
    from django.db import transaction
    from roles.models import Postpago, Fondo

    monto = Decimal(str(monto))
    if monto <= 0:
        return Decimal('0.00'), Decimal('0.00')

    with transaction.atomic():
        # 1. Postpago (si hay deuda)
        pagado = Decimal('0.00')
        pp = Postpago.objects.select_for_update().filter(
            cliente=cliente, gestor=gestor, forma_pago=forma_pago,
        ).first()
        if pp and pp.saldo < 0:
            deuda = -pp.saldo  # saldo negativo → deuda positiva
            pagado = min(monto, deuda)
            pp.saldo += pagado
            if pp.saldo == 0:
                pp.activo = False
            pp.save(update_fields=['saldo', 'activo', 'actualizado_en'])
            monto -= pagado

        # 2. Resto al Fondo
        al_fondo = monto
        if al_fondo > 0:
            fondo, _ = Fondo.objects.select_for_update().get_or_create(
                usuario=cliente, forma_pago=forma_pago,
                defaults={'monto': Decimal('0.00'), 'activo': True, 'asignado_por': gestor},
            )
            fondo.monto += al_fondo
            fondo.activo = True
            if not fondo.asignado_por_id and gestor:
                fondo.asignado_por = gestor
            fondo.save(update_fields=['monto', 'activo', 'asignado_por'] if fondo.asignado_por_id else ['monto', 'activo'])

        return al_fondo, pagado
