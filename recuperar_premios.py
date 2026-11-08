import csv
from django.contrib.auth.models import User
from roles.models import Fondo, MovimientoFondo
from pagos.models import FormaPago
from decimal import Decimal

seider = User.objects.get(username__iexact='Seider')
procesados = 0
total_abonado = Decimal('0.00')

# Leer el archivo CSV
with open('reproceso_premios_detalle.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        # Solo procesar los que están pendientes
        if row.get('estado_premio', '').strip().lower() != 'pendiente':
            continue

        username = row['cliente'].strip()
        fp_nombre = row['forma_pago'].strip()
        try:
            monto = Decimal(row['monto_premio'].strip())
        except:
            continue

        # Buscar usuario
        usuario = User.objects.filter(username__iexact=username).first()
        if not usuario:
            continue

        # Buscar forma de pago
        forma_pago = FormaPago.objects.filter(nombre__iexact=fp_nombre).first()
        if not forma_pago:
            continue

        # Buscar o crear el fondo para ese cliente y esa forma de pago
        fondo, created = Fondo.objects.get_or_create(
            usuario=usuario, asignado_por=seider, forma_pago=forma_pago,
            defaults={'monto': Decimal('0.00'), 'activo': True}
        )
        
        # Sumar el monto al fondo
        saldo_antes = fondo.monto
        fondo.monto += monto
        fondo.save()

        # Registrar el movimiento para que quede en el historial
        MovimientoFondo.objects.create(
            emisor=None, receptor=usuario, forma_pago=forma_pago,
            monto=monto, tipo='ajuste', estado='confirmado',
            motivo=f"Recuperación de premio pendiente: {row['sorteo']}",
            saldo_antes=saldo_antes, saldo_despues=fondo.monto,
            datos_transferencia={'origen': 'csv_rescate_premios', 'jugada_id': row['jugada_id']}
        )

        procesados += 1
        total_abonado += monto

print(f"✅ Se procesaron {procesados} premios pendientes.")
print(f"💰 Se recuperó un total de: ${total_abonado}")
