import time
from django.db import transaction
from django.contrib.auth.models import User
from jugadas.models import Jugada
from roles.models import Rol, Subordinacion

inicio = time.time()
print("⏳ Cargando datos en memoria...")

# 1. Cargar todas las jugadas (solo los IDs únicos) en 1 sola consulta
relaciones = list(Jugada.objects.values('usuario_id', 'destinatario_id').distinct())

# 2. Cargar todos los usuarios en 1 sola consulta y guardarlos en un diccionario
usuarios_dict = {u.id: u for u in User.objects.all()}

# 3. Cargar todos los roles en 1 sola consulta y guardarlos en un diccionario
roles_dict = {r.usuario_id: r for r in Rol.objects.filter(activo=True)}

print("🚀 Procesando relaciones...")

subordinaciones_crear = []
seider = usuarios_dict.get(User.objects.filter(username__iexact='Seider').first().id)

# Usamos un set para evitar duplicados
relaciones_creadas = set()

for r in relaciones:
    cliente_id = r['usuario_id']
    gestor_id = r['destinatario_id']
    
    if not cliente_id or not gestor_id or cliente_id == gestor_id:
        continue

    rol_cliente = roles_dict.get(cliente_id)
    rol_gestor = roles_dict.get(gestor_id)

    # Verificar que el cliente sea cliente y el gestor sea banco/comercial/superadmin
    if rol_cliente and rol_cliente.tipo == 'cliente' and rol_gestor and rol_gestor.tipo in ['banco', 'comercial', 'superadmin']:
        clave = (gestor_id, cliente_id)
        if clave not in relaciones_creadas:
            relaciones_creadas.add(clave)
            subordinaciones_crear.append(Subordinacion(jefe_id=gestor_id, subordinado_id=cliente_id, activo=True))

# 4. Insertar todo de golpe en la base de datos
print("💾 Guardando en la base de datos...")
with transaction.atomic():
    # Borrar las subordinaciones actuales para no duplicar
    Subordinacion.objects.all().delete()
    if subordinaciones_crear:
        Subordinacion.objects.bulk_create(subordinaciones_crear, batch_size=2000)

fin = time.time()
print(f"✅ ¡Listo! Se crearon {len(subordinaciones_crear)} relaciones Jefe->Subordinado.")
print(f"⏱️ Tiempo total: {fin - inicio:.2f} segundos.")
