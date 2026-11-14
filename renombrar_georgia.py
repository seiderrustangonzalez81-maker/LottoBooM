from sorteos.models import Sorteo

# Buscamos el sorteo por su ID (54)
sorteo = Sorteo.objects.filter(id=54).first()

if sorteo:
    nombre_anterior = sorteo.nombre
    # Cambiamos el nombre al de la hora de salida real
    sorteo.nombre = "Georgia 12:34 AM" 
    sorteo.save(update_fields=['nombre'])
    print(f"✅ Sorteo renombrado con éxito.")
    print(f"   Antes: '{nombre_anterior}'")
    print(f"   Ahora: '{sorteo.nombre}'")
else:
    print("❌ No se encontró el sorteo con ID 54.")
