from pathlib import Path
import ast

p = Path("/home/LottoBooM/usuarios/views.py")
src = p.read_text(encoding="utf-8")

# Bloque mal insertado por el patch anterior
viejo_malo = """    # FIX_FILTRO_HOY_V1: fecha por defecto = hoy
    if not f_fecha_desde and not f_fecha_hasta:
        from django.utils import timezone as _tz_hoy
        f_fecha_desde = _tz_hoy.localdate().strftime('%Y-%m-%d')
        f_fecha_hasta = _tz_hoy.localdate().strftime('%Y-%m-%d')
"""

if viejo_malo not in src:
    print("WARN: no encontré el bloque mal insertado en mis_movimientos")
    print("       puede ser distinto, revisa manualmente")
else:
    # 1. Quitar el bloque mal puesto
    src = src.replace(viejo_malo, "", 1)

    # 2. Insertar DESPUÉS de que se lean los valores del request
    #    Buscar el patrón donde termina la lectura (probablemente fecha_hasta o similar)
    idx = src.find("def mis_movimientos(")
    if idx < 0:
        print("ERROR: no encontré mis_movimientos")
        raise SystemExit(1)

    end_func = src.find("\ndef ", idx + 10)
    cuerpo = src[idx:end_func if end_func > 0 else len(src)]

    lineas = cuerpo.split("\n")
    # Buscar la línea donde se lee f_fecha_hasta desde request.GET
    idx_insert = None
    for i, ln in enumerate(lineas):
        if "f_fecha_hasta" in ln and "request.GET" in ln:
            idx_insert = i
            break
        if "f_fecha_desde" in ln and "request.GET" in ln:
            idx_insert = i  # por si no hay fecha_hasta

    if idx_insert is None:
        print("ERROR: no encontré dónde leer f_fecha_hasta del request")
        print("       pégame la función completa y lo arreglo")
        raise SystemExit(1)

    # Insertar el bloque de defaults DESPUÉS de las lecturas
    bloque_ok = [
        "",
        "    # FIX_FILTRO_HOY_V1: fecha por defecto = hoy",
        "    if not f_fecha_desde and not f_fecha_hasta:",
        "        from django.utils import timezone as _tz_hoy",
        "        f_fecha_desde = _tz_hoy.localdate().strftime('%Y-%m-%d')",
        "        f_fecha_hasta = _tz_hoy.localdate().strftime('%Y-%m-%d')",
    ]
    lineas[idx_insert+1:idx_insert+1] = bloque_ok
    nuevo_cuerpo = "\n".join(lineas)
    src = src[:idx] + nuevo_cuerpo + src[end_func if end_func > 0 else len(src):]

try:
    ast.parse(src)
    p.write_text(src, encoding="utf-8")
    print("OK: usuarios/views.py corregido")
except SyntaxError as e:
    print(f"ERROR sintaxis: {e}")
    raise SystemExit(1)
