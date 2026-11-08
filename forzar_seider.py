from django.contrib.auth.models import User
from roles.models import Rol, Fondo

# 1. Buscar a Seider
seider = User.objects.filter(username__iexact='seider').first()

if not seider:
    print("⚠️ No se encontró a 'Seider'. Creándolo...")
    seider = User.objects.create_user(username='seider', password='temporal123')
    print("✅ Usuario 'seider' creado con contraseña 'temporal123'.")

# 2. Ascender a Seider a Banco
rol, created = Rol.objects.update_or_create(
    usuario=seider,
    tipo='banco',
    defaults={'activo': True}
)
print(f"✅ Rol 'banco' asignado a {seider.username} (Activo: True)")

# 3. Reasignar TODOS los fondos a Seider
fondos = Fondo.objects.all()
total_fondos = fondos.count()

if total_fondos == 0:
    print("⚠️ ATENCIÓN: Hay 0 fondos en esta base de datos. No hay nada que reasignar.")
    print("💡 Si tu web sí muestra fondos, estás en la base de datos equivocada (revisa si estás en el entorno virtual o carpeta correcta).")
else:
    actualizados = 0
    for f in fondos:
        f.asignado_por = seider
        f.activo = True  # Nos aseguramos de que estén activos para que se vean
        f.save()
        actualizados += 1
    print(f"✅ ¡Éxito! Se reasignaron {actualizados} fondos de clientes a {seider.username}.")
