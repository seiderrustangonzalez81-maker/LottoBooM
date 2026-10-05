from pathlib import Path
import os, django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "LottoBooM.settings")
django.setup()

from django.contrib.auth.models import User
from roles.models import Fondo
from pagos.models import FormaPago
from decimal import Decimal

USERNAME = "TEST_MULTIGESTOR"

# ─── Crear/limpiar cliente ───
if User.objects.filter(username=USERNAME).exists():
    print(f"Cliente {USERNAME} ya existe — limpiando...")
    user = User.objects.get(username=USERNAME)
    Fondo.objects.filter(usuario=user).delete()
else:
    user = User.objects.create_user(
        username=USERNAME,
        password="test123456",
        is_active=True,
    )
    print(f"✅ Cliente creado: {USERNAME} (id={user.id})")

# ─── Encontrar 2 gestores con fondos propios ───
gestores = list(User.objects.filter(
    roles__tipo__in=['banco', 'comercial', 'superadmin'],
    roles__activo=True,
    is_active=True,
).distinct()[:2])

if len(gestores) < 2:
    # Buscar cualquiera que tenga fondos como asignado_por
    gestores = list(User.objects.filter(
        fondos_asignados__activo=True,
    ).distinct()[:2])

print(f"Gestores de prueba: {[g.username for g in gestores]}")

if len(gestores) < 2:
    print("❌ Necesito al menos 2 gestores en el sistema")
    raise SystemExit(1)

# ─── Forma de pago ───
fp = FormaPago.objects.filter(activo=True).first()
if not fp:
    print("❌ No hay formas de pago activas")
    raise SystemExit(1)

# ─── Crear fondos ───
print(f"\nCreando fondos en {fp.nombre}:")
saldos = [100, 50]
for i, g in enumerate(gestores):
    monto = Decimal(str(saldos[i]))
    f = Fondo.objects.create(
        usuario=user,
        forma_pago=fp,
        asignado_por=g,
        monto=monto,
        activo=True,
    )
    print(f"  {g.username}: ${monto} (Fondo id={f.id})")

print(f"\n✅ Cliente de prueba {USERNAME} listo")
print(f"   usuario: {USERNAME}")
print(f"   password: test123456")
print(f"   Debe borrarse al finalizar")
