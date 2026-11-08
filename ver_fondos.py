from django.contrib.auth.models import User
from roles.models import Fondo
from django.db.models import Sum

try:
    seider = User.objects.get(username__iexact='Seider')
except User.DoesNotExist:
    print("❌ No se encontró al usuario Seider.")
    exit()

# Buscamos los fondos activos de Seider
fondos = Fondo.objects.filter(asignado_por=seider, activo=True).select_related('usuario', 'forma_pago').order_by('usuario__username')

if not fondos.exists():
    print("No hay ningún fondo registrado para Seider.")
else:
    print("=== DETALLE DE FONDOS POR CLIENTE Y FORMA DE PAGO ===")
    for f in fondos:
        cliente = f.usuario.username
        fp = f.forma_pago.nombre if f.forma_pago else "Sin FP"
        monto = f.monto
        print(f"Cliente: {cliente:<20} | Forma de Pago: {fp:<15} | Monto: ${monto}")

    print("\n=== TOTAL GENERAL POR CLIENTE ===")
    totales = fondos.values('usuario__username').annotate(total=Sum('monto')).order_by('usuario__username')
    for t in totales:
        print(f"Cliente: {t['usuario__username']:<20} | Total: ${t['total']}")
