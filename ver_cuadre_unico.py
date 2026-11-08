from roles.models import CuadreDiario
import json

# Obtener el único cuadre que existe
cuadres = CuadreDiario.objects.all()

for c in cuadres:
    print(f"=== CUADRE DIARIO ENCONTRADO ===")
    print(f"Usuario: {c.usuario.username}")
    print(f"Fecha: {c.fecha}")
    
    # Vamos a imprimir todos los campos que tenga este objeto
    print("\n--- Todos los campos guardados ---")
    for field in c._meta.fields:
        valor = getattr(c, field.name)
        print(f"{field.name}: {valor}")
        
    print("\n--- Campos JSON (Fondos) ---")
    # Intentar imprimir los campos JSON formateados si existen
    if hasattr(c, 'fondo_inicial'):
        print(f"Fondo Inicial: {json.dumps(c.fondo_inicial, indent=2)}")
    if hasattr(c, 'fondo_final'):
        print(f"Fondo Final: {json.dumps(c.fondo_final, indent=2)}")
    if hasattr(c, 'limpio'):
        print(f"Limpio: {json.dumps(c.limpio, indent=2)}")
    if hasattr(c, 'ajuste'):
        print(f"Ajuste: {json.dumps(c.ajuste, indent=2)}")
        
    print("=" * 40)
