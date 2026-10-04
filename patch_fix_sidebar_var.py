from pathlib import Path

p = Path("/home/LottoBooM/templates/base.html")
src = p.read_text(encoding="utf-8")

if "es_cliente_sidebar" not in src:
    print("SKIP: no hay referencia a es_cliente_sidebar")
    raise SystemExit(0)

# Estrategia: reemplazar la condición por una que use user.roles directamente
# Buscar: {% if not es_cliente_sidebar %}
viejo = "{% if not es_cliente_sidebar %}"
nuevo = """{% if user.is_authenticated %}
  {% with roles=user.roles.all %}
  {% if roles %}
    {% with primer_tipo=roles.0.tipo %}
    {% if primer_tipo != 'cliente' %}
"""

# Y el cierre: {% endif %} → {% endif %}{% endwith %}{% endif %}{% endif %}
# Buscar el bloque completo
import re

patron = re.compile(
    r"(\{%\s*if not es_cliente_sidebar\s*%\}\s*\n\s*<a href=\"#\" id=\"sidebarLimitesLink\".*?</a>\s*\n\s*)\{%\s*endif\s*%\}",
    re.DOTALL,
)

nuevo_bloque = """{% if user.is_authenticated %}{% if user.roles.all %}{% for r in user.roles.all %}{% if r.tipo != 'cliente' and r.activo %}<a href="#" id="sidebarLimitesLink" class="menu-item" style="cursor:pointer;"><i class="fas fa-chart-bar"></i><span>Límites y dosis</span></a>{% endif %}{% endfor %}{% endif %}{% endif %}"""

src_new, n = patron.subn(nuevo_bloque, src, count=1)
if n == 0:
    print("WARN: no matcheo el patrón exacto, intentando variante...")
    # Variante más simple: solo reemplazar la línea del {% if %}
    viejo_alt = "{% if not es_cliente_sidebar %}"
    if viejo_alt in src:
        # Reemplazar por un for loop con condicional
        src = src.replace(
            "{% if not es_cliente_sidebar %}\n    <a href=\"#\" id=\"sidebarLimitesLink\" class=\"menu-item\" style=\"cursor:pointer;\">\n      <i class=\"fas fa-chart-bar\"></i>\n      <span>Límites y dosis</span>\n    </a>\n    {% endif %}",
            "{% for r in user.roles.all %}{% if r.tipo != 'cliente' and r.activo %}<a href=\"#\" id=\"sidebarLimitesLink\" class=\"menu-item\" style=\"cursor:pointer;\"><i class=\"fas fa-chart-bar\"></i><span>Límites y dosis</span></a>{% endif %}{% endfor %}",
            1,
        )
        print("OK: reemplazo simple aplicado")
    else:
        print("ERROR: no encontre el bloque")
        raise SystemExit(1)
else:
    src = src_new
    print("OK: reemplazo via regex aplicado")

p.write_text(src, encoding="utf-8")
print("OK: base.html actualizado")
print("Referencias es_cliente_sidebar restantes:", src.count("es_cliente_sidebar"))
