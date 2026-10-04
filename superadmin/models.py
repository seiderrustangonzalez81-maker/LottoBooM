from django.db import models

# La app superadmin no necesita modelos propios.
# Toda la lógica se maneja desde las otras apps:
# - usuarios: perfiles
# - roles: jerarquía
# - jugadas: apuestas
# - pagos: transacciones