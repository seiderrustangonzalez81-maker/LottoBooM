#!/bin/bash
set -euo pipefail
cd /home/LottoBooM
python3 manage.py shell << 'PYEOF'
from django.contrib.auth.models import User
from roles.models import Rol, Fondo
from django.db.models import Count, Q

print("═══ USUARIOS CON MÚLTIPLES ROLES ═══")
multi = User.objects.filter(is_active=True).annotate(
    n=Count('roles', filter=Q(roles__activo=True))
).filter(n__gt=1)
for u in multi[:20]:
    tipos = list(Rol.objects.filter(usuario=u, activo=True).values_list('tipo', flat=True))
    print(f"  {u.username:<25} roles={tipos}")
print(f"\nTotal multi-rol: {multi.count()}")

print("\n═══ COMERCIALES (rol comercial activo) ═══")
com = User.objects.filter(roles__tipo='comercial', roles__activo=True, is_active=True).distinct()
for u in com[:15]:
    tipos = list(Rol.objects.filter(usuario=u, activo=True).values_list('tipo', flat=True))
    print(f"  {u.username:<25} roles={tipos}")
print(f"\nTotal comerciales: {com.count()}")

print("\n═══ USERS EN 'clientes_sel' ACTUAL (superadmin) ═══")
con_fondo = User.objects.filter(fondos__isnull=False, is_active=True).distinct()
for u in con_fondo[:20]:
    tipos = list(Rol.objects.filter(usuario=u, activo=True).values_list('tipo', flat=True))
    marca = " ⚠️ ES COMERCIAL" if 'comercial' in tipos else ""
    print(f"  {u.username:<25} roles={tipos}{marca}")
print(f"\nTotal en clientes_sel: {con_fondo.count()}")

print("\n═══ RESUMEN ═══")
print(f"  Clientes (rol): {Rol.objects.filter(activo=True, tipo='cliente').count()}")
print(f"  Comerciales: {com.count()}")
print(f"  Users con Fondo: {con_fondo.count()}")
PYEOF
