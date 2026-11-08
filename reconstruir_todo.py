from django.contrib.auth.models import User
from jugadas.models import Jugada
from roles.models import Rol, Subordinacion, RelacionClienteGestor

print("🔍 Reconstruyendo jerarquía completa...")

# 1. Vincular clientes faltantes usando CUALQUIER jugada
relaciones = Jugada.objects.values('usuario_id', 'destinatario_id').distinct()
clientes_vinculados = 0

for r in relaciones:
    cliente_id = r['usuario_id']
    gestor_id = r['destinatario_id']
    
    if not cliente_id or not gestor_id: continue
    
    try:
        cliente = User.objects.get(id=cliente_id)
        gestor = User.objects.get(id=gestor_id)
        
        # Solo si el cliente tiene rol de cliente y el gestor es comercial/banco
        if Rol.objects.filter(usuario=cliente, tipo='cliente', activo=True).exists() and \
           Rol.objects.filter(usuario=gestor, activo=True, tipo__in=['comercial', 'banco', 'superadmin']).exists():
            
            obj, created = Subordinacion.objects.get_or_create(
                jefe=gestor, subordinado=cliente, defaults={'activo': True}
            )
            if created: clientes_vinculados += 1
    except:
        pass

# 2. Vincular Comerciales a Seider (si existen y no tienen banco)
seider = User.objects.get(username__iexact='Seider')
comerciales = Rol.objects.filter(tipo='comercial', activo=True, banco_asignado__isnull=True)
comerciales_vinculados = 0

for c in comerciales:
    c.banco_asignado = seider
    c.save()
    Subordinacion.objects.get_or_create(jefe=seider, subordinado=c.usuario, defaults={'activo': True})
    comerciales_vinculados += 1

print(f"✅ Se vincularon {clientes_vinculados} clientes adicionales a sus gestores.")
print(f"✅ Se vincularon {comerciales_vinculados} comerciales sin banco a Seider.")
