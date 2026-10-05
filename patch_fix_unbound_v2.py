from pathlib import Path
import ast

# ══════════════════════════════════════════════════════════════
# usuarios/views.py
# ══════════════════════════════════════════════════════════════
p1 = Path("/home/LottoBooM/usuarios/views.py")
src1 = p1.read_text(encoding="utf-8")

# Bloque malo EXACTO (con el bug que mete UnboundLocalError)
malo_1 = """    fd = (request.GET.get('fecha_desde') or '').strip()
    if fd: qs = qs.filter(creado_en__date__gte=fd)
    fh = (request.GET.get('fecha_hasta') or '').strip()

    # FIX_FILTRO_HOY_V1: fecha por defecto = hoy
    if not f_fecha_desde and not f_fecha_hasta:
        from django.utils import timezone as _tz_hoy
        f_fecha_desde = _tz_hoy.localdate().strftime('%Y-%m-%d')
        f_fecha_hasta = _tz_hoy.localdate().strftime('%Y-%m-%d')
    if fh: qs = qs.filter(creado_en__date__lte=fh)"""

bueno_1 = """    fd = (request.GET.get('fecha_desde') or '').strip()
    fh = (request.GET.get('fecha_hasta') or '').strip()
    # FIX_DEFAULT_HOY_OK_V1: default hoy si no hay filtros de fecha
    if not fd and not fh:
        from django.utils import timezone as _tz_hoy
        fd = _tz_hoy.localdate().strftime('%Y-%m-%d')
        fh = _tz_hoy.localdate().strftime('%Y-%m-%d')
    if fd: qs = qs.filter(creado_en__date__gte=fd)
    if fh: qs = qs.filter(creado_en__date__lte=fh)"""

if malo_1 in src1:
    src1 = src1.replace(malo_1, bueno_1, 1)
    try:
        ast.parse(src1)
        p1.write_text(src1, encoding="utf-8")
        print("OK: usuarios/views.py corregido")
    except SyntaxError as e:
        print(f"ERROR sintaxis usuarios: {e}")
elif bueno_1 in src1:
    print("SKIP: usuarios/views.py ya está correcto")
else:
    print("❌ ERROR: no encontré el bloque en usuarios/views.py")
    print("   → Pégame el sed -n '1388,1402p' para arreglar manual")

# ══════════════════════════════════════════════════════════════
# roles/views.py
# ══════════════════════════════════════════════════════════════
p2 = Path("/home/LottoBooM/roles/views.py")
src2 = p2.read_text(encoding="utf-8")

malo_2 = """    fd = (request.GET.get('fecha_desde') or '').strip()
    if fd:
        qs = qs.filter(creado_en__date__gte=fd)
    fh = (request.GET.get('fecha_hasta') or '').strip()

    # FIX_FILTRO_HOY_V1: fecha por defecto = hoy si no hay filtros
    if not f_fecha_desde and not f_fecha_hasta:
        from django.utils import timezone as _tz_hoy
        f_fecha_desde = _tz_hoy.localdate().strftime('%Y-%m-%d')
        f_fecha_hasta = _tz_hoy.localdate().strftime('%Y-%m-%d')
    if fh:
        qs = qs.filter(creado_en__date__lte=fh)"""

bueno_2 = """    fd = (request.GET.get('fecha_desde') or '').strip()
    fh = (request.GET.get('fecha_hasta') or '').strip()
    # FIX_DEFAULT_HOY_OK_V1: default hoy si no hay filtros de fecha
    if not fd and not fh:
        from django.utils import timezone as _tz_hoy
        fd = _tz_hoy.localdate().strftime('%Y-%m-%d')
        fh = _tz_hoy.localdate().strftime('%Y-%m-%d')
    if fd:
        qs = qs.filter(creado_en__date__gte=fd)
    if fh:
        qs = qs.filter(creado_en__date__lte=fh)"""

if malo_2 in src2:
    src2 = src2.replace(malo_2, bueno_2, 1)
    try:
        ast.parse(src2)
        p2.write_text(src2, encoding="utf-8")
        print("OK: roles/views.py corregido")
    except SyntaxError as e:
        print(f"ERROR sintaxis roles: {e}")
elif bueno_2 in src2:
    print("SKIP: roles/views.py ya está correcto")
else:
    print("❌ ERROR: no encontré el bloque en roles/views.py")
    print("   → Pégame el sed -n '4852,4868p' para arreglar manual")

print("\n✅ Script terminado")
