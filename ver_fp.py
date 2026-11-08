from pagos.models import FormaPago
for fp in FormaPago.objects.all():
    print(f"ID: {fp.id} | Nombre: {fp.nombre} | Activa: {fp.activo}")
