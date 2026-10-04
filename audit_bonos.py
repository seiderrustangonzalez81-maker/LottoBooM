# -*- coding: utf-8 -*-
"""Auditoría rápida: sistema de bonos y referidos actual."""
import os, sys
sys.path.insert(0, '/home/LottoBooM')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'LottoBooM.settings')
import django
django.setup()

from django.contrib.auth.models import User
from roles.models import Bono
from decimal import Decimal

print('=' * 70)
print('BONOS — estado actual')
print('=' * 70)
print(f'Total: {Bono.objects.count()}')
print(f'Activos: {Bono.objects.filter(estado="activo").count()}')
print(f'Por tipo:')
from django.db.models import Count
for r in Bono.objects.values('tipo').annotate(n=Count('id')):
    print(f'  {r["tipo"]}: {r["n"]}')
print()
print('Últimos 5 bonos:')
for b in Bono.objects.order_by('-id')[:5]:
    print(f'  #{b.id} | {b.usuario.username} | tipo={b.tipo} | saldo=${b.saldo_restante} | asignado_por={b.asignado_por.username if b.asignado_por else "?"} | venc={b.fecha_vencimiento}')
print()

# Buscar sistema de referidos
print('=' * 70)
print('BUSCAR SISTEMA DE REFERIDOS')
print('=' * 70)
from django.apps import apps
for model in apps.get_models():
    n = model.__name__.lower()
    if 'refer' in n or 'invit' in n or 'enlace' in n:
        print(f'  {model._meta.app_label}.{model.__name__}')
        for f in model._meta.get_fields():
            if hasattr(f, 'name'):
                print(f'     - {f.name}')

# Buscar en User si hay campo referido_por
from django.db.models import Q
u = User.objects.filter(is_active=True).first()
if u:
    campos_user = [f.name for f in u._meta.get_fields() if hasattr(f, 'name')]
    referidos_campos = [c for c in campos_user if 'refer' in c.lower() or 'invit' in c.lower()]
    print(f'\nCampos User con "refer"/"invit": {referidos_campos}')

# Buscar en Bono tipos referidos
print()
print('Bonos con usuario_referido o usuario_referente no nulos:')
n_ref = Bono.objects.filter(
    Q(usuario_referido__isnull=False) | Q(usuario_referente__isnull=False)
).count()
print(f'  Total: {n_ref}')
