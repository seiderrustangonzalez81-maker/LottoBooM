# -*- coding: utf-8 -*-
import os, sys
sys.path.insert(0, '/home/LottoBooM')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'LottoBooM.settings')
import django
django.setup()

from resultados.models import Premio, Resultado

print('=' * 78)
print('PREMIOS SOSPECHOSOS (jugada y resultado en distinto sorteo o fecha)')
print('=' * 78)

malos = 0
total = Premio.objects.count()
print(f'Total premios en BD: {total}\n')

for p in Premio.objects.select_related('jugada', 'jugada__sorteo', 'jugada__usuario').all():
    j = p.jugada
    meta = p.metadata or {}
    rid = meta.get('resultado_id')
    if not rid:
        continue
    r = Resultado.objects.filter(id=rid).first()
    if not r:
        continue
    if r.sorteo_id != j.sorteo_id or r.fecha != j.fecha_sorteo:
        malos += 1
        print(f'Premio #{p.id} | ${p.monto_premio} | cliente={j.usuario.username}')
        print(f'   jugada sorteo={j.sorteo.nombre} fecha={j.fecha_sorteo}')
        print(f'   resultado sorteo_id={r.sorteo_id} fecha={r.fecha}')

print()
print('=' * 78)
print(f'PREMIOS MAL ASIGNADOS: {malos}')
print('=' * 78)
