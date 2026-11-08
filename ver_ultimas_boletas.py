from jugadas.models import Boleta

print("=== ÚLTIMAS 5 BOLETAS EN EL SISTEMA ===")
boletas = Boleta.objects.all().order_by('-id')[:5]

for b in boletas:
    print(f"Boleta ID: {b.id} | Cliente: {b.usuario.username} | Fecha: {b.creado_en.strftime('%Y-%m-%d')} | Jugado: ${b.monto_total} | Premio: ${b.premios_total} | Estado: {b.estado}")
