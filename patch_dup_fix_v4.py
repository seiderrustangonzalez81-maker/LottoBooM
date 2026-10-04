import re
from pathlib import Path

p = Path("/home/LottoBooM/jugadas/views.py")
src = p.read_text(encoding="utf-8")
original = src

# ═══════════════════════════════════════════════════════════════
# PASO 1: ELIMINAR el check actual (el que corre después de crear)
# ═══════════════════════════════════════════════════════════════
patron_viejo = re.compile(
    r"\n\s+# ═+\n\s+# Check de BOLETA DUPLICADA \(firma completa\).*?\n\s+monto_fondo_consumido = Decimal\('0\.00'\)",
    re.DOTALL,
)

if "Check de BOLETA DUPLICADA" in src:
    src_new, n = patron_viejo.subn("\n            monto_fondo_consumido = Decimal('0.00')", src, count=1)
    if n:
        src = src_new
        print("PASO 1: OK (check viejo eliminado)")
    else:
        print("PASO 1: WARN (no matcheo el patrón, revisar)")
else:
    print("PASO 1: SKIP (no habia check previo)")

# ═══════════════════════════════════════════════════════════════
# PASO 2: INSERTAR el check ANTES de crear jugadas
# Anchor: justo antes de "with transaction.atomic():"
# ═══════════════════════════════════════════════════════════════
viejo_anchor = """        with transaction.atomic():
            # Asegurar que 'boleta' este siempre definida
            boleta = None"""

nuevo_bloque = """        # ═══════════════════════════════════════════════════════════════
        # Check de BOLETA DUPLICADA — ANTES de crear cualquier jugada
        # ═══════════════════════════════════════════════════════════════
        if not es_edicion_boleta and not es_edicion_pura and forma_pago:
            try:
                _items_check = []
                # Combinar items_normales + items_super
                for _it in (items_normales + items_super):
                    _sid = _it.get('sorteo_id')
                    if not _sid:
                        continue
                    _items_check.append({
                        'sorteo_id': int(_sid),
                        'tipo': (_it.get('tipo') or '').strip().lower(),
                        'numero': _it.get('numero') or '',
                        'monto': _it.get('monto') or 0,
                    })
                if _items_check:
                    logger.info(f'[dup check pre] cliente={cliente.id} fp={forma_pago.id} fecha={fecha_apuesta} n_items={len(_items_check)}')
                    _dups_pre = _boleta_duplicada(cliente.id, forma_pago.id, fecha_apuesta, _items_check)
                    logger.info(f'[dup check pre] duplicados={_dups_pre}')
                    if _dups_pre:
                        _refs = ', '.join([d.get('boleta_ref', '?') for d in _dups_pre])
                        return JsonResponse({
                            'success': False,
                            'message': f'⚠️ Ya existe una boleta idéntica para este cliente/sorteo/fecha/forma de pago ({_refs}). Modifica números, montos o forma de pago para continuar.',
                            'advertencias': [f'Duplicado con: {_refs}'],
                        }, status=400)
            except Exception as _e:
                logger.warning(f'[dup check pre] ERROR: {_e}')

        with transaction.atomic():
            # Asegurar que 'boleta' este siempre definida
            boleta = None"""

if "Check de BOLETA DUPLICADA — ANTES" in src:
    print("PASO 2: SKIP (ya existe)")
elif viejo_anchor in src:
    src = src.replace(viejo_anchor, nuevo_bloque, 1)
    print("PASO 2: OK (check insertado antes de transaction)")
else:
    print("PASO 2: ERROR — no encontre el anchor 'with transaction.atomic()'")
    print("         Verificar manualmente")

p.write_text(src, encoding="utf-8")

# ═══════════════════════════════════════════════════════════════
# PASO 3: Verificar sintaxis
# ═══════════════════════════════════════════════════════════════
import ast
try:
    ast.parse(src)
    print("OK: sintaxis correcta")
except SyntaxError as e:
    print(f"ERROR: {e.lineno}: {e.msg}")
    p.write_text(original, encoding="utf-8")
    print("REVERTIDO")
    raise SystemExit(1)

print(f"\nCheck pre-transaction: {'✓' if 'Check de BOLETA DUPLICADA — ANTES' in src else '✗'}")
print(f"Check post-transaction: {'✓' if 'Check de BOLETA DUPLICADA (firma completa)' in src else '✗'}")

