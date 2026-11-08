import csv
from django.contrib.auth.models import User
from roles.models import Rol

# Buscar a todos los usuarios que tengan el rol de cliente
clientes_ids = Rol.objects.filter(tipo='cliente', activo=True).values_list('usuario_id', flat=True)
clientes = User.objects.filter(id__in=clientes_ids, is_active=True).order_by('username')

with open('saldos.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['usuario', 'forma_pago', 'monto'])
    
    for c in clientes:
        # Creamos una línea por defecto con Tarjeta y monto 0
        writer.writerow([c.username, 'Tarjeta', '0.00'])

print(f"✅ Plantilla creada con {clientes.count()} clientes en el archivo 'saldos.csv'.")
print("👉 Ahora abre el archivo, cambia los montos y ejecuta el script de carga.")
