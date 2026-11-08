from pagos.models import FormaPago

# 1. Renombrar los IDs existentes a nombres útiles
# (Puedes cambiar "Tarjeta Clásica" por el nombre exacto que uses)
fp1 = FormaPago.objects.filter(id=1).first()
if fp1:
    fp1.nombre = 'Tarjeta'
    fp1.save()

fp3 = FormaPago.objects.filter(id=3).first()
if fp3:
    fp3.nombre = 'Saldo Móvil'
    fp3.save()

fp9 = FormaPago.objects.filter(id=9).first()
if fp9:
    fp9.nombre = 'Zelle' # O el nombre que prefieras
    fp9.save()

print("✅ Formas de pago renombradas correctamente.")
for fp in FormaPago.objects.all():
    print(f"ID: {fp.id} | Nombre: {fp.nombre} | Activa: {fp.activo}")
