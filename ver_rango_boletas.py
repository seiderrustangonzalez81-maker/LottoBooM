from jugadas.models import Boleta
from django.db.models import Min, Max

print("=== RANGO DE FECHAS DE LAS BOLETAS RECUPERADAS ===")

# Buscar las fechas extremas (la más antigua y la más reciente)
fechas_creacion = Boleta.objects.aggregate(
    primera=Min('creado_en'),
    ultima=Max('creado_en')
)

fechas_sorteo = Boleta.objects.aggregate(
    primer_sorteo=Min('fecha_sorteo'),
    ultimo_sorteo=Max('fecha_sorteo')
)

print(f"📅 Fecha de creación de la primera boleta: {fechas_creacion['primera']}")
print(f"📅 Fecha de creación de la última boleta:  {fechas_creacion['ultima']}")
print("--------------------------------------------------")
print(f"🎰 Fecha del primer sorteo jugado: {fechas_sorteo['primer_sorteo']}")
print(f"🎰 Fecha del último sorteo jugado: {fechas_sorteo['ultimo_sorteo']}")

# Para estar 100% seguros, vamos a contar cuántas boletas hay por mes
print("\n=== CANTIDAD DE BOLETAS POR MES ===")
from django.db.models.functions import TruncMonth
por_mes = Boleta.objects.annotate(mes=TruncMonth('creado_en')).values('mes').annotate(total=__import__('django.db.models', fromlist=['Count']).Count('id')).order_by('mes')

for p in por_mes:
    if p['mes']:
        print(f"Mes: {p['mes'].strftime('%Y-%m')} | Boletas: {p['total']}")
