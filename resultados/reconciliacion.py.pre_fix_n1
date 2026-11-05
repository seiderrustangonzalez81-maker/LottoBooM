# -*- coding: utf-8 -*-
"""
FASE1_RECONCILIACION_V1
Crea premios tardíos: cuando una jugada se inserta DESPUÉS de que
el resultado ya salió, esta función verifica si ganó y crea el Premio.
"""
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


def reconciliar_premio_jugada(jugada, resultado=None, usuario_sistema=None):
    """
    Verifica si `jugada` ganó contra el `resultado` de su sorteo/fecha
    y crea el Premio si no existe.

    Returns (premio, created, error_msg).
    """
    from resultados.models import Resultado, Premio
    from resultados.views import jugada_es_ganadora

    if not jugada or not jugada.sorteo_id or not jugada.fecha_sorteo:
        return None, False, 'jugada sin sorteo/fecha'

    # 1. Si ya tiene premio, no duplicar
    try:
        existente = Premio.objects.filter(jugada=jugada).first()
        if existente:
            return existente, False, None
    except Exception as e:
        logger.warning(f'reconciliar_premio_jugada: check existente: {e}')

    # 2. Buscar resultado si no viene
    if resultado is None:
        resultado = Resultado.objects.filter(
            sorteo_id=jugada.sorteo_id,
            fecha=jugada.fecha_sorteo,
        ).first()
    if not resultado:
        return None, False, 'sin resultado'

    # 3. Verificar si ganó
    try:
        es_ganadora, multiplicador = jugada_es_ganadora(jugada, resultado)
    except Exception as e:
        logger.error(f'reconciliar_premio_jugada: jugada_es_ganadora: {e}', exc_info=True)
        return None, False, f'error jugada_es_ganadora: {e}'

    if not es_ganadora or multiplicador <= 0:
        return None, False, None

    # 4. Crear premio
    monto_premio = Decimal(str(jugada.monto)) * Decimal(multiplicador)

    try:
        # Marcar jugada
        jugada.estado = 'ganadora'
        jugada.monto_premio = monto_premio
        jugada.save(update_fields=['estado', 'monto_premio'])

        premio = Premio.objects.create(
            jugada=jugada,
            monto_premio=monto_premio,
            multiplicador_aplicado=multiplicador,
            estado='pendiente',
            cobrado=False,
            metadata={'resultado_id': resultado.id, 'reconciliado_tardio': True},
        )

        # Pago automático al fondo
        try:
            from roles.utils import _aplicar_ingreso_a_fondo
            cliente = jugada.usuario
            gestor = jugada.destinatario or cliente
            if jugada.forma_pago:
                _aplicar_ingreso_a_fondo(
                    cliente=cliente,
                    gestor=gestor,
                    forma_pago=jugada.forma_pago,
                    monto=monto_premio,
                )
                # Marcar como pagado
                premio.cobrado = True
                premio.estado = 'pagado'
                premio.fecha_pago = __import__('django.utils.timezone', fromlist=['timezone']).now()
                if usuario_sistema:
                    premio.pagado_por = usuario_sistema
                premio.save(update_fields=['cobrado', 'estado', 'fecha_pago', 'pagado_por'])
        except Exception as e:
            logger.warning(f'reconciliar_premio_jugada: pago: {e}')

        return premio, True, None
    except Exception as e:
        logger.error(f'reconciliar_premio_jugada: create: {e}', exc_info=True)
        return None, False, f'error crear premio: {e}'


def reconciliar_lote(jugadas_qs, usuario_sistema=None, limite=500):
    """
    Reconciliación masiva. Devuelve (creados, errores).
    """
    creados = 0
    errores = 0
    for j in jugadas_qs[:limite]:
        _, created, _err = reconciliar_premio_jugada(j, usuario_sistema=usuario_sistema)
        if created:
            creados += 1
        elif _err:
            errores += 1
    return creados, errores
