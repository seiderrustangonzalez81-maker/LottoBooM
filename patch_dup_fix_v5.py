import re
from pathlib import Path

p = Path("/home/LottoBooM/jugadas/views.py")
src = p.read_text(encoding="utf-8")
original = src

# ═══════════════════════════════════════════════════════════════
# Verificar estado previo
# ═══════════════════════════════════════════════════════════════
if "Check de BOLETA DUPLICADA — ANTES" in src:
    print("SKIP: el check nuevo ya existe")
    raise SystemExit(0)

# ═══════════════════════════════════════════════════════════════
# Anchor: encontrar el `with transaction.atomic():` específico
# que está después de la definición de es_solo_editar, es_edicion_boleta, es_edicion_pura
# ═══════════════════════════════════════════════════════════════

# Buscar desde "es_solo_editar = (es_edicion_boleta" hacia adelante
idx_es_solo = src.find("es_solo_editar = (es_edicion_boleta and modo_operacion == 'editar')")
if idx_es_solo == -1:
    print("ERROR: no encontre 'es_solo_editar = ...'")
    raise SystemExit(1)

# A partir de ahí, buscar el siguiente "with transaction.atomic():"
idx_trans = src.find("with transaction.atomic():", idx_es_solo)
if idx_trans == -1:
    print("ERROR: no encontre 'with transaction.atomic():' después de es_solo_editar")
    raise SystemExit(1)

# Retroceder al inicio de la línea
idx_line_start = src.rfind("\n", 0, idx_trans) + 1
indent = src[idx_line_start:idx_trans]

print(f"INFO: encontrado 'with transaction.atomic():' en posición {idx_trans}, indentación '{indent}'")

# ═══════════════════════════════════════════════════════════════
# Construir el bloque del check con la misma indentación
# ═══════════════════════════════════════════════════════════════
# indentación base (8 espacios) y sub (12 espacios)
ind_base = indent
ind_sub = indent + "    "
ind_sub2 = indent + "        "
ind_sub3 = indent + "            "

check_block = f'''{ind_base}# ═══════════════════════════════════════════════════════════════
{ind_base}# Check de BOLETA DUPLICADA — ANTES de crear cualquier jugada
{ind_base}# Compara la firma completa (cliente + sorteo + fecha + FP + números + montos)
{ind_base}# ═══════════════════════════════════════════════════════════════
{ind_base}if not es_edicion_boleta and not es_edicion_pura and forma_pago and cliente:
{ind_sub}try:
{ind_sub2}_items_check = []
{ind_sub2}for _it in (items_normales + items_super):
{ind_sub3}_sid = _it.get('sorteo_id')
{ind_sub3}if not _sid:
{ind_sub3}    continue
{ind_sub3}_items_check.append({{
{ind_sub3}    'sorteo_id': int(_sid),
{ind_sub3}    'tipo': (_it.get('tipo') or '').strip().lower(),
{ind_sub3}    'numero': _it.get('numero') or '',
{ind_sub3}    'monto': _it.get('monto') or 0,
{ind_sub3}}})
{ind_sub2}if _items_check:
{ind_sub3}logger.info(f'[dup check pre] cliente={{cliente.id}} fp={{forma_pago.id}} fecha={{fecha_apuesta}} n_items={{len(_items_check)}}')
{ind_sub3}_dups_pre = _boleta_duplicada(cliente.id, forma_pago.id, fecha_apuesta, _items_check)
{ind_sub3}logger.info(f'[dup check pre] duplicados={{_dups_pre}}')
{ind_sub3}if _dups_pre:
{ind_sub3}    _refs = ', '.join([d.get('boleta_ref', '?') for d in _dups_pre])
{ind_sub3}    return JsonResponse({{
{ind_sub3}        'success': False,
{ind_sub3}        'message': '⚠️ Ya existe una boleta idéntica para este cliente/sorteo/fecha/forma de pago (' + _refs + '). Modifica números, montos o forma de pago para continuar.',
{ind_sub3}        'advertencias': ['Duplicado con: ' + _refs],
{ind_sub3}    }}, status=400)
{ind_sub}except Exception as _e:
{ind_sub2}logger.warning(f'[dup check pre] ERROR: {{_e}}')

{ind_base}'''

# Insertar ANTES del `with transaction.atomic():`
src = src[:idx_line_start] + check_block + src[idx_line_start:]
p.write_text(src, encoding="utf-8")
print("OK: check insertado antes de 'with transaction.atomic():'")

# ═══════════════════════════════════════════════════════════════
# Verificar sintaxis
# ═══════════════════════════════════════════════════════════════
import ast
try:
    ast.parse(src)
    print("OK: sintaxis correcta")
except SyntaxError as e:
    print(f"ERROR: {e.lineno}: {e.msg}")
    print(f"   Contexto: {e.text}")
    p.write_text(original, encoding="utf-8")
    print("REVERTIDO")
    raise SystemExit(1)

# Verificar
print(f"\nCheck insertado: {'✓' if 'Check de BOLETA DUPLICADA — ANTES' in src else '✗'}")
print(f"Llamada a _boleta_duplicada: {src.count('_boleta_duplicada(')}")
