from django.contrib.auth.models import User
from roles.models import Fondo
from pagos.models import FormaPago

seider = User.objects.get(username__iexact='Seider')
# Buscamos específicamente la forma de pago llamada Tarjeta
forma_pago_tarjeta = FormaPago.objects.filter(nombre__iexact='Tarjeta', activo=True).first()

if not forma_pago_tarjeta:
    print("❌ No existe una forma de pago activa llamada 'Tarjeta'.")
else:
    usuarios = User.objects.filter(is_active=True).exclude(id=seider.id)
    creados = 0
    
    for u in usuarios:
        # Si el cliente no tiene fondo en Tarjeta con Seider, lo creamos
        if not Fondo.objects.filter(usuario=u, asignado_por=seider, forma_pago=forma_pago_tarjeta).exists():
            Fondo.objects.create(
                usuario=u,
                asignado_por=seider,
                forma_pago=forma_pago_tarjeta,
                monto=0.00,
                activo=True
            )
            creados += 1
            
    print(f"✅ Se crearon {creados} fondos de 'Tarjeta' en $0.00 para los clientes.")
