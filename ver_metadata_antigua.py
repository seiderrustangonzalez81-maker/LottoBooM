from jugadas.models import Boleta
import json

# Buscar 3 boletas ANTIGUAS que sí tengan la clave 'pago' en su metadata
boletas = Boleta.objects.filter(metadata__has_key='pago').order_by('creado_en')[:3]

if not boletas.exists():
    print("❌ No se encontraron boletas con metadata de pago.")
else:
    for b in boletas:
        print(f"=== BOLETA ID: {b.id} | Cliente: {b.usuario.username} | Fecha: {b.creado_en.strftime('%Y-%m-%d')} ===")
        print(f"Monto Jugado: ${b.monto_total}")
        print("Metadata (Contenido interno):")
        print(json.dumps(b.metadata, indent=4, ensure_ascii=False))
        print("-" * 50)
