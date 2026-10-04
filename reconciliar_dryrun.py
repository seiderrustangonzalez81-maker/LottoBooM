import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'LottoBooM.settings')
django.setup()

from decimal import Decimal
from django.db.models import Sum
from roles.models import Fondo, MovimientoFondo

TIPOS_FONDO = ['recarga', 'apuesta', 'premio', 'retiro', 'ajuste']

print("=" * 70)
print("  DRY RUN - Plan de reconciliacion")
print("=" * 70)
print()

fondos = Fondo.objects.filter(activo=True).select_related('usuario', 'forma_pago')

plan = []
for f in fondos:
    fondo_monto = f.monto or Decimal('0.00')
    movs = MovimientoFondo.objects.filter(
        receptor=f.usuario,
        forma_pago=f.forma_pago,
        tipo__in=TIPOS_FONDO,
    ).aggregate(t=Sum('monto'))['t'] or Decimal('0.00')
    diff = fondo_monto - movs

    if abs(diff) > Decimal('0.01'):
        plan.append({
            'user_id': f.usuario.id,
            'cliente': f.usuario.username,
            'fp_id': f.forma_pago.id if f.forma_pago else None,
            'fp': f.forma_pago.nombre if f.forma_pago else 'SIN FP',
            'fondo_id': f.id,
            'fondo_monto': fondo_monto,
            'movs_antes': movs,
            'diff': diff,
        })

plan.sort(key=lambda x: abs(x['diff']), reverse=True)

print(f"Se crearan {len(plan)} movimientos de reconciliacion.")
print()
print("--- LISTA COMPLETA ---")
for i, p in enumerate(plan, 1):
    signo = '+' if p['diff'] > 0 else ''
    print(f"  {i:2}. {p['cliente']:<20} (uid={p['user_id']:<4}) "
          f"FP={p['fp']:<15} "
          f"movs=${p['movs_antes']:<12} "
          f"-> ${p['fondo_monto']:<12} "
          f"[{signo}${p['diff']}]")

print()
total = sum(p['diff'] for p in plan)
print(f"Suma total de ajustes: ${total}")
print()

script_path = '/home/LottoBooM/reconciliar_apply.py'
with open(script_path, 'w') as fh:
    fh.write("# Auto-generado por reconciliar_dryrun.py\n")
    fh.write("import os\n")
    fh.write("import django\n")
    fh.write("os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'LottoBooM.settings')\n")
    fh.write("django.setup()\n\n")
    fh.write("from decimal import Decimal\n")
    fh.write("from django.db import transaction\n")
    fh.write("from django.utils import timezone\n")
    fh.write("from roles.models import Fondo, MovimientoFondo\n")
    fh.write("from django.contrib.auth.models import User\n")
    fh.write("from pagos.models import FormaPago\n\n")
    fh.write("PLAN = [\n")
    for p in plan:
        fh.write("    {'user_id': %d, 'cliente': %r, 'fp_id': %s, 'fondo_id': %d, "
                 "'diff': Decimal('%s'), 'movs_antes': Decimal('%s'), "
                 "'fondo_monto': Decimal('%s')},\n" % (
                     p['user_id'], p['cliente'], p['fp_id'], p['fondo_id'],
                     p['diff'], p['movs_antes'], p['fondo_monto']))
    fh.write("]\n\n")
    fh.write('''print(f"Reconciliando {len(PLAN)} fondos...")
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
''')

print(f"Script generado: {script_path}")
