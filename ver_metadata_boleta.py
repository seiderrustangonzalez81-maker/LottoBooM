from jugadas.models import Boleta
import json

# Buscar 3 boletas que tengan metadata
boletas = Boleta.objects.exclude(metadata__isnull=True).exclude(metadata={})[:3]

for b in boletas:
    print(f"=== BOLETA ID: {b.id} | Cliente: {b.usuario.username} | Fecha: {b.creado_en.strftime('%Y-%m-%d')} ===")
    print(f"Monto Jugado: ${b.monto_total}")
    print("Metadata (Contenido interno):")
    print(json.dumps(b.metadata, indent=4, ensure_ascii=False))
    print("-" * 50)
