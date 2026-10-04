from pathlib import Path
import ast

p = Path("/home/LottoBooM/roles/models.py")
src = p.read_text(encoding="utf-8")

if "FIX_PRESTAMO_V1" in src:
    print("SKIP: ya aplicado")
    raise SystemExit(0)

viejo = """    aprobado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, default=None, related_name='prestamos_aprobados')
    comercial_comun = models.ForeignKey(User, on_delete=models.CASCADE, related_name='prestamos_comunes', null=True, blank=True, default=None)
    metadata = models.JSONField(default=dict, blank=True)"""

nuevo = """    aprobado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, default=None, related_name='prestamos_aprobados')
    comercial_comun = models.ForeignKey(User, on_delete=models.CASCADE, related_name='prestamos_comunes', null=True, blank=True, default=None)
    # FIX_PRESTAMO_V1: forma de pago + gestor + fecha_saldado
    forma_pago = models.ForeignKey('pagos.FormaPago', on_delete=models.PROTECT, null=True, blank=True, related_name='prestamos')
    gestor = models.ForeignKey(User, on_delete=models.PROTECT, null=True, blank=True, related_name='prestamos_como_gestor')
    fecha_saldado = models.DateTimeField(null=True, blank=True, default=None)
    metadata = models.JSONField(default=dict, blank=True)"""

if viejo not in src:
    print("ERROR: no encontré el bloque de campos")
    raise SystemExit(1)

src = src.replace(viejo, nuevo, 1)

# Agregar 'saldado' a ESTADOS
viejo2 = """        ('pagado', 'Pagado'),
        ('rechazado', 'Rechazado'),
        ('vencido', 'Vencido'),
    ]"""
nuevo2 = """        ('pagado', 'Pagado'),
        ('saldado', 'Saldado'),
        ('rechazado', 'Rechazado'),
        ('vencido', 'Vencido'),
    ]"""

if viejo2 in src:
    src = src.replace(viejo2, nuevo2, 1)
    print("OK: estado 'saldado' agregado")

try:
    ast.parse(src)
except SyntaxError as e:
    print(f"ERROR sintaxis: {e}")
    raise SystemExit(1)

p.write_text(src, encoding="utf-8")
print("OK: campos agregados")
