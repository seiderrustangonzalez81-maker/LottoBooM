from pathlib import Path
import os, django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "LottoBooM.settings")
django.setup()

from django.contrib.auth.models import User
from roles.models import Fondo, Bono, Postpago, Rol, MovimientoFondo

USERNAME = "TEST_MULTIGESTOR"

user = User.objects.filter(username=USERNAME).first()
if not user:
    print(f"SKIP: {USERNAME} no existe")
    raise SystemExit(0)

print(f"═══ Limpiando {USERNAME} (id={user.id}) ═══")

# Fondos
n1 = Fondo.objects.filter(usuario=user).delete()
print(f"  Fondos borrados: {n1}")

# Bonos
n2 = Bono.objects.filter(usuario=user).delete()
print(f"  Bonos borrados: {n2}")

# Postpagos
n3 = Postpago.objects.filter(cliente=user).delete()
print(f"  Postpagos borrados: {n3}")

# Roles
n4 = Rol.objects.filter(usuario=user).delete()
print(f"  Roles borrados: {n4}")

# Movimientos donde aparece
n5 = MovimientoFondo.objects.filter(
    models.Q(emisor=user) | models.Q(receptor=user)
).delete() if False else (0, {})  # Skip para no borrar histórico
print(f"  (Movimientos no borrados para conservar historial)")

# Usuario
user.delete()
print(f"  ✅ Usuario {USERNAME} eliminado")
