from django.contrib.auth.models import User
from jugadas.models import Jugada
from roles.models import Rol, Subordinacion, RelacionClienteGestor
from django.db.models import Count

print("🔍 Analizando las 105,357 jugadas para reconstruir la jerarquía...")

# 1. Encontrar quién es el gestor principal de cada cliente
# Agrupamos por cliente (usuario) y vemos quién es el destinatario más frecuente
relaciones = Jugada.objects.values('usuario_id', 'destinatario_id').annotate(
    total=Count('id')
).order_by('usuario_id', '-total')

# 2. Limpiar relaciones actuales para no duplicar
Subordinacion.objects.all().delete()
RelacionClienteGestor.objects.all().delete()

clientes_vinculados = 0
comerciales_vinculados = 0
procesados = set()

for r in relaciones:
    cliente_id = r['usuario_id']
    gestor_id = r['destinatario_id']
    
    # Si ya procesamos a este cliente, ignoramos sus otras relaciones
    if cliente_id in procesados or not cliente_id or not gestor_id:
        continue
        
    procesados.add(cliente_id)
    
    try:
        cliente = User.objects.get(id=cliente_id)
        gestor = User.objects.get(id=gestor_id)
        
        # Verificar roles
        rol_cliente = Rol.objects.filter(usuario=cliente, tipo='cliente', activo=True).first()
        rol_gestor = Rol.objects.filter(usuario=gestor, activo=True).first()
        
        if rol_cliente and rol_gestor:
            if rol_gestor.tipo in ['comercial', 'banco', 'superadmin']:
                # Crear relación
                Subordinacion.objects.get_or_create(
                    jefe=gestor, subordinado=cliente, defaults={'activo': True}
                )
                RelacionClienteGestor.objects.get_or_create(
                    cliente=cliente, gestor=gestor, defaults={'activo': True, 'asignado_por': gestor}
                )
                clientes_vinculados += 1
                
                # Si el gestor es comercial, ver quién es su banco
                if rol_gestor.tipo == 'comercial' and rol_gestor.banco_asignado:
                    Subordinacion.objects.get_or_create(
                        jefe=rol_gestor.banco_asignado, subordinado=gestor, defaults={'activo': True}
                    )
                    comerciales_vinculados += 1
                    
    except Exception as e:
        continue

print(f"✅ Se vincularon {clientes_vinculados} clientes con sus gestores originales.")
print(f"✅ Se vincularon {comerciales_vinculados} comerciales con sus bancos.")
