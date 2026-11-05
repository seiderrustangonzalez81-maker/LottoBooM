# -*- coding: utf-8 -*-
"""
Procesamiento asíncrono de premios.
Corre en un hilo; el endpoint responde de inmediato con el estado.
"""
import logging
import threading
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from django.db.models import F

logger = logging.getLogger(__name__)


def procesar_premios_background(resultado_id, usuario_id=None):
    """
    Lanza el cálculo de premios en un hilo separado.
    Se llama desde api_guardar_resultado/crear_resultado para no bloquear.
    """
    t = threading.Thread(
        target=_procesar_premios_worker,
        args=(resultado_id, usuario_id),
        daemon=True,
        name=f'premios-{resultado_id}',
    )
    t.start()
    return t


def _procesar_premios_worker(resultado_id, usuario_id=None):
    from resultados.models import Resultado, Premio
    from jugadas.models import Jugada
    from resultados.views import jugada_es_ganadora

    try:
        resultado = Resultado.objects.get(id=resultado_id)
    except Resultado.DoesNotExist:
        return

    try:
        resultado.procesamiento_estado = 'procesando'
        resultado.procesamiento_inicio = timezone.now()
        resultado.procesamiento_msg = 'Calculando premios...'
        resultado.save(update_fields=['procesamiento_estado', 'procesamiento_inicio', 'procesamiento_msg'])

        jugadas = list(Jugada.objects.filter(
            sorteo=resultado.sorteo,
            fecha_sorteo=resultado.fecha,
            estado__in=['confirmada', 'pendiente', 'ganadora'],
        ).select_related('usuario', 'forma_pago', 'forma_juego', 'destinatario'))

        # 1) Calcular todas las ganadoras en memoria (sin BD)
        ganadoras = []
        for j in jugadas:
            try:
                es_g, mult = jugada_es_ganadora(j, resultado)
                if es_g and mult > 0:
                    ganadoras.append((j, Decimal(str(j.monto)) * Decimal(str(mult)), mult))
            except Exception as e:
                logger.warning(f'jugada_es_ganadora error jugada={j.id}: {e}')

        # 2) Actualizar jugadas en batch
        for j, monto, mult in ganadoras:
            j.estado = 'ganadora'
            j.monto_premio = monto
        if ganadoras:
            Jugada.objects.bulk_update(
                [g[0] for g in ganadoras],
                ['estado', 'monto_premio'],
                batch_size=200,
            )

        # 3) Marcar perdedoras (las que no ganaron)
        ganadoras_ids = [g[0].id for g in ganadoras]
        Jugada.objects.filter(
            sorteo=resultado.sorteo,
            fecha_sorteo=resultado.fecha,
        ).exclude(id__in=ganadoras_ids).update(estado='perdedora')

        # 4) Crear premios + pagar en lote
        # Pre-cargar premios existentes para evitar N+1
        existentes = set(
            Premio.objects.filter(jugada__in=[g[0] for g in ganadoras])
            .values_list('jugada_id', flat=True)
        )

        premios_creados = 0
        for j, monto, mult in ganadoras:
            if j.id in existentes:
                continue
            try:
                with transaction.atomic():
                    premio = Premio.objects.create(
                        jugada=j,
                        monto_premio=monto,
                        multiplicador_aplicado=mult,
                        estado='pendiente',
                        cobrado=False,
                        metadata={'resultado_id': resultado.id},
                    )
                    premios_creados += 1

                    # Pago automático al fondo (por ganadora)
                    if j.forma_pago:
                        from roles.utils import _aplicar_ingreso_a_fondo
                        try:
                            _aplicar_ingreso_a_fondo(
                                cliente=j.usuario,
                                gestor=j.destinatario or j.usuario,
                                forma_pago=j.forma_pago,
                                monto=monto,
                                tipo_mov='premio',
                                extra_data={
                                    'tipo': 'premio_automatico',
                                    'premio_id': premio.id,
                                    'jugada_id': j.id,
                                    'sorteo': resultado.sorteo.nombre,
                                },
                            )
                            premio.cobrado = True
                            premio.estado = 'pagado'
                            premio.fecha_pago = timezone.now()
                            premio.save(update_fields=['cobrado', 'estado', 'fecha_pago'])
                        except Exception as e:
                            logger.warning(f'_aplicar_ingreso_a_fondo jugada={j.id}: {e}')

                    # Notificación
                    try:
                        from resultados.views import crear_notificacion  # FIX_IMPORT_NOTIF
                        crear_notificacion(
                            usuario=j.usuario,
                            tipo='premio',
                            mensaje=f"🎉 ¡Has ganado ${monto} en {resultado.sorteo.nombre}!",
                            datos={
                                'premio_id': premio.id,
                                'monto': float(monto),
                                'sorteo': resultado.sorteo.nombre,
                                'url_detalle': '/resultados/mis-premios/',
                            },
                        )
                    except Exception as e:
                        logger.warning(f'crear_notificacion jugada={j.id}: {e}')
            except Exception as e:
                logger.error(f'crear premio jugada={j.id}: {e}', exc_info=True)

        resultado.procesamiento_estado = 'completado'
        resultado.procesamiento_fin = timezone.now()
        resultado.premios_generados = premios_creados
        resultado.procesamiento_msg = f'{premios_creados} premios generados de {len(jugadas)} jugadas'
        resultado.save(update_fields=['procesamiento_estado', 'procesamiento_fin', 'premios_generados', 'procesamiento_msg'])

        logger.info(f'[premios] resultado={resultado_id} completado: {premios_creados} premios')

    except Exception as e:
        logger.error(f'[premios] error resultado={resultado_id}: {e}', exc_info=True)
        try:
            Resultado.objects.filter(id=resultado_id).update(
                procesamiento_estado='error',
                procesamiento_msg=str(e)[:255],
                procesamiento_fin=timezone.now(),
            )
        except Exception:
            pass
