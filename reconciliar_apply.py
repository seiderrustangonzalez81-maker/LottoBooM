# Auto-generado por reconciliar_dryrun.py
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'LottoBooM.settings')
django.setup()

from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from roles.models import Fondo, MovimientoFondo
from django.contrib.auth.models import User
from pagos.models import FormaPago

PLAN = [
    {'user_id': 40, 'cliente': 'Kasama', 'fp_id': 3, 'fondo_id': 19, 'diff': Decimal('-28172.00'), 'movs_antes': Decimal('29500'), 'fondo_monto': Decimal('1328.00')},
    {'user_id': 39, 'cliente': 'Yoel', 'fp_id': 3, 'fondo_id': 23, 'diff': Decimal('-23145.94'), 'movs_antes': Decimal('47300'), 'fondo_monto': Decimal('24154.06')},
    {'user_id': 43, 'cliente': 'Yudy', 'fp_id': 3, 'fondo_id': 22, 'diff': Decimal('22612.00'), 'movs_antes': Decimal('60480'), 'fondo_monto': Decimal('83092.00')},
    {'user_id': 55, 'cliente': 'Camagüey-JC', 'fp_id': 3, 'fondo_id': 33, 'diff': Decimal('-12618.20'), 'movs_antes': Decimal('16920'), 'fondo_monto': Decimal('4301.80')},
    {'user_id': 61, 'cliente': 'Roberto-Carlos', 'fp_id': 3, 'fondo_id': 38, 'diff': Decimal('9675.00'), 'movs_antes': Decimal('150'), 'fondo_monto': Decimal('9825.00')},
    {'user_id': 48, 'cliente': 'yusyyusy', 'fp_id': 3, 'fondo_id': 25, 'diff': Decimal('-8763.00'), 'movs_antes': Decimal('17858'), 'fondo_monto': Decimal('9095.00')},
    {'user_id': 45, 'cliente': 'Yasnay', 'fp_id': 3, 'fondo_id': 21, 'diff': Decimal('-6820.00'), 'movs_antes': Decimal('6800'), 'fondo_monto': Decimal('-20.00')},
    {'user_id': 67, 'cliente': 'Juan', 'fp_id': 3, 'fondo_id': 43, 'diff': Decimal('5000.00'), 'movs_antes': Decimal('0.00'), 'fondo_monto': Decimal('5000.00')},
    {'user_id': 63, 'cliente': 'NIxon', 'fp_id': 3, 'fondo_id': 40, 'diff': Decimal('-3599.32'), 'movs_antes': Decimal('13920'), 'fondo_monto': Decimal('10320.68')},
    {'user_id': 60, 'cliente': 'Lázarohb', 'fp_id': 3, 'fondo_id': 37, 'diff': Decimal('-3199.88'), 'movs_antes': Decimal('3230'), 'fondo_monto': Decimal('30.12')},
    {'user_id': 56, 'cliente': 'Silvita', 'fp_id': 3, 'fondo_id': 34, 'diff': Decimal('-3051.64'), 'movs_antes': Decimal('8770'), 'fondo_monto': Decimal('5718.36')},
    {'user_id': 46, 'cliente': 'Reynaldo@691204', 'fp_id': 3, 'fondo_id': 28, 'diff': Decimal('-3000.00'), 'movs_antes': Decimal('3000'), 'fondo_monto': Decimal('0.00')},
    {'user_id': 50, 'cliente': 'Luis', 'fp_id': 3, 'fondo_id': 27, 'diff': Decimal('2000.00'), 'movs_antes': Decimal('0.00'), 'fondo_monto': Decimal('2000.00')},
    {'user_id': 62, 'cliente': 'Robert', 'fp_id': 3, 'fondo_id': 39, 'diff': Decimal('1800.00'), 'movs_antes': Decimal('0.00'), 'fondo_monto': Decimal('1800.00')},
    {'user_id': 52, 'cliente': 'Adile', 'fp_id': 3, 'fondo_id': 30, 'diff': Decimal('1501.00'), 'movs_antes': Decimal('4520'), 'fondo_monto': Decimal('6021.00')},
    {'user_id': 41, 'cliente': 'Yuli', 'fp_id': 3, 'fondo_id': 18, 'diff': Decimal('-1200.00'), 'movs_antes': Decimal('1200'), 'fondo_monto': Decimal('0.00')},
    {'user_id': 53, 'cliente': 'Celiacel', 'fp_id': 3, 'fondo_id': 31, 'diff': Decimal('1060.00'), 'movs_antes': Decimal('0.00'), 'fondo_monto': Decimal('1060.00')},
    {'user_id': 54, 'cliente': 'Ernesto', 'fp_id': 3, 'fondo_id': 32, 'diff': Decimal('335.00'), 'movs_antes': Decimal('0.00'), 'fondo_monto': Decimal('335.00')},
    {'user_id': 58, 'cliente': 'Yaris', 'fp_id': 3, 'fondo_id': 36, 'diff': Decimal('250.00'), 'movs_antes': Decimal('0.00'), 'fondo_monto': Decimal('250.00')},
    {'user_id': 64, 'cliente': 'Yurislay', 'fp_id': 3, 'fondo_id': 41, 'diff': Decimal('124.00'), 'movs_antes': Decimal('150'), 'fondo_monto': Decimal('274.00')},
    {'user_id': 44, 'cliente': 'YSD', 'fp_id': 3, 'fondo_id': 20, 'diff': Decimal('40.00'), 'movs_antes': Decimal('0.00'), 'fondo_monto': Decimal('40.00')},
    {'user_id': 3, 'cliente': 'Seider', 'fp_id': 8, 'fondo_id': 16, 'diff': Decimal('-10.00'), 'movs_antes': Decimal('0.00'), 'fondo_monto': Decimal('-10.00')},
]

print(f"Reconciliando {len(PLAN)} fondos...")
print()

creados = 0
errores = 0

with transaction.atomic():
    for item in PLAN:
        try:
            usuario = User.objects.get(id=item['user_id'])
            forma_pago = FormaPago.objects.filter(id=item['fp_id']).first() if item['fp_id'] else None

            if not forma_pago:
                print(f"  SKIP {item['cliente']}: sin FP")
                continue

            MovimientoFondo.objects.create(
                emisor=None,
                receptor=usuario,
                forma_pago=forma_pago,
                monto=item['diff'],
                tipo='ajuste',
                estado='confirmado',
                motivo='Reconciliacion historica de auditoria',
                nota=f"Ajuste automatico. Saldo previo: ${item['movs_antes']}",
                saldo_antes=item['movs_antes'],
                saldo_despues=item['fondo_monto'],
                datos_transferencia={
                    'reconciliacion': True,
                    'fecha_reconciliacion': timezone.now().isoformat(),
                    'diff': float(item['diff']),
                    'fondo_id': item['fondo_id'],
                },
            )
            creados += 1
            signo = '+' if item['diff'] > 0 else ''
            print(f"  OK {item['cliente']:<20} {signo}${item['diff']}")
        except Exception as e:
            errores += 1
            print(f"  ERR {item['cliente']}: {e}")

print()
print(f"Creados: {creados}")
print(f"Errores: {errores}")
print()
print("Reconciliacion completada.")
