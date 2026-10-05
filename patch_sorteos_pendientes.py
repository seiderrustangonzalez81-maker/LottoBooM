from pathlib import Path
import ast

p = Path("/home/LottoBooM/publico/views.py")
src = p.read_text(encoding="utf-8")

if "FIX_SORTEOS_PENDIENTES_V1" in src:
    print("SKIP: ya aplicado")
    raise SystemExit(0)

viejo = """    # ── Sorteos ──
    try:
        total_sorteos = Sorteo.objects.filter(activo=True).count()
        # Sorteos pendientes = activos cuya hora de salida aún no pasó hoy
        # (ajustar el campo según tu modelo real)
        sorteos_pendientes = Sorteo.objects.filter(
            activo=True,
            hora_salida__gte=ahora
        ).count()
    except Exception:
        total_sorteos = 0
        sorteos_pendientes = 0"""

nuevo = """    # ── Sorteos ──
    # FIX_SORTEOS_PENDIENTES_V1: usar get_hora_salida (respeta horarios JSON)
    try:
        total_sorteos = Sorteo.objects.filter(activo=True).count()
        from sorteos.utils import get_hora_salida
        hora_actual = timezone.localtime(ahora).time()
        sorteos_pendientes = 0
        for s in Sorteo.objects.filter(activo=True):
            try:
                hs = get_hora_salida(s, hoy)
                if hs and hs > hora_actual:
                    sorteos_pendientes += 1
            except Exception:
                pass
    except Exception:
        total_sorteos = 0
        sorteos_pendientes = 0"""

if viejo not in src:
    print("ERROR: no encontré el bloque de sorteos")
    raise SystemExit(1)

src = src.replace(viejo, nuevo, 1)

try:
    ast.parse(src)
except SyntaxError as e:
    print(f"ERROR sintaxis: {e}")
    raise SystemExit(1)

p.write_text(src, encoding="utf-8")
print("OK: FIX_SORTEOS_PENDIENTES_V1 aplicado")
