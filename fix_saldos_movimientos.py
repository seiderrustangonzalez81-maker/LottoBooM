from pathlib import Path
import ast, sys

REEMPLAZOS = [
    # ═══════════════════════════════════════════════════════════
    # 1) CANCELAR BOLETA (jugadas/views.py ~línea 690)
    # ═══════════════════════════════════════════════════════════
    {
        "archivo": "jugadas/views.py",
        "label": "cancelar boleta",
        "viejo": """MovimientoFondo.objects.create(
            emisor=boleta.destinatario, receptor=boleta.usuario,
            forma_pago=forma_pago_ref, monto=monto_fondo,
            tipo='ajuste', estado='confirmado',
            datos_transferencia=f"Cancelación boleta {boleta.referencia}",
            nota=f"Reembolso por cancelación. Motivo: {motivo or 'sin motivo'}",
        )""",
        "nuevo": """MovimientoFondo.objects.create(
            emisor=boleta.destinatario, receptor=boleta.usuario,
            forma_pago=forma_pago_ref, monto=monto_fondo,
            tipo='ajuste', estado='confirmado',
            motivo=f"Cancelación boleta {boleta.referencia}",
            datos_transferencia={
                'boleta_id': boleta.id,
                'referencia': str(boleta.referencia),
                'cancelacion': True,
                'motivo': motivo or '',
            },
            nota=f"Reembolso por cancelación. Motivo: {motivo or 'sin motivo'}",
            saldo_antes=fondo.monto - monto_fondo,
            saldo_despues=fondo.monto,
        )""",
    },

    # ═══════════════════════════════════════════════════════════
    # 2a) APUESTA TOTAL (jugadas/views.py ~línea 1429)
    # ═══════════════════════════════════════════════════════════
    {
        "archivo": "jugadas/views.py",
        "label": "apuesta total",
        "viejo": """MovimientoFondo.objects.create(
                            emisor=cliente, receptor=destinatario, forma_pago=forma_pago,
                            monto=total_apostado, tipo='apuesta', estado='confirmado',
                            datos_transferencia=f"Apuesta {ref_boleta}",
                            nota=f"Apuesta realizada por {usuario.username}"
                        )""",
        "nuevo": """MovimientoFondo.objects.create(
                            emisor=cliente, receptor=destinatario, forma_pago=forma_pago,
                            monto=total_apostado, tipo='apuesta', estado='confirmado',
                            motivo=f"Apuesta {ref_boleta}",
                            datos_transferencia={
                                'referencia': str(ref_boleta),
                                'usuario': usuario.username,
                                'tipo_operacion': 'apuesta',
                            },
                            nota=f"Apuesta realizada por {usuario.username}",
                            saldo_antes=fondo.monto + monto_restante,
                            saldo_despues=fondo.monto,
                        )""",
    },

    # ═══════════════════════════════════════════════════════════
    # 2b) APUESTA PARCIAL (jugadas/views.py ~línea 1441)
    # ═══════════════════════════════════════════════════════════
    {
        "archivo": "jugadas/views.py",
        "label": "apuesta parcial",
        "viejo": """MovimientoFondo.objects.create(
                            emisor=cliente, receptor=destinatario, forma_pago=forma_pago,
                            monto=monto_descontado, tipo='apuesta', estado='confirmado',
                            datos_transferencia=f"Apuesta {ref_boleta} (parcial)",
                            nota=f"Apuesta parcial por {usuario.username}"
                        )""",
        "nuevo": """MovimientoFondo.objects.create(
                            emisor=cliente, receptor=destinatario, forma_pago=forma_pago,
                            monto=monto_descontado, tipo='apuesta', estado='confirmado',
                            motivo=f"Apuesta parcial {ref_boleta}",
                            datos_transferencia={
                                'referencia': str(ref_boleta),
                                'usuario': usuario.username,
                                'tipo_operacion': 'apuesta_parcial',
                            },
                            nota=f"Apuesta parcial por {usuario.username}",
                            saldo_antes=monto_descontado,
                            saldo_despues=Decimal('0.00'),
                        )""",
    },

    # ═══════════════════════════════════════════════════════════
    # 4) RECARGA AL CREAR CLIENTE (jugadas/views.py ~línea 2025)
    # ═══════════════════════════════════════════════════════════
    {
        "archivo": "jugadas/views.py",
        "label": "recarga al crear cliente",
        "viejo": """MovimientoFondo.objects.create(
                    emisor=user, receptor=nuevo, forma_pago=recarga_fp,
                    monto=recarga_monto, tipo='recarga', estado='confirmado',
                    datos_transferencia="Recarga inicial - " + recarga_fp.nombre,
                    nota="Recarga inicial al crear cliente " + nuevo.username,
                )""",
        "nuevo": """_f4 = Fondo.objects.filter(
                    usuario=nuevo, forma_pago=recarga_fp, activo=True
                ).first()
                _saldo_c4 = _f4.monto if _f4 else Decimal('0.00')
                MovimientoFondo.objects.create(
                    emisor=user, receptor=nuevo, forma_pago=recarga_fp,
                    monto=recarga_monto, tipo='recarga', estado='confirmado',
                    motivo=f"Recarga inicial · {recarga_fp.nombre}",
                    datos_transferencia={
                        'cliente_nuevo': nuevo.username,
                        'forma_pago': recarga_fp.nombre,
                        'tipo_operacion': 'recarga_inicial',
                    },
                    nota="Recarga inicial al crear cliente " + nuevo.username,
                    saldo_antes=_saldo_c4 - recarga_monto,
                    saldo_despues=_saldo_c4,
                )""",
    },

    # ═══════════════════════════════════════════════════════════
    # 5a) DUPLICADO TOTAL (jugadas/views.py ~línea 2610)
    # ═══════════════════════════════════════════════════════════
    {
        "archivo": "jugadas/views.py",
        "label": "duplicado total",
        "viejo": """MovimientoFondo.objects.create(
                        emisor=cliente, receptor=destinatario, forma_pago=forma_pago,
                        monto=total_apostado, tipo='apuesta', estado='confirmado',
                        datos_transferencia=f"Apuesta {ref_nueva}",
                        nota=f"Duplicado por {user.username}",
                    )""",
        "nuevo": """MovimientoFondo.objects.create(
                        emisor=cliente, receptor=destinatario, forma_pago=forma_pago,
                        monto=total_apostado, tipo='apuesta', estado='confirmado',
                        motivo=f"Duplicado {ref_nueva}",
                        datos_transferencia={
                            'referencia': str(ref_nueva),
                            'usuario': user.username,
                            'tipo_operacion': 'duplicado_total',
                        },
                        nota=f"Duplicado por {user.username}",
                        saldo_antes=fondo.monto + monto_restante,
                        saldo_despues=fondo.monto,
                    )""",
    },

    # ═══════════════════════════════════════════════════════════
    # 5b) DUPLICADO PARCIAL (jugadas/views.py ~línea 2622)
    # ═══════════════════════════════════════════════════════════
    {
        "archivo": "jugadas/views.py",
        "label": "duplicado parcial",
        "viejo": """MovimientoFondo.objects.create(
                        emisor=cliente, receptor=destinatario, forma_pago=forma_pago,
                        monto=monto_descontado, tipo='apuesta', estado='confirmado',
                        datos_transferencia=f"Apuesta {ref_nueva} (parcial)",
                        nota=f"Duplicado parcial por {user.username}",
                    )""",
        "nuevo": """MovimientoFondo.objects.create(
                        emisor=cliente, receptor=destinatario, forma_pago=forma_pago,
                        monto=monto_descontado, tipo='apuesta', estado='confirmado',
                        motivo=f"Duplicado parcial {ref_nueva}",
                        datos_transferencia={
                            'referencia': str(ref_nueva),
                            'usuario': user.username,
                            'tipo_operacion': 'duplicado_parcial',
                        },
                        nota=f"Duplicado parcial por {user.username}",
                        saldo_antes=monto_descontado,
                        saldo_despues=Decimal('0.00'),
                    )""",
    },

    # ═══════════════════════════════════════════════════════════
    # 6) CANCELAR JUGADA INDIVIDUAL (jugadas/views.py ~línea 2758)
    # ═══════════════════════════════════════════════════════════
    {
        "archivo": "jugadas/views.py",
        "label": "cancelar jugada",
        "viejo": """MovimientoFondo.objects.create(
                    emisor=jugada.destinatario, receptor=jugada.usuario,
                    forma_pago=jugada.forma_pago, monto=jugada.monto,
                    tipo='ajuste', estado='confirmado',
                    datos_transferencia=f"Cancelación de jugada #{jugada.id}",
                    nota=f"Cancelación por {user.username}"
                )""",
        "nuevo": """MovimientoFondo.objects.create(
                    emisor=jugada.destinatario, receptor=jugada.usuario,
                    forma_pago=jugada.forma_pago, monto=jugada.monto,
                    tipo='ajuste', estado='confirmado',
                    motivo=f"Cancelación jugada #{jugada.id}",
                    datos_transferencia={
                        'jugada_id': jugada.id,
                        'cancelacion': True,
                        'cancelado_por': user.username,
                    },
                    nota=f"Cancelación por {user.username}",
                    saldo_antes=fondo.monto - jugada.monto,
                    saldo_despues=fondo.monto,
                )""",
    },

    # ═══════════════════════════════════════════════════════════
    # 7) PREMIO AUTOMÁTICO (resultados/views.py ~línea 678)
    #    Solo parche parcial: motivo. Saldos quedan pendientes
    #    hasta ver el contexto completo del fondo.
    # ═══════════════════════════════════════════════════════════
    {
        "archivo": "resultados/views.py",
        "label": "premio automático",
        "viejo": """                        MovimientoFondo.objects.create(
                            emisor=None, receptor=cliente,
                            forma_pago=forma_pago, monto=premio.monto_premio,
                            tipo='premio', estado='confirmado',
                            datos_transferencia={""",
        "nuevo": """                        _fp_pre = Fondo.objects.filter(
                            usuario=cliente, forma_pago=forma_pago, activo=True
                        ).first()
                        _saldo_pre = _fp_pre.monto if _fp_pre else Decimal('0.00')
                        MovimientoFondo.objects.create(
                            emisor=None, receptor=cliente,
                            forma_pago=forma_pago, monto=premio.monto_premio,
                            tipo='premio', estado='confirmado',
                            motivo=f"Premio {resultado.sorteo.nombre} · jugada #{jugada.id}",
                            saldo_antes=_saldo_pre - premio.monto_premio,
                            saldo_despues=_saldo_pre,
                            datos_transferencia={""",
    },
]


def aplicar():
    cambios = []
    errores = []
    for r in REEMPLAZOS:
        p = Path("/home/LottoBooM") / r["archivo"]
        src = p.read_text(encoding="utf-8")

        if r["nuevo"] in src:
            cambios.append((r["label"], "SKIP", "ya aplicado"))
            continue

        if r["viejo"] not in src:
            errores.append((r["label"], "NO MATCH"))
            continue

        src = src.replace(r["viejo"], r["nuevo"], 1)
        p.write_text(src, encoding="utf-8")
        cambios.append((r["label"], "OK", ""))

    print("\n─── RESULTADO ───")
    for label, status, extra in cambios:
        icon = {"OK": "✔", "SKIP": "○", "NO MATCH": "✘"}[status]
        print(f"  {icon} [{status}] {label} {extra}")

    if errores:
        print("\n⚠  BLOQUES NO MATCHEADOS:")
        for label, _ in errores:
            print(f"   • {label}")

    # Verificar sintaxis de cada archivo modificado
    print("\n─── SINTAXIS ───")
    for archivo in set(r["archivo"] for r in REEMPLAZOS):
        p = Path("/home/LottoBooM") / archivo
        try:
            ast.parse(p.read_text(encoding="utf-8"))
            print(f"  ✔ {archivo}")
        except SyntaxError as e:
            print(f"  ✘ {archivo} línea {e.lineno}: {e.msg}")
            return 1
    return 0 if not errores else 2


if __name__ == "__main__":
    sys.exit(aplicar())
