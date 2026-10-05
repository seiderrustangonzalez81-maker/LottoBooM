from pathlib import Path
import ast

# ══════════════════════════════════════════════════════════════
# 1. roles/views.py :: historial_movimientos
# ══════════════════════════════════════════════════════════════
p1 = Path("/home/LottoBooM/roles/views.py")
src1 = p1.read_text(encoding="utf-8")

if "FIX_FILTRO_HOY_V1" in src1:
    print("SKIP: roles/views.py ya aplicado")
else:
    # Buscar la función y agregar default después de capturar los params
    # Buscamos el patrón: def historial_movimientos(request):
    idx = src1.find("def historial_movimientos(request")
    if idx < 0:
        print("WARN: no encontré historial_movimientos en roles/views.py")
    else:
        # Buscar la línea después de la firma, donde se leen los parámetros
        # Insertar bloque justo después de la línea que contiene "fecha_hasta"
        end_func = src1.find("\ndef ", idx + 10)
        cuerpo = src1[idx:end_func if end_func > 0 else len(src1)]

        # Buscar el patrón request.GET.get('fecha_desde')
        if "'fecha_desde'" in cuerpo or '"fecha_desde"' in cuerpo:
            # Insertar después de la línea con fecha_hasta
            lineas = cuerpo.split("\n")
            for i, ln in enumerate(lineas):
                if "fecha_hasta" in ln and "request.GET" in ln:
                    # Insertar bloque de default después de esta línea
                    bloque = [
                        "",
                        "    # FIX_FILTRO_HOY_V1: fecha por defecto = hoy si no hay filtros",
                        "    if not f_fecha_desde and not f_fecha_hasta:",
                        "        from django.utils import timezone as _tz_hoy",
                        "        f_fecha_desde = _tz_hoy.localdate().strftime('%Y-%m-%d')",
                        "        f_fecha_hasta = _tz_hoy.localdate().strftime('%Y-%m-%d')",
                    ]
                    lineas[i+1:i+1] = bloque
                    break
            nuevo_cuerpo = "\n".join(lineas)
            src1 = src1[:idx] + nuevo_cuerpo + src1[end_func if end_func > 0 else len(src1):]
            try:
                ast.parse(src1)
                p1.write_text(src1, encoding="utf-8")
                print("OK: roles/views.py actualizado")
            except SyntaxError as e:
                print(f"ERROR sintaxis roles: {e}")

# ══════════════════════════════════════════════════════════════
# 2. resultados/views.py :: api_resumen_filtrado
# ══════════════════════════════════════════════════════════════
p2 = Path("/home/LottoBooM/resultados/views.py")
src2 = p2.read_text(encoding="utf-8")

if "FIX_FILTRO_HOY_V1" in src2:
    print("SKIP: resultados/views.py ya aplicado")
else:
    viejo = """    # Si no hay filtros -> solo hoy
    if not (fecha_desde_str or fecha_hasta_str):
        fecha_actual = timezone.localtime(timezone.now()).date()
        resultados = resultados.filter(fecha=fecha_actual)"""
    if viejo in src2:
        print("SKIP: api_resumen_filtrado ya tiene default hoy")
    else:
        print("WARN: api_resumen_filtrado necesita revisión manual")

# ══════════════════════════════════════════════════════════════
# 3. usuarios/views.py :: mis_movimientos
# ══════════════════════════════════════════════════════════════
p3 = Path("/home/LottoBooM/usuarios/views.py")
src3 = p3.read_text(encoding="utf-8")

if "FIX_FILTRO_HOY_V1" in src3:
    print("SKIP: usuarios/views.py ya aplicado")
else:
    idx = src3.find("def mis_movimientos(request")
    if idx < 0:
        print("WARN: no encontré mis_movimientos en usuarios/views.py")
    else:
        end_func = src3.find("\ndef ", idx + 10)
        cuerpo = src3[idx:end_func if end_func > 0 else len(src3)]

        lineas = cuerpo.split("\n")
        inserted = False
        for i, ln in enumerate(lineas):
            if ("fecha_hasta" in ln and "request.GET" in ln) or ("fecha_hasta_str" in ln and "GET" in ln):
                bloque = [
                    "",
                    "    # FIX_FILTRO_HOY_V1: fecha por defecto = hoy",
                    "    if not f_fecha_desde and not f_fecha_hasta:",
                    "        from django.utils import timezone as _tz_hoy",
                    "        f_fecha_desde = _tz_hoy.localdate().strftime('%Y-%m-%d')",
                    "        f_fecha_hasta = _tz_hoy.localdate().strftime('%Y-%m-%d')",
                ]
                lineas[i+1:i+1] = bloque
                inserted = True
                break

        if not inserted:
            print("WARN: no encontré el punto de inserción en mis_movimientos")
        else:
            nuevo_cuerpo = "\n".join(lineas)
            src3 = src3[:idx] + nuevo_cuerpo + src3[end_func if end_func > 0 else len(src3):]
            try:
                ast.parse(src3)
                p3.write_text(src3, encoding="utf-8")
                print("OK: usuarios/views.py actualizado")
            except SyntaxError as e:
                print(f"ERROR sintaxis usuarios: {e}")

print("\nNOTA: si algún WARN aparece, pégame la función específica")
print("y lo arreglo manualmente en el siguiente mensaje.")
