from pathlib import Path
import ast

p = Path("/home/LottoBooM/roles/utils.py")
src = p.read_text(encoding="utf-8")

if "FIX_PRESTAMO_INGRESO_V1" in src:
    print("SKIP: ya aplicado")
    raise SystemExit(0)

# 1. Cambiar firma
viejo_firma = "def _aplicar_ingreso_a_fondo(cliente, gestor, forma_pago, monto):"
nuevo_firma = "def _aplicar_ingreso_a_fondo(cliente, gestor, forma_pago, monto, _skip_prestamos=False, _return_detalle=False):"

if viejo_firma not in src:
    print("ERROR: no encontré la firma")
    raise SystemExit(1)
src = src.replace(viejo_firma, nuevo_firma, 1)

# 2. Insertar bloque de préstamos antes del bloque "al_fondo = monto"
viejo_bloque = """        al_fondo = monto
        if al_fondo > 0:
            fondo, _ = Fondo.objects.select_for_update().get_or_create("""

nuevo_bloque = """        # ═══ FIX_PRESTAMO_INGRESO_V1: cobrar préstamos FIFO ═══
        descuento_prestamo = Decimal('0.00')
        pagos_prestamos = []
        if not _skip_prestamos and monto > 0:
            from roles.models import Prestamo
            sobrante = monto
            prestamos = Prestamo.objects.select_for_update().filter(
                solicitante=cliente,
                forma_pago=forma_pago,
                estado='aprobado',
                saldo_pendiente__gt=0,
            )
            if gestor:
                prestamos = prestamos.filter(gestor=gestor)
            prestamos = prestamos.order_by('fecha_aprobacion', 'id')

            for p_obj in prestamos:
                if sobrante <= 0:
                    break
                pago = min(sobrante, p_obj.saldo_pendiente)
                p_obj.saldo_pendiente -= pago
                p_obj.monto_pagado += pago
                if p_obj.saldo_pendiente <= 0:
                    p_obj.estado = 'saldado'
                    p_obj.fecha_saldado = timezone.now()
                    p_obj.saldo_pendiente = Decimal('0.00')
                p_obj.save(update_fields=['saldo_pendiente', 'monto_pagado', 'estado', 'fecha_saldado'])

                # Acreditar al prestamista (sin recursión de préstamos)
                try:
                    _aplicar_ingreso_a_fondo(
                        cliente=p_obj.prestamista,
                        gestor=p_obj.gestor or gestor,
                        forma_pago=forma_pago,
                        monto=pago,
                        _skip_prestamos=True,
                    )
                except Exception as e:
                    logger.warning(f"[FIX_PRESTAMO_INGRESO_V1] Error acreditando prestamista: {e}")

                # Movimiento descriptivo
                try:
                    MovimientoFondo.objects.create(
                        emisor=cliente, receptor=p_obj.prestamista, forma_pago=forma_pago,
                        monto=pago, tipo='pago_deuda', estado='confirmado',
                        motivo=f"Cobro automático préstamo #{p_obj.id}",
                        datos_transferencia={
                            'prestamo_id': p_obj.id,
                            'tipo_operacion': 'cobro_automatico_prestamo',
                            'prestamista': p_obj.prestamista.username,
                        },
                        nota=f"Cobro automático al recibir ingreso",
                    )
                except Exception:
                    pass

                # Notificaciones
                try:
                    _crear_notificacion(
                        usuario=p_obj.prestamista,
                        tipo='prestamo',
                        mensaje=f"💰 Recibiste ${pago} del préstamo a {cliente.username} (cobro automático).",
                        datos={'prestamo_id': p_obj.id, 'monto': float(pago), 'url_detalle': '/roles/mis-prestamos/'},
                        prioridad='media', categoria='financiera',
                    )
                    if p_obj.estado == 'saldado':
                        _crear_notificacion(
                            usuario=cliente,
                            tipo='prestamo',
                            mensaje=f"🎉 Préstamo #{p_obj.id} con {p_obj.prestamista.username} totalmente saldado.",
                            datos={'prestamo_id': p_obj.id, 'url_detalle': '/roles/mis-prestamos/'},
                            prioridad='media', categoria='financiera',
                        )
                        _crear_notificacion(
                            usuario=p_obj.prestamista,
                            tipo='prestamo',
                            mensaje=f"🎉 Préstamo #{p_obj.id} a {cliente.username} totalmente saldado.",
                            datos={'prestamo_id': p_obj.id, 'url_detalle': '/roles/mis-prestamos/'},
                            prioridad='media', categoria='financiera',
                        )
                except Exception:
                    pass

                sobrante -= pago
                descuento_prestamo += pago
                pagos_prestamos.append({
                    'prestamo_id': p_obj.id,
                    'prestamista': p_obj.prestamista.username,
                    'monto': float(pago),
                })

            monto = sobrante

        # ═══ FIN FIX_PRESTAMO_INGRESO_V1 ═══

        al_fondo = monto
        if al_fondo > 0:
            fondo, _ = Fondo.objects.select_for_update().get_or_create("""

if viejo_bloque not in src:
    print("ERROR: no encontré el bloque 'al_fondo = monto'")
    raise SystemExit(1)
src = src.replace(viejo_bloque, nuevo_bloque, 1)

# 3. Cambiar el return
viejo_return = "        return al_fondo, pagado"
nuevo_return = """        if _return_detalle:
            return al_fondo, pagado, descuento_prestamo, pagos_prestamos
        return al_fondo, pagado"""

if viejo_return not in src:
    print("ERROR: no encontré el return")
    raise SystemExit(1)
src = src.replace(viejo_return, nuevo_return, 1)

try:
    ast.parse(src)
except SyntaxError as e:
    print(f"ERROR sintaxis: {e}")
    raise SystemExit(1)

p.write_text(src, encoding="utf-8")
print("OK: FIX_PRESTAMO_INGRESO_V1 aplicado")
