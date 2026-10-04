from pathlib import Path

p = Path("/home/LottoBooM/templates/base.html")
src = p.read_text(encoding="utf-8")

if "menu-prestamos-link" in src:
    print("SKIP: ya aplicado")
    raise SystemExit(0)

# 1. CSS del badge "Nuevo"
css_viejo = ".sidebar-menu .menu-item.active {"
css_nuevo = """/* FIX_PRESTAMO_V1: badge "Nuevo" amarillo */
    .menu-item.menu-item-nuevo { position: relative; }
    .menu-item.menu-item-nuevo .badge-nuevo {
        background: #facc15;
        color: #422006;
        font-size: 0.6rem;
        font-weight: 800;
        padding: 2px 7px;
        border-radius: 10px;
        margin-left: auto;
        text-transform: uppercase;
        letter-spacing: 0.3px;
        animation: badgeNuevoPulse 1.8s ease-in-out infinite;
    }
    @keyframes badgeNuevoPulse {
        0%,100% { box-shadow: 0 0 0 0 rgba(250,204,21,.6); }
        50%     { box-shadow: 0 0 0 6px rgba(250,204,21,0); }
    }

    .sidebar-menu .menu-item.active {"""

if css_viejo in src:
    src = src.replace(css_viejo, css_nuevo, 1)
    print("OK: CSS badge agregado")

# 2. Insertar el link después de 'usuarios:mis_fondos' (que está en el bloque del cliente)
ancla = """<a href="{% url 'usuarios:mis_fondos' %}" class="menu-item">"""
if ancla not in src:
    print("ERROR: no encontré el ancla usuarios:mis_fondos")
    raise SystemExit(1)

bloque_link = """{% if mostrar_link_prestamos %}
        <a href="{% url 'roles:mis_prestamos' %}" class="menu-item menu-prestamos-link {% if not perfil_prestamo_badge_visto %}menu-item-nuevo{% endif %}">
            <i class="fas fa-hand-holding-usd"></i> <span class="text">Préstamos</span>
            {% if not perfil_prestamo_badge_visto %}<span class="badge-nuevo">Nuevo</span>{% endif %}
        </a>
        {% endif %}
        """ + ancla

src = src.replace(ancla, bloque_link, 1)

p.write_text(src, encoding="utf-8")
print("OK: link de préstamos agregado al sidebar")
