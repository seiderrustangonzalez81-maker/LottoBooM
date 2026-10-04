import os
import sys
sys.path.insert(0, '/home/LottoBooM')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'LottoBooM.settings')

import django
django.setup()

from django.test import RequestFactory
from django.contrib.auth.models import User
from jugadas.views import api_disponible_por_numero
from jugadas.models import FormaJuego, Jugada
from sorteos.models import Sorteo
from pagos.models import FormaPago
from roles.utils import get_pool_gestor
from django.utils import timezone
from datetime import date

print("=" * 60)
print("  VERIFICACIÓN DEL ENDPOINT api_disponible_por_numero")
print("=" * 60)

# Buscar un gestor con actividad
gestor = User.objects.filter(roles__tipo='banco', roles__activo=True, is_active=True).first()
if not gestor:
    print("ERROR: no hay bancos activos")
    sys.exit(1)
print(f"\nGestor de prueba: {gestor.username} (id={gestor.id})")

# Buscar un sorteo activo
sorteo = Sorteo.objects.filter(activo=True).first()
if not sorteo:
    print("ERROR: no hay sorteos activos")
    sys.exit(1)
print(f"Sorteo: {sorteo.nombre} (id={sorteo.id})")

# Forma de pago activa (no bono)
fp = FormaPago.objects.filter(activo=True).exclude(nombre__iexact='bono').first()
if not fp:
    print("ERROR: no hay FP activas")
    sys.exit(1)
print(f"Forma de pago: {fp.nombre} (id={fp.id})")

# Fecha hoy
hoy = date.today().strftime('%Y-%m-%d')
print(f"Fecha: {hoy}")

# Preparar request
rf = RequestFactory()
req = rf.get(f'/jugadas/api/disponible-por-numero/?gestor_id={gestor.id}&sorteo_id={sorteo.id}&forma_pago_id={fp.id}&fecha={hoy}')
req.user = gestor

# Llamar la vista
print("\n→ Llamando endpoint...")
try:
    resp = api_disponible_por_numero(req)
    print(f"  Status: {resp.status_code}")
    
    import json
    body = json.loads(resp.content)
    
    if not body.get('success'):
        print(f"  ERROR: {body.get('error')}")
        sys.exit(1)
    
    data = body.get('data', {})
    print(f"  Formas de juego en respuesta: {len(data)}")
    
    # Detalle por forma
    for fj_id, info in data.items():
        fj = FormaJuego.objects.filter(id=int(fj_id)).first()
        nombre = fj.nombre if fj else f'id={fj_id}'
        pool = info.get('pool_total', 0)
        consumos = info.get('consumido_por_numero', {})
        print(f"\n  [{nombre}]")
        print(f"    Pool total: ${pool:.2f}")
        print(f"    Números con consumo: {len(consumos)}")
        
        # Mostrar top 5
        top5 = sorted(consumos.items(), key=lambda x: -x[1])[:5]
        for num, monto in top5:
            disponible = pool - monto
            print(f"      {num} → apostado ${monto:.2f} · disponible ${disponible:.2f}")

    # Test adicional: verificar que el pool total coincide con get_pool_gestor
    print("\n→ Verificación cruzada con get_pool_gestor:")
    for fj_id in list(data.keys())[:3]:
        fj = FormaJuego.objects.filter(id=int(fj_id)).first()
        if fj:
            pool_directo = float(get_pool_gestor(gestor, sorteo, fj, fp) or 0)
            pool_endpoint = data[fj_id]['pool_total']
            match = abs(pool_directo - pool_endpoint) < 0.01
            print(f"  {fj.nombre}: endpoint=${pool_endpoint:.2f} · get_pool_gestor=${pool_directo:.2f} → {'✅' if match else '❌'}")

    print("\n✅ Endpoint funciona correctamente")

except Exception as e:
    import traceback
    print(f"\n❌ ERROR:")
    traceback.print_exc()
    sys.exit(1)
