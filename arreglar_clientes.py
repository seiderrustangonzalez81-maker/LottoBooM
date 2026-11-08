from django.contrib.auth.models import User
from roles.models import Fondo, Rol
from pagos.models import FormaPago

seider = User.objects.get(username__iexact='Seider')
forma_pago = FormaPago.objects.filter(activo=True).first()

if not forma_pago:
    print("❌ ERROR: No hay formas de pago activas.")
else:
    usuarios = User.objects.filter(is_active=True).exclude(id=seider.id)
    roles_creados = 0
    fondos_creados = 0

    for u in usuarios:
        # 1. Asignar rol de cliente si no lo tiene
        if not Rol.objects.filter(usuario=u, tipo='cliente', activo=True).exists():
            Rol.objects.filter(usuario=u, activo=True).update(activo=False)
            Rol.objects.create(usuario=u, tipo='cliente', activo=True)
            roles_creados += 1
        
        # 2. Vincular fondo con Seider (que es el banco)
        if not Fondo.objects.filter(usuario=u, asignado_por=seider).exists():
            Fondo.objects.create(
                usuario=u,
                asignado_por=seider,
                forma_pago=forma_pago,
                monto=0.00,
                activo=True
            )
            fondos_creados += 1

    print(f"✅ Se asignó el rol de cliente a {roles_creados} usuarios.")
    print(f"✅ Se crearon {fondos_creados} fondos vinculados a Seider.")
