# -*- coding: utf-8 -*-
import os, sys
sys.path.insert(0, '/home/LottoBooM')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'LottoBooM.settings')
import django
django.setup()

from datetime import timedelta
from django.utils import timezone
from jugadas.models import Jugada
from resultados.models import Resultado
from resultados.reconciliacion import reconciliar_premio_jugada

hoy = timezone.localdate()
hace30 = hoy - timedelta(days=30)

q = Jugada.objects.filter(
    fecha_sorteo__gte=hace30,
    estado__in=['confirmada', 'pendiente'],
).select_related('sorteo', 'usuario', 'destinatario', 'forma_pago', 'forma_juego')

total = q.count()
print(f'Total a revisar: {total}')

creados = 0
errores = 0
for i, j in enumerate(q.iterator(), 1):
    r = Resultado.objects.filter(sorteo_id=j.sorteo_id, fecha=j.fecha_sorteo).first()
    if not r:
        continue
    try:
        p, created, err = reconciliar_premio_jugada(j, resultado=r)
        if created:
            creados += 1
            print(f'  OK Premio creado para #{j.id} ({j.numero} ${j.monto})')
        if err:
            errores += 1
    except Exception as e:
        errores += 1
        print(f'  ERROR #{j.id}: {e}')

print()
print(f'Premios creados: {creados}')
print(f'Errores: {errores}')
