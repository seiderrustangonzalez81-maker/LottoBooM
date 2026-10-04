from pathlib import Path

p = Path("/home/LottoBooM/roles/views.py")
src = p.read_text(encoding="utf-8")

if "Fondos aprobados a" in src:
    print("SKIP: ya aplicado")
    raise SystemExit(0)

viejo = """                        monto_restante = solicitud.monto
                        for fondo in fondos_gestor.order_by('id'):
                            if monto_restante <= 0:
                                break
                            if fondo.monto >= monto_restante:
                                fondo.monto -= monto_restante
                                monto_restante = 0
                            else:
                                monto_restante -= fondo.monto
                                fondo.monto = 0
                            fondo.save()
                        forma_pago = FormaPago.objects.filter(activo=True).first()
                        if forma_pago:
                            fondo_comercial, _ = Fondo.objects.get_or_create(
                                usuario=solicitud.solicitante,
                                forma_pago=forma_pago,
                                defaults={'monto': 0, 'activo': True, 'asignado_por': user}
                            )
                            fondo_comercial.monto += solicitud.monto
                            fondo_comercial.save()"""

nuevo = """                        monto_restante = solicitud.monto
                        for fondo in fondos_gestor.order_by('id'):
                            if monto_restante <= 0:
                                break
                            saldo_ant_g = fondo.monto
                            if fondo.monto >= monto_restante:
                                fondo.monto -= monto_restante
                                delta_g = -monto_restante
                                monto_restante = 0
                            else:
                                delta_g = -fondo.monto
                                monto_restante -= fondo.monto
                                fondo.monto = 0
                            fondo.save()
                            try:
                                MovimientoFondo.objects.create(
                                    emisor=user,
                                    receptor=user,
                                    forma_pago=fondo.forma_pago,
                                    monto=delta_g,
                                    tipo='ajuste',
                                    estado='confirmado',
                                    motivo='Fondos aprobados a ' + solicitud.solicitante.username + ' (solicitud #' + str(solicitud.id) + ')',
                                    saldo_antes=saldo_ant_g,
                                    saldo_despues=fondo.monto,
                                    datos_transferencia={'solicitud_id': solicitud.id, 'rol': 'emisor'},
                                )
                            except Exception:
                                pass
                        forma_pago = FormaPago.objects.filter(activo=True).first()
                        if forma_pago:
                            fondo_comercial, _ = Fondo.objects.get_or_create(
                                usuario=solicitud.solicitante,
                                forma_pago=forma_pago,
                                defaults={'monto': 0, 'activo': True, 'asignado_por': user}
                            )
                            saldo_ant_c = fondo_comercial.monto
                            fondo_comercial.monto += solicitud.monto
                            fondo_comercial.save()
                            try:
                                MovimientoFondo.objects.create(
                                    emisor=user,
                                    receptor=solicitud.solicitante,
                                    forma_pago=forma_pago,
                                    monto=solicitud.monto,
                                    tipo='ajuste',
                                    estado='confirmado',
                                    motivo='Fondos recibidos de ' + user.username + ' (solicitud #' + str(solicitud.id) + ')',
                                    saldo_antes=saldo_ant_c,
                                    saldo_despues=fondo_comercial.monto,
                                    datos_transferencia={'solicitud_id': solicitud.id, 'rol': 'receptor'},
                                )
                            except Exception:
                                pass"""

if viejo not in src:
    print("ERROR: no encontre el bloque de aprobacion de fondos")
    raise SystemExit(1)

src_new = src.replace(viejo, nuevo, 1)
p.write_text(src_new, encoding="utf-8")
print("OK aprobacion de fondos con auditoria")

import ast
ast.parse(src_new)
print("OK sintaxis")
