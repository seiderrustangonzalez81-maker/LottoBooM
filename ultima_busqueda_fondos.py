from roles.models import CuadreDiario, UserActivity, SuscripcionBanco
from jugadas.models import Boleta
import json

print("=== ÚLTIMA BÚSQUEDA DE SALDOS FINALES ===")

print(f"1. Cuadres Diarios (Cierres de caja): {CuadreDiario.objects.count()} registros.")
if CuadreDiario.objects.count() > 0:
    for c in CuadreDiario.objects.all()[:3]:
        print(f"   - Cuadre de {c.usuario.username} el {c.fecha}: Fondo Final {c.fondo_final}")

print(f"2. Actividad de Usuario: {UserActivity.objects.count()} registros.")
print(f"3. Suscripciones: {SuscripcionBanco.objects.count()} registros.")

print("\n=== REVISANDO METADATA DE BOLETAS ANTIGUAS (Buscando saldos) ===")
# A veces los sistemas guardan el saldo dentro de la metadata de la boleta
# Vamos a buscar si alguna boleta tiene las palabras 'saldo' o 'fondo_final'
boletas_con_saldo = 0
for b in Boleta.objects.exclude(metadata__isnull=True):
    metadata_str = str(b.metadata).lower()
    if 'saldo' in metadata_str or 'restante' in metadata_str:
        print(f"   - ¡Posible rastro en Boleta ID {b.id} ({b.usuario.username})!")
        print(f"     Metadata: {json.dumps(b.metadata)}")
        boletas_con_saldo += 1
        if boletas_con_saldo >= 3: # Solo mostrar 3 para no saturar
            break

if boletas_con_saldo == 0:
    print("   ❌ No se encontró ninguna boleta que guarde el saldo restante del cliente.")
