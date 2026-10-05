from pathlib import Path
import ast

# ══════════════════════════════════════════════════════════════
# usuarios/views.py → mis_movimientos (usa fd, fh)
# ══════════════════════════════════════════════════════════════
p1 = Path("/home/LottoBooM/usuarios/views.py")
src1 = p1.read_text(encoding="utf-8")

if "FIX_DEFAULT_HOY_OK_V1" in src1:
    print("SKIP: usuarios/views.py ya aplicado")
else:
    viejo = """    fd = (request.GET.get('fecha_desde') or '').strip()
    if fd: qs = qs.filter(creado_en__date__gte=fd)
    fh = (request.GET.get('fecha_hasta') or '').strip()"""

    nuevo = """    fd = (request.GET.get('fecha_desde') or '').strip()
    fh = (request.GET.get('fecha_hasta') or '').strip()
    # FIX_DEFAULT_HOY_OK_V1: default hoy si no hay filtros de fecha
    if not fd and not fh:
        from django.utils import timezone as _tz_hoy
        fd = _tz_hoy.localdate().strftime('%Y-%m-%d')
        fh = _tz_hoy.localdate().strftime('%Y-%m-%d')
    if fd: qs = qs.filter(creado_en__date__gte=fd)"""

    if viejo not in src1:
        print("WARN 1: no encontré el patrón exacto en usuarios/views.py")
        print("        ¿ya revirtió con git checkout?")
    else:
        src1 = src1.replace(viejo, nuevo, 1)
        try:
            ast.parse(src1)
            p1.write_text(src1, encoding="utf-8")
            print("OK: usuarios/views.py actualizado")
        except SyntaxError as e:
            print(f"ERROR sintaxis usuarios: {e}")

# ══════════════════════════════════════════════════════════════
# roles/views.py → historial_movimientos (usa fd, fh)
# ══════════════════════════════════════════════════════════════
p2 = Path("/home/LottoBooM/roles/views.py")
src2 = p2.read_text(encoding="utf-8")

if "FIX_DEFAULT_HOY_OK_V1" in src2:
    print("SKIP: roles/views.py ya aplicado")
else:
    viejo = """    fd = (request.GET.get('fecha_desde') or '').strip()
    if fd:
        qs = qs.filter(creado_en__date__gte=fd)
    fh = (request.GET.get('fecha_hasta') or '').strip()"""

    nuevo = """    fd = (request.GET.get('fecha_desde') or '').strip()
    fh = (request.GET.get('fecha_hasta') or '').strip()
    # FIX_DEFAULT_HOY_OK_V1: default hoy si no hay filtros de fecha
    if not fd and not fh:
        from django.utils import timezone as _tz_hoy
        fd = _tz_hoy.localdate().strftime('%Y-%m-%d')
        fh = _tz_hoy.localdate().strftime('%Y-%m-%d')
    if fd:
        qs = qs.filter(creado_en__date__gte=fd)"""

    if viejo not in src2:
        print("WARN 2: no encontré el patrón exacto en roles/views.py")
        print("        ¿ya revirtió con git checkout?")
    else:
        src2 = src2.replace(viejo, nuevo, 1)
        try:
            ast.parse(src2)
            p2.write_text(src2, encoding="utf-8")
            print("OK: roles/views.py actualizado")
        except SyntaxError as e:
            print(f"ERROR sintaxis roles: {e}")

print("\n✅ Script completado")
