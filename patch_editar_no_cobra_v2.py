from pathlib import Path
import re
import sys

p = Path("/home/LottoBooM/jugadas/views.py")
src = p.read_text(encoding="utf-8")
original = src
cambios = []

# ═══════════════════════════════════════════════════════════════
# PASO 1: Añadir es_solo_editar después de es_edicion_boleta
# ═══════════════════════════════════════════════════════════════
patron1 = re.compile(
    r"(\s+modo_operacion\s*=\s*request\.POST\.get\('modo_operacion',\s*''\))",
    re.MULTILINE,
)

if "es_solo_editar" in src:
    cambios.append("PASO 1: SKIP (ya existe)")
else:
    m = patron1.search(src)
    if not m:
        cambios.append("PASO 1: ERROR (no encontre modo_operacion)")
    else:
        indent = re.match(r"^(\s*)", m.group(0)).group(1)
        nuevo = m.group(1) + f"\n{indent}es_solo_editar = (es_edicion_boleta and modo_operacion == 'editar')"
        src = src[:m.end()] + nuevo + src[m.end():]
        cambios.append("PASO 1: OK (es_solo_editar definido)")

p.write_text(src, encoding="utf-8")  # ← Guardar inmediatamente
print(cambios[-1])

# ═══════════════════════════════════════════════════════════════
# PASO 2: Reemplazar bloque if es_edicion_boleta (con regex flexible)
# ═══════════════════════════════════════════════════════════════
patron2 = re.compile(
    r"(            if es_edicion_boleta:.*?raise ValueError\(f'La boleta original está en estado \{orig\.estado\}, no se puede editar'\)\s*\n)(\s+)(boleta = None)",
    re.DOTALL,
)

if "Modo editar: no cancelar" in src:
    cambios.append("PASO 2: SKIP (ya existe)")
else:
    m = patron2.search(src)
    if not m:
        cambios.append("PASO 2: ERROR (no matchea bloque if es_edicion_boleta)")
        print(cambios[-1])
    else:
        bloque_original = m.group(1)
        indent = m.group(2)
        resto = m.group(3)

        # Determinar indentación base (12 espacios típicos)
        indent_if = "            "  # 12
        indent_body = "                "  # 16

        bloque_nuevo = f'''{indent_if}if es_edicion_boleta:
{indent_body}orig = Boleta.objects.select_for_update().filter(id=int(boleta_origen_id)).first()
{indent_body}if not orig:
{indent_body}    raise ValueError('Boleta original no encontrada')
{indent_body}if orig.estado != 'activa':
{indent_body}    raise ValueError(f'La boleta original está en estado {{orig.estado}}, no se puede editar')

{indent_body}if es_solo_editar:
{indent_body}    # Modo editar: no cancelar, no reintegrar, reusar la misma boleta
{indent_body}    orig.jugadas.all().delete()
{indent_body}    orig.forma_pago = forma_pago
{indent_body}    orig.fecha_sorteo = fecha_apuesta
{indent_body}    orig.save(update_fields=['forma_pago', 'fecha_sorteo', 'actualizado_en'])
{indent_body}    boleta = orig
{indent_body}else:
{indent_body}    # Modo reenviar: cancelar (con reintegro) y crear nueva
{indent_body}    ok_cancel, _, err_cancel = _do_cancelar_boleta(
{indent_body}        orig, usuario, motivo='Reenviada a nuevos sorteos',
{indent_body}    )
{indent_body}    if not ok_cancel:
{indent_body}        raise ValueError(f'No se pudo cancelar la boleta original: {{err_cancel}}')
{indent_body}    boleta = Boleta.objects.create(
{indent_body}        usuario=cliente,
{indent_body}        destinatario=destinatario,
{indent_body}        comercial=usuario if usuario != cliente else None,
{indent_body}        creado_por=usuario,
{indent_body}        forma_pago=forma_pago,
{indent_body}        fecha_sorteo=fecha_apuesta,
{indent_body}        metadata={{
{indent_body}            'origen': 'reenviar',
{indent_body}            'modo': 'reenviar',
{indent_body}            'boleta_origen_id': int(boleta_origen_id),
{indent_body}        }},
{indent_body}    )

{indent}'''
        # Reemplazar: el bloque viejo + indent + "boleta = None"
        # Necesito también reemplazar el "if not es_edicion_pura:" para que no recree la boleta
        src = src[:m.start()] + bloque_nuevo + resto + src[m.end():]
        cambios.append("PASO 2: OK (bloque reescrito)")
        print(cambios[-1])

p.write_text(src, encoding="utf-8")

# ═══════════════════════════════════════════════════════════════
# PASO 3: Modificar el "if not es_edicion_pura:" para que no recree
# ═══════════════════════════════════════════════════════════════
patron3 = re.compile(
    r"(\s+)(boleta\s*=\s*None\s*\n\s+)if not es_edicion_pura:\s*\n(\s+)boleta\s*=\s*Boleta\.objects\.create\(",
    re.MULTILINE,
)

if "boleta = boleta or" in src or "# Ya se manejo en el bloque anterior" in src:
    cambios.append("PASO 3: SKIP (ya existe)")
else:
    m = patron3.search(src)
    if not m:
        cambios.append("PASO 3: WARN (no matchea boleta = None + if not es_edicion_pura)")
        print(cambios[-1])
    else:
        # Cambiar "boleta = None" por algo que no pise
        # Y "if not es_edicion_pura:" por "if not es_edicion_pura and boleta is None:"
        viejo3 = m.group(0)
        nuevo3 = f'''{m.group(1)}# Ya se manejo en el bloque anterior si es edicion_boleta
{m.group(1)}if not es_edicion_pura and boleta is None:
{m.group(3)}boleta = Boleta.objects.create('''
        src = src[:m.start()] + nuevo3 + src[m.end():]
        cambios.append("PASO 3: OK (no recrea boleta si ya existe)")
        print(cambios[-1])
    p.write_text(src, encoding="utf-8")

# ═══════════════════════════════════════════════════════════════
# PASO 4: Cascada de pago — saltar en modo editar
# ═══════════════════════════════════════════════════════════════
patron4 = re.compile(
    r"(\s+)if forma_pago and total_apostado > 0:\s*\n\s+monto_restante = total_apostado",
    re.MULTILINE,
)

if "not es_solo_editar" in src and "and forma_pago" in src:
    cambios.append("PASO 4: SKIP (ya existe)")
else:
    m = patron4.search(src)
    if not m:
        cambios.append("PASO 4: WARN (no matchea cascada de pago)")
        print(cambios[-1])
    else:
        indent = m.group(1)
        nuevo4 = f"{indent}# En modo editar NO se recobra (el dinero ya esta pagado)\n{indent}if (not es_solo_editar) and forma_pago and total_apostado > 0:\n{indent}    monto_restante = total_apostado"
        src = src[:m.start()] + nuevo4 + src[m.end():]
        cambios.append("PASO 4: OK (cascada saltada en editar)")
        print(cambios[-1])
    p.write_text(src, encoding="utf-8")

# ═══════════════════════════════════════════════════════════════
# PASO 5: Metadata de pago — preservar en modo editar
# ═══════════════════════════════════════════════════════════════
patron5 = re.compile(
    r"(\s+)if boleta:\s*\n\s+boleta\.metadata\['pago'\] = \{",
    re.MULTILINE,
)

if "Modo editar: preservar metadata" in src:
    cambios.append("PASO 5: SKIP (ya existe)")
else:
    m = patron5.search(src)
    if not m:
        cambios.append("PASO 5: WARN (no matchea metadata de pago)")
        print(cambios[-1])
    else:
        indent = m.group(1)
        cuerpo_indent = indent + "    "
        nuevo5 = f"""{indent}if boleta:
{cuerpo_indent}if es_solo_editar:
{cuerpo_indent}    # Modo editar: preservar metadata de pago original (no toca metadata['pago'])
{cuerpo_indent}    pass
{cuerpo_indent}else:
{cuerpo_indent}    boleta.metadata['pago'] = {{"""
        src = src[:m.start()] + nuevo5 + src[m.end():]
        cambios.append("PASO 5: OK (metadata preservada en editar)")
        print(cambios[-1])
    p.write_text(src, encoding="utf-8")

# ═══════════════════════════════════════════════════════════════
# REPORTE FINAL
# ═══════════════════════════════════════════════════════════════
print("\n═══ REPORTE ═══")
for c in cambios:
    print(f"  {c}")

# Verificar sintaxis
import ast
try:
    ast.parse(src)
    print("\nOK: sintaxis correcta")
except SyntaxError as e:
    print(f"\nERROR: sintaxis linea {e.lineno}: {e.msg}")
    print(f"   {e.text}")
    # Revertir si hay error
    p.write_text(original, encoding="utf-8")
    print("REVERTIDO al estado original")
    sys.exit(1)
