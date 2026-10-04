from pathlib import Path

p = Path("/home/LottoBooM/jugadas/views.py")
src = p.read_text(encoding="utf-8")

# ═══════════════════════════════════════════════════════════════
# FIX 1: Definir es_solo_editar después de es_edicion_boleta
# ═══════════════════════════════════════════════════════════════
viejo1 = '''        es_edicion_boleta = (
            modo_edicion == 'editar_boleta'
            and boleta_origen_id and boleta_origen_id.isdigit()
        )

        # Validar suma igual si modo_operacion == 'editar'
        modo_operacion = request.POST.get('modo_operacion', '')'''

nuevo1 = '''        es_edicion_boleta = (
            modo_edicion == 'editar_boleta'
            and boleta_origen_id and boleta_origen_id.isdigit()
        )

        # Validar suma igual si modo_operacion == 'editar'
        modo_operacion = request.POST.get('modo_operacion', '')

        # ═══ NUEVO: distinguir editar (sin recobro) de reenviar (con recobro) ═══
        es_solo_editar = es_edicion_boleta and modo_operacion == 'editar'
        orig_boleta_editar = None'''

if viejo1 not in src:
    print("ERROR: no encontre el bloque de es_edicion_boleta")
    raise SystemExit(1)
src = src.replace(viejo1, nuevo1, 1)
print("OK: es_solo_editar definido")

# ═══════════════════════════════════════════════════════════════
# FIX 2: En editar, NO cancelar + reusar boleta original
# ═══════════════════════════════════════════════════════════════
viejo2 = '''        with transaction.atomic():
            if es_edicion_boleta:
                orig = Boleta.objects.select_for_update().filter(id=int(boleta_origen_id)).first()
                if orig and orig.estado == 'activa':
                    ok_cancel, _, err_cancel = _do_cancelar_boleta(
                        orig, usuario, motivo='Editada y reemplazada',
                    )
                    if not ok_cancel:
                        raise ValueError(f'No se pudo cancelar la boleta original: {err_cancel}')
                elif orig and orig.estado != 'activa':
                    raise ValueError(f'La boleta original está en estado {orig.estado}, no se puede editar')
            boleta = None
            if not es_edicion_pura:
                boleta = Boleta.objects.create(
                    usuario=cliente,
                    destinatario=destinatario,
                    comercial=usuario if usuario != cliente else None,
                    creado_por=usuario,
                    forma_pago=forma_pago,
                    fecha_sorteo=fecha_apuesta,
                    metadata={
                        'origen': 'editar_boleta' if es_edicion_boleta else 'guardar_apuesta',
                        'modo': modo_edicion or 'nuevo',
                        'boleta_origen_id': int(boleta_origen_id) if es_edicion_boleta else None,
                    },
                )'''

nuevo2 = '''        with transaction.atomic():
            boleta = None

            if es_edicion_boleta:
                orig = Boleta.objects.select_for_update().filter(id=int(boleta_origen_id)).first()
                if not orig:
                    raise ValueError('Boleta original no encontrada')
                if orig.estado != 'activa':
                    raise ValueError(f'La boleta original está en estado {orig.estado}, no se puede editar')

                if es_solo_editar:
                    # ═══ MODO EDITAR: no cancelar, no reintegrar, no recobrar ═══
                    # Reusar la misma boleta: borrar jugadas viejas, agregar nuevas.
                    orig_boleta_editar = orig
                    # Preservar metadata de pago original
                    _pago_original = (orig.metadata or {}).get('pago')
                    orig.jugadas.all().delete()
                    # Actualizar campos por si cambiaron (misma FP, mismo cliente, etc.)
                    orig.forma_pago = forma_pago
                    orig.fecha_sorteo = fecha_apuesta
                    orig.save(update_fields=['forma_pago', 'fecha_sorteo', 'actualizado_en'])
                    boleta = orig
                    print(f'[editar] Reusando boleta {orig.referencia} (sin recobro)')
                else:
                    # ═══ MODO REENVIAR: cancelar (con reintegro) y crear nueva ═══
                    ok_cancel, _, err_cancel = _do_cancelar_boleta(
                        orig, usuario, motivo='Reenviada a nuevos sorteos',
                    )
                    if not ok_cancel:
                        raise ValueError(f'No se pudo cancelar la boleta original: {err_cancel}')
                    boleta = Boleta.objects.create(
                        usuario=cliente,
                        destinatario=destinatario,
                        comercial=usuario if usuario != cliente else None,
                        creado_por=usuario,
                        forma_pago=forma_pago,
                        fecha_sorteo=fecha_apuesta,
                        metadata={
                            'origen': 'reenviar',
                            'modo': 'reenviar',
                            'boleta_origen_id': int(boleta_origen_id),
                        },
                    )

            if not es_edicion_pura and boleta is None:
                boleta = Boleta.objects.create(
                    usuario=cliente,
                    destinatario=destinatario,
                    comercial=usuario if usuario != cliente else None,
                    creado_por=usuario,
                    forma_pago=forma_pago,
                    fecha_sorteo=fecha_apuesta,
                    metadata={
                        'origen': 'guardar_apuesta',
                        'modo': modo_edicion or 'nuevo',
                    },
                )'''

if viejo2 not in src:
    print("ERROR: no encontre el bloque with transaction.atomic()")
    print("Buscando variantes...")
    # Buscar por línea específica
    if "orig, usuario, motivo='Editada y reemplazada'," in src:
        print("WARN: el bloque tiene texto ligeramente distinto")
    raise SystemExit(1)
src = src.replace(viejo2, nuevo2, 1)
print("OK: modo editar reusa boleta sin cobrar")

# ═══════════════════════════════════════════════════════════════
# FIX 3: Saltar cascada de pago en modo editar
# ═══════════════════════════════════════════════════════════════
viejo3 = '''            if forma_pago and total_apostado > 0:
                monto_restante = total_apostado'''

nuevo3 = '''            # ═══ En modo editar NO se recobra: el dinero ya está pagado ═══
            if (not es_solo_editar) and forma_pago and total_apostado > 0:
                monto_restante = total_apostado'''

if viejo3 not in src:
    print("WARN: no encontre el bloque de cascada de pago")
    print("     Buscando por patron...")
    import re
    match = re.search(r"if forma_pago and total_apostado > 0:\s*\n\s*monto_restante = total_apostado", src)
    if match:
        print("OK: encontrado por regex")
    else:
        print("ERROR: no pude encontrar la cascada de pago")
        raise SystemExit(1)
else:
    src = src.replace(viejo3, nuevo3, 1)
    print("OK: cascada de pago saltada en modo editar")

# ═══════════════════════════════════════════════════════════════
# FIX 4: Preservar metadata de pago original en modo editar
# ═══════════════════════════════════════════════════════════════
viejo4 = '''            if boleta:
                boleta.metadata['pago'] = {
                    'fondo': str(monto_fondo_consumido),
                    'bono': str(monto_bono_consumido),
                    'postpago': str(monto_postpago_consumido),
                    'total': str(total_apostado),
                }
                boleta.save(update_fields=['metadata'])
                boleta.recalcular_totales()'''

nuevo4 = '''            if boleta:
                if es_solo_editar:
                    # ═══ Modo editar: preservar metadata de pago original ═══
                    # El pago no cambia, no tocamos metadata['pago']
                    pass
                else:
                    boleta.metadata['pago'] = {
                        'fondo': str(monto_fondo_consumido),
                        'bono': str(monto_bono_consumido),
                        'postpago': str(monto_postpago_consumido),
                        'total': str(total_apostado),
                    }
                    boleta.save(update_fields=['metadata'])
                boleta.recalcular_totales()'''

if viejo4 not in src:
    print("WARN: no encontre el bloque de metadata final")
else:
    src = src.replace(viejo4, nuevo4, 1)
    print("OK: metadata de pago preservada en modo editar")

p.write_text(src, encoding="utf-8")

# Verificar sintaxis
import ast
try:
    ast.parse(src)
    print("OK: sintaxis correcta")
except SyntaxError as e:
    print(f"ERROR: sintaxis linea {e.lineno}: {e.msg}")
    print(f"   {e.text}")
    raise SystemExit(1)
