from pathlib import Path
import re

p = Path("/home/LottoBooM/templates/base.html")
src = p.read_text(encoding="utf-8")

# ═══════════════════════════════════════════════════════════════
# 1. Eliminar el enlace del menú de auditor
# ═══════════════════════════════════════════════════════════════
viejo_auditor = '''    {% if user.is_authenticated %}{% if user.roles.all %}{% for r in user.roles.all %}{% if r.tipo != 'cliente' and r.activo %}<a href="#" id="sidebarLimitesLink" class="menu-item" style="cursor:pointer;"><i class="fas fa-chart-bar"></i><span>Límites y dosis</span></a>{% endif %}{% endfor %}{% endif %}{% endif %}'''

if viejo_auditor in src:
    src = src.replace(viejo_auditor, "", 1)
    print("1: OK (enlace eliminado del menú auditor)")
else:
    print("1: WARN (no encontre el enlace en auditor)")

# ═══════════════════════════════════════════════════════════════
# 2. Insertar enlace en el menú de gestor, después de recarga_directa
# ═══════════════════════════════════════════════════════════════
viejo_gestor = '''<a href="{% url 'roles:recarga_directa' %}" class="menu-item">'''

nuevo_gestor = '''<a href="{% url 'roles:recarga_directa' %}" class="menu-item">'''

# Buscar el bloque completo del recarga_directa (con su contenido)
patron = re.compile(
    r"(<a href=\"\{% url 'roles:recarga_directa' %\}\" class=\"menu-item\">.*?</a>)",
    re.DOTALL,
)

m = patron.search(src)
if m:
    enlace_recarga = m.group(1)
    enlace_limites = '''

        <a href="#" id="sidebarLimitesLink" class="menu-item" style="cursor:pointer;">
            <i class="fas fa-chart-bar"></i>
            <span>Límites y dosis</span>
        </a>'''
    src = src[:m.end()] + enlace_limites + src[m.end():]
    print("2: OK (enlace insertado después de recarga_directa)")
else:
    print("2: ERROR (no encontre el bloque recarga_directa)")

p.write_text(src, encoding="utf-8")

# Verificar
print("")
print("--- VERIFICACION ---")
print("sidebarLimitesLink:", src.count("sidebarLimitesLink"), "(debe ser 2: html + js)")
print("Después de recarga_directa:", "OK" if "recarga_directa" in src else "NO")
