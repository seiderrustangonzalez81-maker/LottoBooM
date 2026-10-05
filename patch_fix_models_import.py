from pathlib import Path
import ast

p = Path("/home/LottoBooM/roles/utils.py")
src = p.read_text(encoding="utf-8")

if "FIX_MODELS_IMPORT_V1" in src:
    print("SKIP: ya aplicado")
    raise SystemExit(0)

# Buscar la línea con "from django.db import models" o "from django.db import"
if "from django.db import models" in src:
    print("SKIP: models ya está importado arriba")
    raise SystemExit(0)

# Estrategia: reemplazar `models.Q` por import local
# Ya que el helper no importa models, hacemos import local dentro de la función

viejo = """    from decimal import Decimal
    from roles.models import Fondo, Bono, Postpago
    from pagos.models import FormaPago

    CERO = Decimal('0.00')"""

nuevo = """    # FIX_MODELS_IMPORT_V1
    from decimal import Decimal
    from django.db import models
    from roles.models import Fondo, Bono, Postpago
    from pagos.models import FormaPago

    CERO = Decimal('0.00')"""

if viejo not in src:
    print("ERROR: no encontré el bloque dentro de calcular_saldos_cliente")
    # Buscar alternativas
    if "CERO = Decimal('0.00')" in src:
        src = src.replace(
            "    CERO = Decimal('0.00')",
            "    # FIX_MODELS_IMPORT_V1\n    from django.db import models\n    CERO = Decimal('0.00')",
            1
        )
        print("OK: aplicado por CERO")
    else:
        raise SystemExit(1)
else:
    src = src.replace(viejo, nuevo, 1)
    print("OK: models importado dentro de la función")

try:
    ast.parse(src)
except SyntaxError as e:
    print(f"ERROR sintaxis: {e}")
    raise SystemExit(1)

p.write_text(src, encoding="utf-8")
print("OK: fix aplicado")
