from pathlib import Path
import re

p = Path("/home/LottoBooM/roles/models.py")
src = p.read_text(encoding="utf-8")

if "MOTIVOS_RETIRO" in src:
    print("SKIP: ya aplicado")
    raise SystemExit(0)

# Ancla: dentro de class SolicitudRetiro, justo antes de "class Meta:"
patron = re.compile(
    r"(class SolicitudRetiro\(models\.Model\):.*?)(\n    class Meta:)",
    re.DOTALL,
)

if not patron.search(src):
    print("ERROR: no encontre class SolicitudRetiro")
    raise SystemExit(1)

# Bloque de choices + campo motivo
inserto = '''

    MOTIVOS_RETIRO = [
        ('cobro_premios', 'Cobro de premios'),
        ('donacion_banco', 'Donacion al banco'),
        ('donacion_comercial', 'Donacion al comercial'),
        ('donacion_gestor', 'Donacion al gestor'),
        ('otro', 'Otro (especificar)'),
    ]

    motivo_tipo = models.CharField(
        max_length=30, choices=MOTIVOS_RETIRO,
        default='cobro_premios',
        verbose_name='Motivo del retiro',
    )
    motivo_detalle = models.CharField(
        max_length=200, blank=True, default='',
        verbose_name='Detalle del motivo',
        help_text='Obligatorio solo si motivo_tipo = "otro".',
    )
'''

src_new, n = patron.subn(r"\1" + inserto + r"\2", src, count=1)
if n == 0:
    print("ERROR en sub")
    raise SystemExit(1)

p.write_text(src_new, encoding="utf-8")
print("OK roles/models.py SolicitudRetiro con motivo_tipo + motivo_detalle")

import ast
ast.parse(src_new)
print("OK sintaxis")
