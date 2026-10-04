# usuarios/utils.py
# -*- coding: utf-8 -*-
from decimal import Decimal
from django.db.models import Sum, Q  # Q importada por si se necesita en futuras consultas
from django.contrib.auth.models import User

# Modelos correctamente importados desde sus apps correspondientes
from roles.models import Fondo, MovimientoFondo, Comision, Subordinacion, Rol
from jugadas.models import Jugada  # ✅ CORRECTO: Jugada está en jugadas.models


# ============================================================
# FUNCIÓN: CALCULAR FONDO DE COMERCIAL CON SU BANCO
# ============================================================
def calcular_fondo_comercial(comercial, banco):
    """
    Calcula el fondo neto de un comercial con su banco.

    Fórmula:
    fondo = (total_jugadas_recibidas - total_comisiones_banco - total_premios_pagados - total_enviado_banco + total_recibido_banco)
    """
    # 1. Total de jugadas recibidas (de sus clientes)
    total_jugadas = Jugada.objects.filter(
        comercial=comercial,
        estado__in=['confirmada', 'ganadora', 'perdedora']
    ).aggregate(total=Sum('monto'))['total'] or Decimal('0.00')

    # 2. Total de comisiones del banco sobre esas jugadas
    comision_obj = Comision.objects.filter(
        banco=banco,
        comercial=comercial,
        activo=True
    ).first()
    porcentaje_comision = comision_obj.porcentaje if comision_obj else Decimal('0.00')
    total_comisiones = (total_jugadas * porcentaje_comision) / Decimal('100.00')

    # 3. Total de premios pagados a clientes
    total_premios = MovimientoFondo.objects.filter(
        emisor=comercial,
        tipo='premio',
        estado='confirmado'
    ).aggregate(total=Sum('monto'))['total'] or Decimal('0.00')

    # 4. Total enviado al banco
    total_enviado_banco = MovimientoFondo.objects.filter(
        emisor=comercial,
        receptor=banco,
        tipo__in=['envio_banco', 'pago_banco'],
        estado='confirmado'
    ).aggregate(total=Sum('monto'))['total'] or Decimal('0.00')

    # 5. Total recibido del banco
    total_recibido_banco = MovimientoFondo.objects.filter(
        emisor=banco,
        receptor=comercial,
        tipo__in=['recibo_banco', 'recarga_banco'],
        estado='confirmado'
    ).aggregate(total=Sum('monto'))['total'] or Decimal('0.00')

    # 6. Fondo neto
    fondo_neto = (
        total_jugadas
        - total_comisiones
        - total_premios
        - total_enviado_banco
        + total_recibido_banco
    )

    return {
        'total_jugadas': total_jugadas,
        'total_comisiones': total_comisiones,
        'total_premios': total_premios,
        'total_enviado_banco': total_enviado_banco,
        'total_recibido_banco': total_recibido_banco,
        'fondo_neto': fondo_neto,
        'porcentaje_comision': porcentaje_comision,
    }


# ============================================================
# FUNCIÓN: CALCULAR FONDO TOTAL DE UN BANCO
# ============================================================
def calcular_fondo_banco(banco):
    """
    Calcula el fondo total de un banco:
    = fondos de clientes directos + fondos de comerciales + fondo propio del banco
    """
    # 1. Fondos de clientes directos (asignado_por = banco)
    clientes_directos_ids = Fondo.objects.filter(
        asignado_por=banco,
        activo=True
    ).values_list('usuario_id', flat=True).distinct()

    fondos_clientes_directos = Fondo.objects.filter(
        usuario__in=clientes_directos_ids,
        asignado_por=banco,
        activo=True
    ).aggregate(total=Sum('monto'))['total'] or Decimal('0.00')

    # 2. Fondos de comerciales (que tienen a este banco como jefe)
    comerciales_ids = Subordinacion.objects.filter(
        jefe=banco,
        activo=True
    ).values_list('subordinado_id', flat=True)

    fondos_comerciales = Fondo.objects.filter(
        usuario__in=comerciales_ids,
        asignado_por=banco,
        activo=True
    ).aggregate(total=Sum('monto'))['total'] or Decimal('0.00')

    # 3. Fondos propios del banco
    fondo_propio = Fondo.objects.filter(
        usuario=banco,
        activo=True
    ).aggregate(total=Sum('monto'))['total'] or Decimal('0.00')

    return {
        'fondos_clientes_directos': fondos_clientes_directos,
        'fondos_comerciales': fondos_comerciales,
        'fondo_propio': fondo_propio,
        'total_banco': fondos_clientes_directos + fondos_comerciales + fondo_propio,
    }


# ============================================================
# FUNCIÓN: OBTENER ROL DEL USUARIO (AUXILIAR)
# ============================================================
def get_rol_usuario(usuario):
    """
    Retorna el tipo de rol activo del usuario, o None si no tiene.
    """
    if not usuario or not usuario.is_authenticated:
        return None
    rol = Rol.objects.filter(usuario=usuario, activo=True).first()
    return rol.tipo if rol else None


# ============================================================
# FUNCIÓN: VALIDAR TELÉFONO INTERNACIONAL
# ============================================================
def validar_telefono_internacional(telefono):
    """
    Valida y formatea un número de teléfono a formato internacional.
    Si el teléfono es None o está vacío, retorna None.
    """
    if not telefono:
        return None

    # Eliminar espacios y caracteres especiales
    telefono_limpio = ''.join(filter(str.isdigit, str(telefono)))

    # Si no tiene código de país, asumir +1 (EE.UU./Canadá) como ejemplo
    if len(telefono_limpio) == 10:
        telefono_limpio = '1' + telefono_limpio

    # Si tiene 11 dígitos y empieza con 1, es formato internacional
    if len(telefono_limpio) == 11 and telefono_limpio.startswith('1'):
        return '+' + telefono_limpio

    # Si ya tiene el signo +, devolverlo tal cual
    if str(telefono).startswith('+'):
        return telefono

    # Si no, asumir que necesita el prefijo internacional
    return '+' + telefono_limpio