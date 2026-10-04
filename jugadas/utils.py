# -*- coding: utf-8 -*-
# UNIFICADO_ROLES_V1: postpago unificado en roles.models.Postpago
from decimal import Decimal

from django.db import transaction
from django.db.models import Q, Sum


# ============================================================
# OTORGAR POSTPAGO — delega a roles.utils.agregar_postpago
# ============================================================
def otorgar_postpago(gestor, cliente, monto, notas='', forma_pago=None):
    """
    Wrapper de compatibilidad. Delega a roles.utils.agregar_postpago.
    Cualquier vía de asignación de postpago usa el mismo modelo.
    """
    from roles.utils import agregar_postpago
    return agregar_postpago(
        cliente=cliente,
        gestor=gestor,
        monto=monto,
        concepto=notas or '',
        forma_pago=forma_pago,
    )


# ============================================================
# CONSUMIR POSTPAGO — delega a roles.utils.descontar_postpago
# ============================================================
def consumir_postpago(cliente, monto_necesario, gestor, origen_id=None, concepto=''):
    """
    Wrapper de compatibilidad. Delega a roles.utils.descontar_postpago.
    Devuelve el monto realmente descontado.
    """
    from roles.utils import descontar_postpago
    if not gestor:
        return Decimal('0.00')
    try:
        monto_necesario = Decimal(str(monto_necesario))
    except Exception:
        return Decimal('0.00')
    if monto_necesario <= 0:
        return Decimal('0.00')
    return descontar_postpago(
        cliente=cliente,
        monto=monto_necesario,
        tipo='apuesta',
        origen_id=origen_id,
        concepto=concepto or 'Consumo por apuesta',
        gestor=gestor,
    )


# ============================================================
# LIQUIDAR POSTPAGO — delega a roles.utils.descontar_postpago
# ============================================================
def liquidar_postpago(cliente, monto_ingreso, origen, referencia_id, gestor=None):
    """
    Wrapper de compatibilidad. Devuelve el excedente (lo que sobra después
    de descontar el postpago).
    """
    from roles.utils import descontar_postpago
    try:
        monto_ingreso = Decimal(str(monto_ingreso))
    except Exception:
        return Decimal('0.00')
    if monto_ingreso <= 0:
        return Decimal('0.00')
    if not gestor:
        return monto_ingreso
    descontado = descontar_postpago(
        cliente=cliente,
        monto=monto_ingreso,
        tipo=origen or 'ajuste',
        origen_id=referencia_id,
        concepto=f"Liquidación {origen}",
        gestor=gestor,
    )
    return monto_ingreso - (descontado or Decimal('0.00'))


# ============================================================
# HELPERS
# ============================================================
def total_postpago_cliente(cliente, gestor=None):
    """Total pendiente de postpago del cliente (de un gestor o de todos)."""
    from roles.models import Postpago
    filtro = Q(cliente=cliente, activo=True, monto_pendiente__gt=0)
    if gestor is not None:
        filtro &= Q(gestor=gestor)
    return (
        Postpago.objects.filter(filtro).aggregate(total=Sum('monto_pendiente'))['total']
        or Decimal('0.00')
    )


def postpago_por_gestor(cliente):
    """Postpago pendiente agrupado por gestor."""
    from roles.models import Postpago
    return list(
        Postpago.objects
        .filter(cliente=cliente, activo=True, monto_pendiente__gt=0)
        .values('gestor__id', 'gestor__username')
        .annotate(
            monto_total=Sum('monto'),
            monto_pendiente=Sum('monto_pendiente'),
        )
        .order_by('gestor__username')
    )
