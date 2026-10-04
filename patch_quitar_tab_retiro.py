from pathlib import Path
import re

p = Path("/home/LottoBooM/roles/templates/roles/recarga_directa.html")
src = p.read_text(encoding="utf-8")

if 'data-tab="retiro"' not in src:
    print("SKIP: ya aplicado")
    raise SystemExit(0)

# 1) Quitar el <button> del tab Retiro
patron_btn = re.compile(
    r"\s*<button\s+type=\"button\"\s+class=\"mov-tab tab-retiro\"\s+data-tab=\"retiro\".*?</button>",
    re.DOTALL,
)
src, n_btn = patron_btn.subn("", src, count=1)
print(f"  Boton retiro eliminado: {n_btn}")

# 2) Quitar el <form id="formRetiro">
patron_form = re.compile(
    r"\s*<form\s+method=\"post\"\s+class=\"mov-panel\"\s+id=\"formRetiro\".*?</form>",
    re.DOTALL,
)
src, n_form = patron_form.subn("", src, count=1)
print(f"  Form retiro eliminado: {n_form}")

# 3) Revertir el JS
src = src.replace(
    "var map = { recarga: 'formRecarga', postpago: 'formPostpago', ajuste: 'formAjuste', retiro: 'formRetiro' };",
    "var map = { recarga: 'formRecarga', postpago: 'formPostpago', ajuste: 'formAjuste' };",
)
print("  JS revertido")

# 4) Quitar 'retiro' del tipo_movimiento permitido en el template (si quedó)
# (en el template no hay, solo en la vista)

p.write_text(src, encoding="utf-8")

# Verificar
if 'data-tab="retiro"' in src:
    print("WARN aun queda data-tab=retiro")
else:
    print("OK tab retiro eliminado del template")
