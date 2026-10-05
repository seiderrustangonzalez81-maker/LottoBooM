from pathlib import Path
import ast

# ══════════════════════════════════════════════════════════════
# 1. publico/views.py → _calcular_estadisticas
# ══════════════════════════════════════════════════════════════
p1 = Path("/home/LottoBooM/publico/views.py")
src1 = p1.read_text(encoding="utf-8")

if "FIX_TZ_CONTADORES_V1" in src1:
    print("SKIP: publico/views.py ya aplicado")
else:
    viejo = """    hoy = timezone.now().date()
    ahora = timezone.now()

    # ── Usuarios ──"""

    nuevo = """    # FIX_TZ_CONTADORES_V1: usar fecha local (Cuba), no UTC
    hoy = timezone.localdate()
    ahora = timezone.now()

    # ── Usuarios ──"""

    if viejo not in src1:
        print("WARN 1: no encontré el patrón exacto en publico/views.py")
    else:
        src1 = src1.replace(viejo, nuevo, 1)
        try:
            ast.parse(src1)
            p1.write_text(src1, encoding="utf-8")
            print("OK: publico/views.py actualizado")
        except SyntaxError as e:
            print(f"ERROR sintaxis: {e}")

# ══════════════════════════════════════════════════════════════
# 2. publico/context_processors.py → contadores
# ══════════════════════════════════════════════════════════════
p2 = Path("/home/LottoBooM/publico/context_processors.py")
src2 = p2.read_text(encoding="utf-8")

if "FIX_TZ_CONTADORES_V1" in src2:
    print("SKIP: context_processors.py ya aplicado")
else:
    viejo = """    hoy = timezone.now().date()
    cache_key = f'contadores_{hoy}'"""

    nuevo = """    # FIX_TZ_CONTADORES_V1: fecha local (Cuba)
    hoy = timezone.localdate()
    cache_key = f'contadores_{hoy}'"""

    if viejo not in src2:
        print("WARN 2: no encontré el patrón exacto en context_processors.py")
    else:
        src2 = src2.replace(viejo, nuevo, 1)
        try:
            ast.parse(src2)
            p2.write_text(src2, encoding="utf-8")
            print("OK: context_processors.py actualizado")
        except SyntaxError as e:
            print(f"ERROR sintaxis: {e}")

print("\n✅ Listo")
