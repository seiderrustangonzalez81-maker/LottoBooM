from pathlib import Path
import re

p = Path("/home/LottoBooM/templates/roles/responder_retiro.html")
if not p.exists():
    print("ERROR: no existe responder_retiro.html")
    raise SystemExit(1)

src = p.read_text(encoding="utf-8")

if "Motivo del cliente" in src:
    print("SKIP: ya aplicado")
    raise SystemExit(0)

# Ancla 1: buscar el bloque que muestra el monto
anclas = [
    "Monto a retirar",
    "Monto solicitado",
    "Monto:",
    "monto</",
]

encontrado = None
for a in anclas:
    if a in src:
        encontrado = a
        print(f"INFO: ancla encontrada: {a}")
        break

if not encontrado:
    print("ERROR: no encontre ancla de monto")
    print("Corre: head -120 templates/roles/responder_retiro.html")
    raise SystemExit(1)

# Insertar bloque de motivo después del primer cierre de div que contenga el monto
# Estrategia: buscar la línea con el monto y añadir después
patron = re.compile(
    r"(.*?" + re.escape(encontrado) + r".*?</(?:div|td|p|li|h\d)>)\s*\n",
    re.DOTALL,
)
m = patron.search(src)
if not m:
    print("ERROR: no pude aislar el bloque del monto")
    raise SystemExit(1)

# Detectar indentación
idx_ini = m.end()
indent_match = re.search(r"\n(\s*)", src[idx_ini:])
indent = indent_match.group(1) if indent_match else "        "

bloque_motivo = f'''
{indent}<div class="motivo-cliente-wrap" style="background:#fef3c7;border-left:4px solid #f59e0b;padding:10px 14px;border-radius:8px;margin:12px 0;">
{indent}  <div style="font-size:.7rem;font-weight:800;color:#78350f;text-transform:uppercase;letter-spacing:.4px;margin-bottom:4px;">Motivo declarado por el cliente</div>
{indent}  <div style="font-weight:700;color:#78350f;font-size:.88rem;">
{indent}    {{{{ solicitud.get_motivo_tipo_display }}}}
{indent}    {{% if solicitud.motivo_detalle %}} — {{{{ solicitud.motivo_detalle }}}}{{% endif %}}
{indent}  </div>
{indent}</div>
'''

src_new = src[:m.end()] + bloque_motivo + src[m.end():]
p.write_text(src_new, encoding="utf-8")
print("OK responder_retiro.html con motivo del cliente")
