from jugadas.models import Boleta
import json
from decimal import Decimal
from collections import defaultdict

print("🔍 Rastreando el uso de fondos y postpagos en las boletas...")

resumen_diario = defaultdict(lambda: {'fondo': Decimal('0.00'), 'postpago': Decimal('0.00'), 'boletas': 0})
boletas_con_metadata = 0

for b in Boleta.objects.all():
    # Si la boleta tiene metadata (donde se guarda cómo se pagó)
    if b.metadata and isinstance(b.metadata, dict) and 'pago' in b.metadata:
        boletas_con_metadata += 1
        pago = b.metadata['pago']
        fecha = b.creado_en.strftime('%Y-%m-%d')
        
        try:
            monto_fondo = Decimal(str(pago.get('fondo', '0.00')))
            monto_postpago = Decimal(str(pago.get('postpago', '0.00')))
        except:
            monto_fondo = Decimal('0.00')
            monto_postpago = Decimal('0.00')
            
        resumen_diario[fecha]['fondo'] += monto_fondo
        resumen_diario[fecha]['postpago'] += monto_postpago
        resumen_diario[fecha]['boletas'] += 1

print(f"✅ Boletas analizadas: {Boleta.objects.count()}")
print(f"✅ Boletas que guardaron cómo se pagaron: {boletas_con_metadata}\n")

if boletas_con_metadata == 0:
    print("⚠️ Las boletas no tienen registrado de dónde salió el dinero (metadata vacía).")
else:
    print("=== DINERO UTILIZADO EN APUESTAS POR DÍA ===")
    print(f"{'Fecha':<12} | {'Boletas':<8} | {'Pagado con Fondo':<20} | {'Pagado con Postpago':<20}")
    print("-" * 70)
    
    total_fondo = Decimal('0.00')
    total_postpago = Decimal('0.00')
    
    # Ordenar por fecha
    for fecha in sorted(resumen_diario.keys()):
        datos = resumen_diario[fecha]
        total_fondo += datos['fondo']
        total_postpago += datos['postpago']
        print(f"{fecha:<12} | {datos['boletas']:<8} | ${datos['fondo']:<19} | ${datos['postpago']:<19}")
        
    print("-" * 70)
    print(f"TOTAL FONDOS USADOS:    ${total_fondo}")
    print(f"TOTAL POSTPAGOS USADOS: ${total_postpago}")
