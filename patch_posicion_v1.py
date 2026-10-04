from pathlib import Path

p = Path("/home/LottoBooM/resultados/views.py")
src = p.read_text(encoding="utf-8")

if "FIX_POSICION_V1" in src:
    print("SKIP: ya aplicado")
    raise SystemExit(0)

viejo = """      # ─── POSICIÓN ───
      if forma in ('posicion', 'posiciones'):
          if numero in posicion_list:
              return True, multiplicador
          return False, 0"""

# El archivo tiene indentación de 4 espacios (function body)
viejo = """    # ─── POSICIÓN ───
    if forma in ('posicion', 'posiciones'):
        if numero in posicion_list:
            return True, multiplicador
        return False, 0"""

nuevo = """    # ─── POSICIÓN (FIX_POSICION_V1: respeta la posición apostada) ───
    if forma in ('posicion', 'posiciones'):
        meta = jugada.metadata or {}
        orig = meta.get('original') or {}
        pos_apostada = orig.get('posicion') if isinstance(orig, dict) else None
        if pos_apostada is None:
            pos_apostada = meta.get('posicion')

        if pos_apostada is not None:
            try:
                idx = int(pos_apostada) - 1  # 1-based -> 0-based
            except (ValueError, TypeError):
                logger.warning(f'[FIX_POSICION_V1] jugada #{jugada.id} posicion invalida: {pos_apostada!r}')
                return False, 0
            if idx < 0 or idx >= len(posicion_list):
                return False, 0
            if posicion_list[idx] == numero:
                return True, multiplicador
            return False, 0

        # Fallback legacy (sin metadata de posicion)
        logger.warning(f'[FIX_POSICION_V1] jugada #{jugada.id} sin metadata de posicion — fallback legacy')
        if numero in posicion_list:
            return True, multiplicador
        return False, 0"""

if viejo not in src:
    print("ERROR: no encontre el bloque de POSICIÓN exacto")
    print("  Busca manualmente las lineas ~388-392 en resultados/views.py")
    raise SystemExit(1)

src = src.replace(viejo, nuevo, 1)

import ast
try:
    ast.parse(src)
except SyntaxError as e:
    print(f"ERROR sintaxis: {e}")
    raise SystemExit(1)

p.write_text(src, encoding="utf-8")
print("OK: FIX_POSICION_V1 aplicado")
print("OK: sintaxis correcta")
