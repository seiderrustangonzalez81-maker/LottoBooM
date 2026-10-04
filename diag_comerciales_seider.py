# -*- coding: utf-8 -*-
import os, sys
sys.path.insert(0, '/home/LottoBooM')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'LottoBooM.settings')
import django
django.setup()

from django.contrib.auth.models import User
from roles.models import Rol, Subordinacion

print('=' * 78)
print('DIAGNÓSTICO: Comerciales de Seider')
print('=' * 78)

seider = User.objects.filter(username='Seider').first()
if not seider:
    print('❌ No existe Seider')
    raise SystemExit(1)

print(f'Seider id={seider.id} username={seider.username}')
print()

# 1. Comerciales por Rol
print('1) Usuarios con rol COMERCIAL en el sistema:')
com_ids = list(Rol.objects.filter(tipo='comercial', activo=True).values_list('usuario_id', flat=True))
for u in User.objects.filter(id__in=com_ids, is_active=True).order_by('username'):
    print(f'   - {u.username} (id={u.id})')
print(f'   Total: {len(com_ids)}')
print()

# 2. Subordinados directos de Seider (lo que usa la vista)
print('2) Subordinados directos de Seider (Subordinacion jefe=Seider):')
subs = Subordinacion.objects.filter(jefe=seider, activo=True).select_related('subordinado')
for s in subs:
    u = s.subordinado
    rol = u.roles.filter(activo=True).first() if u else None
    print(f'   - {u.username} (id={u.id}) rol={rol.tipo if rol else "?"}')
print(f'   Total: {subs.count()}')
print()

# 3. Lo que la vista cuadre filtra
print('3) Lo que la vista cuadre_diario_view carga como comerciales:')
from roles.models import Subordinacion as Sub
com_ids_vista = Sub.objects.filter(jefe=seider, activo=True).values_list('subordinado_id', flat=True)
comerciales_vista = User.objects.filter(id__in=com_ids_vista, is_active=True)
for u in comerciales_vista:
    rol = u.roles.filter(activo=True).first()
    print(f'   - {u.username} rol={rol.tipo if rol else "sin rol"}')
print(f'   Total mostrados: {comerciales_vista.count()}')
print()

# 4. Los que DEBERÍA ver (comerciales + comerciales vía Fondo)
print('4) Comerciales vinculados por Fondo (asignado_por=Seider):')
from roles.models import Fondo
fondo_users = Fondo.objects.filter(asignado_por=seider, activo=True).values_list('usuario_id', flat=True).distinct()
for u in User.objects.filter(id__in=fondo_users, is_active=True):
    rol = u.roles.filter(activo=True).first()
    if rol and rol.tipo == 'comercial':
        print(f'   - {u.username} (rol={rol.tipo})')
print()

# 5. Comparación
print('5) RESUMEN:')
print(f'   Comerciales por rol en BD: {len(com_ids)}')
print(f'   Subordinados directos de Seider: {subs.count()}')
print(f'   Muestra la vista actual: {comerciales_vista.count()}')
