from pathlib import Path

p = Path("/home/LottoBooM/jugadas/views.py")
src = p.read_text(encoding="utf-8")
original = src

if "Check de BOLETA DUPLICADA — ANTES" in src:
    print("SKIP: el check ya existe")
    raise SystemExit(0)

# ═══════════════════════════════════════════════════════════════
# Buscar la línea del with transaction.atomic() correcto
# ═══════════════════════════════════════════════════════════════
idx_es_solo = src.find("es_solo_editar = (es_edicion_boleta and modo_operacion == 'editar')")
if idx_es_solo == -1:
    print("ERROR: no encontre es_solo_editar")
    raise SystemExit(1)

idx_trans = src.find("with transaction.atomic():", idx_es_solo)
if idx_trans == -1:
    print("ERROR: no encontre with transaction.atomic()")
    raise SystemExit(1)

idx_line_start = src.rfind("\n", 0, idx_trans) + 1
print(f"INFO: insertando antes de la linea en posicion {idx_line_start}")

# ═══════════════════════════════════════════════════════════════
# Construir el bloque linea por linea (sin f-strings)
# ═══════════════════════════════════════════════════════════════
check_lines = [
    "        # \u2550\u2550\u2550\u2550 Check de BOLETA DUPLICADA \u2014 ANTES de crear cualquier jugada \u2550\u2550\u2550\u2550",
    "        if not es_edicion_boleta and not es_edicion_pura and forma_pago and cliente:",
    "            try:",
    "                _items_check = []",
    "                for _it in (items_normales + items_super):",
    "                    _sid = _it.get('sorteo_id')",
    "                    if not _sid:",
    "                        continue",
    "                    _items_check.append({",
    "                        'sorteo_id': int(_sid),",
    "                        'tipo': (_it.get('tipo') or '').strip().lower(),",
    "                        'numero': _it.get('numero') or '',",
    "                        'monto': _it.get('monto') or 0,",
    "                    })",
    "                if _items_check:",
    "                    _dups_pre = _boleta_duplicada(cliente.id, forma_pago.id, fecha_apuesta, _items_check)",
    "                    if _dups_pre:",
    "                        _refs = ', '.join([d.get('boleta_ref', '?') for d in _dups_pre])",
    "                        return JsonResponse({",
    "                            'success': False,",
    "                            'message': '\u26a0\ufe0f Ya existe una boleta identica para este cliente/sorteo/fecha/forma de pago (' + _refs + '). Modifica numeros, montos o forma de pago para continuar.',",
    "                            'advertencias': ['Duplicado con: ' + _refs],",
    "                        }, status=400)",
    "            except Exception as _e:",
    "                logger.warning('[dup check pre] ERROR: ' + str(_e))",
    "",
    "",
]
check_block = "\n".join(check_lines)

src = src[:idx_line_start] + check_block + src[idx_line_start:]
p.write_text(src, encoding="utf-8")
print("OK: check insertado")

# ═══════════════════════════════════════════════════════════════
# Verificar sintaxis
# ═══════════════════════════════════════════════════════════════
import ast
try:
    ast.parse(src)
    print("OK: sintaxis correcta")
except SyntaxError as e:
    print(f"ERROR: {e.lineno}: {e.msg}")
    print(f"   Linea: {e.text}")
    p.write_text(original, encoding="utf-8")
    print("REVERTIDO")
    raise SystemExit(1)

print(f"\nCheck insertado: {'OK' if 'Check de BOLETA DUPLICADA' in src else 'NO'}")
print(f"Llamada _boleta_duplicada: {src.count('_boleta_duplicada(')}")
