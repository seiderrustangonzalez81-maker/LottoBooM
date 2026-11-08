from django.utils import timezone
from django.db import transaction
from django.db.models import Q
from roles.models import Fondo, MovimientoFondo

hoy = timezone.localdate()
print(f"🧹 Iniciando limpieza de saldos negativos para el día {hoy}...")

# 1. Buscar los IDs de todos los usuarios que tuvieron ALGÚN movimiento hoy
usuarios_con_movimiento_hoy = set(
    MovimientoFondo.objects.filter(
        Q(creado_en__date=hoy)
    ).values_list('emisor_id', 'receptor_id')
)
# Aplanar el set y quitar los None
usuarios_activos_hoy = set()
for emisor, receptor in usuarios_con_movimiento_hoy:
    if emisor: usuarios_activos_hoy.add(emisor)
    if receptor: usuarios_activos_hoy.add(receptor)

print(f"👤 Usuarios omitidos por tener movimientos hoy: {len(usuarios_activos_hoy)}")

# 2. Buscar fondos negativos que NO pertenezcan a esos usuarios
fondos_a_limpiar = Fondo.objects.filter(monto__lt=0).exclude(usuario_id__in=usuarios_activos_hoy)

print(f"🔍 Se encontraron {fondos_a_limpiar.count()} fondos negativos para limpiar.")

if fondos_a_limpiar.exists():
    with transaction.atomic():
        for fondo in fondos_a_limpiar:
            saldo_antes = fondo.monto
            fondo.monto = 0.00
            fondo.save(update_fields=['monto'])
            
            # Registrar el movimiento de ajuste para que quede en el historial
            MovimientoFondo.objects.create(
                emisor=None, 
                receptor=fondo.usuario, 
                forma_pago=fondo.forma_pago,
                monto=abs(saldo_antes), # Positivo porque estamos sumando para llegar a 0
                tipo='ajuste', 
                estado='confirmado',
                motivo="Limpieza de sobregiro (recargas originales perdidas)",
                saldo_antes=saldo_antes, 
                saldo_despues=0.00,
                datos_transferencia={'origen': 'limpieza_masiva_negativos'}
            )
    print("✅ Limpieza completada con éxito. Los saldos negativos ahora están en $0.00.")
else:
    print("✨ No se encontraron fondos negativos de otros clientes para limpiar.")

# Mostrar el estado de Adile para confirmar que no se tocó
adile = Fondos = Fondo.objects.filter(usuario__username__iexact='Adile')
for f in adile:
    print(f"Verificación Adile ({f.forma_pago.nombre}): ${f.monto}")
