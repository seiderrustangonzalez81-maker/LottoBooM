from django.db import models

# La app comercial usa los modelos de roles:
# - RelacionUsuario: relación comercial ↔ cliente
# - Fondo: fondos asignados por sorteo
# - RelacionUsuario: relación banco ↔ comercial
# No necesita modelos propios adicionales.