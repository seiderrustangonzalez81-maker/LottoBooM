"""
FIX_REVERSION_DUPLICADOS_V1
============================
Revierte recargas duplicadas por doble submit.

Reglas:
- Por cada MovimientoFondo duplicado:
  · Resta del Fondo lo que alcance (hasta dejar el fondo en 0)
  · Crea Postpago por la diferencia (deuda con el gestor)
  · Crea MovimientoFondo tipo='ajuste' con motivo profesional
  · Marca el original como revertido
  · Notifica al cliente

Ejecutar UNA vez. Si se vuelve a ejecutar, salta los ya revertidos.
"""
import os
import sys
sys.path.insert(0, '/home/LottoBooM')  # FIX_PATH_V1: añadir raíz al path
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'LottoBooM.settings')
import django
django.setup()

from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from roles.models import MovimientoFondo, Fondo, Postpago


DUP_IDS = [1836, 1802, 1792, 1793, 1768, 1749, 1716]


def notificar_cliente(usuario, monto_descontado, monto_deuda, mov_original_id):
    """Envía notificación al cliente explicando el ajuste."""
    try:
        from roles.utils import crear_notificacion
    except ImportError:
        try:
            from usuarios.utils import crear_notificacion
        except ImportError:
            print(f'   ⚠️  No se pudo importar crear_notificacion — se omite')
            return

    # Mensaje profesional
    if monto_deuda > 0:
        mensaje = (
            f'ℹ️ Ajuste de fondo: se detectó una recarga duplicada por un error '
            f'técnico del sistema. Se descontaron ${monto_descontado} de tu fondo '
            f'y el saldo restante (${monto_deuda}) quedó registrado como deuda. '
            f'Disculpa las molestias. Si tienes dudas, contacta a soporte.'
        )
    else:
        mensaje = (
            f'ℹ️ Ajuste de fondo: se detectó una recarga duplicada por un error '
            f'técnico del sistema. Se descontaron ${monto_descontado} de tu fondo. '
            f'Disculpa las molestias.'
        )

    try:
        crear_notificacion(
            usuario=usuario,
            tipo='info',
            mensaje=mensaje,
            datos={
                'tipo_ajuste': 'reversion_duplicado',
                'movimiento_original_id': mov_original_id,
                'monto_descontado': float(monto_descontado),
                'monto_deuda': float(monto_deuda),
            },
            prioridad='alta',
            categoria='financiera',
        )
        print(f'   ✅ Notificación enviada a {usuario.username}')
    except Exception as e:
        print(f'   ⚠️  No se pudo notificar: {e}')


def ejecutar():
    with transaction.atomic():
        total_fondo = Decimal('0')
        total_deuda = Decimal('0')
        procesados = 0

        for mid in DUP_IDS:
            dup = MovimientoFondo.objects.select_for_update().get(id=mid)

            # Verificar si ya se revirtió
            dt = dup.datos_transferencia or {}
            if dt.get('revertido_por_ajuste_id'):
                print(f'  ⏭️  [{mid}] ya revertido — skip')
                continue

            f = Fondo.objects.select_for_update().filter(
                usuario=dup.receptor, forma_pago=dup.forma_pago, activo=True
            ).first()

            fondo_actual = f.monto if f else Decimal('0')
            monto_dup = dup.monto

            if fondo_actual >= monto_dup:
                descuento = monto_dup
                deuda = Decimal('0')
            else:
                descuento = fondo_actual
                deuda = monto_dup - fondo_actual

            # 1) Restar del Fondo
            saldo_antes = fondo_actual
            if descuento > 0 and f:
                f.monto -= descuento
                f.save(update_fields=['monto', 'actualizado_en'])
            saldo_despues = f.monto if f else Decimal('0')

            # 2) Movimiento de ajuste (compensatorio)
            ajuste = MovimientoFondo.objects.create(
                emisor=None,
                receptor=dup.receptor,
                forma_pago=dup.forma_pago,
                monto=-descuento,
                tipo='ajuste',
                estado='confirmado',
                motivo=f'Ajuste por recarga duplicada — ref #{mid}',
                nota=(
                    f'Ajuste automático: se detectó una recarga duplicada por error '
                    f'técnico. Original: ${monto_dup}.'
                ),
                saldo_antes=saldo_antes,
                saldo_despues=saldo_despues,
                datos_transferencia={
                    'tipo_operacion': 'reversion_duplicado',
                    'movimiento_original_id': mid,
                    'monto_original': float(monto_dup),
                    'monto_descontado_fondo': float(descuento),
                    'monto_a_deuda': float(deuda),
                },
            )

            # 3) Marcar original como revertido
            dt['revertido_por_ajuste_id'] = ajuste.id
            dt['revertido_en'] = timezone.now().isoformat()
            dup.datos_transferencia = dt
            dup.save(update_fields=['datos_transferencia'])

            # 4) Deuda → Postpago
            if deuda > 0:
                pp = Postpago.objects.select_for_update().filter(
                    cliente=dup.receptor,
                    gestor=dup.emisor,
                    forma_pago=dup.forma_pago,
                ).first()
                if not pp:
                    pp = Postpago.objects.create(
                        cliente=dup.receptor,
                        gestor=dup.emisor,
                        forma_pago=dup.forma_pago,
                        saldo=Decimal('0'),
                        activo=True,
                    )
                saldo_pp_antes = pp.saldo
                pp.saldo -= deuda
                pp.activo = True
                pp.save(update_fields=['saldo', 'activo', 'actualizado_en'])

                MovimientoFondo.objects.create(
                    emisor=dup.emisor,
                    receptor=dup.receptor,
                    forma_pago=dup.forma_pago,
                    monto=-deuda,
                    tipo='ajuste',
                    estado='confirmado',
                    motivo=f'Deuda por reversión de recarga duplicada — ref #{mid}',
                    nota=(
                        f'Fondo insuficiente para cubrir la reversión. '
                        f'${deuda} registrados como deuda pendiente con {dup.emisor.username if dup.emisor else "—"}.'
                    ),
                    datos_transferencia={
                        'tipo_operacion': 'deuda_reversion_duplicado',
                        'movimiento_original_id': mid,
                        'postpago_id': pp.id,
                        'saldo_pp_antes': float(saldo_pp_antes),
                        'saldo_pp_despues': float(pp.saldo),
                    },
                )

            # 5) Notificar al cliente
            notificar_cliente(
                usuario=dup.receptor,
                monto_descontado=descuento,
                monto_deuda=deuda,
                mov_original_id=mid,
            )

            print(f'  ✅ [{mid}] {dup.receptor.username} → Fondo −${descuento}, Deuda +${deuda}')
            total_fondo += descuento
            total_deuda += deuda
            procesados += 1

        print()
        print('═' * 95)
        print(f'  Reversiones completadas: {procesados}')
        print(f'  Total Fondo descontado:   ${total_fondo}')
        print(f'  Total Deuda creada:       ${total_deuda}')
        print('═' * 95)


if __name__ == '__main__':
    ejecutar()
