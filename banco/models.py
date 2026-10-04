from django.db import models

# La app banco usa los modelos de roles:
# - RelacionUsuario: relación banco ↔ comercial
# - RelacionUsuario: relación comercial ↔ cliente
# - Fondo: fondos asignados
# No necesita modelos propios adicionales.