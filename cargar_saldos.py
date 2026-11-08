import csv
from django.contrib.auth.models import User
from roles.models import Fondo, MovimientoFondo
from pagos.models import FormaPago
from decimal import Decimal

seider = User.objects.get(username__iexact='Seider')
procesados = 0
total = Decimal('0.00')

try:
    with open('saldos.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            username = row['usuario'].strip()
            fp_nombre = row['forma_pago'].strip()
            try:
                monto = Decimal(row['monto'].strip())
            except:
                continue
                
            usuario = User.objects.filter(username__iexact=username).first()
            if not usuario:
                print(f"⚠️ Usuario no encontrado: {username}")
                continue
                
            forma_pago = FormaPago.objects.filter(nombre__iexact=fp_nombre).first()
            if not forma_pago:
                print(f"⚠️ Forma de pago no válida para {username}: {fp_nombre}")
                continue
                
            fondo, created = Fondo.objects.get_or_create(
                usuario=usuario, asignado_por=seider, forma_pago=forma_pago,
                defaults={'monto': Decimal('0.00'), 'activo': True}
            )
            
            saldo_antes = fondo.monto
            fondo.monto += monto
            fondo.save()
            
            MovimientoFondo.objects.create(
                emisor=None, receptor=usuario, forma_pago=forma_pago,
                monto=monto, tipo='ajuste', estado='confirmado',
                motivo="Restauración manual de saldo post-falla",
                saldo_antes=saldo_antes, saldo_despues=fondo.monto,
                datos_transferencia={'origen': 'carga_manual_csv'}
            )
            procesados += 1
            total += monto
            print(f"✅ {username} | +${monto} en {fp_nombre}")

    print(f"\n🎉 Proceso terminado. Se cargaron {procesados} saldos por un total de ${total}")
except FileNotFoundError:
    print("❌ No se encontró el archivo 'saldos.csv'. Súbelo a la carpeta principal.")
