#!/bin/bash
set -euo pipefail
PROJECT="/home/LottoBooM"; cd "$PROJECT"
G='\033[0;32m'; Y='\033[0;33m'; R='\033[0;31m'; NC='\033[0m'

BK="_backup_sidebar_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BK"
cp templates/base.html "$BK/base.html"
echo -e "${G}[✔]${NC} backup → $BK/base.html"
echo "$BK" > .last_backup_sidebar

python3 << 'PYEOF'
from pathlib import Path
import re

p = Path("/home/LottoBooM/templates/base.html")
src = p.read_text(encoding="utf-8")
original = src

# ─── 1) Cliente: insertar "Mis movimientos" después de cada bloque mis_apuestas ───
# Regex: <a href="{% url 'jugadas:mis_apuestas' %}"...> ... </a>
patron_cliente = re.compile(
    r"(<a\s+href=\"\{%\s*url\s*'jugadas:mis_apuestas'\s*%\}\"[^>]*>.*?</a>)",
    re.DOTALL,
)
bloque_mis = '''<a href="{% url 'usuarios:mis_movimientos' %}" class="menu-item">
      <i class="fas fa-book"></i>
      <span>Mis movimientos</span>
    </a>'''

def rep_cliente(m):
    original_a = m.group(1)
    # Detectar indentación real del bloque (espacios antes del `<a`)
    idx = m.start()
    inicio_linea = src.rfind("\n", 0, idx) + 1
    indent = src[inicio_linea:idx]
    bloque = "\n" + indent + bloque_mis.replace("\n    ", "\n" + indent)
    return original_a + bloque

src, n_cli = patron_cliente.subn(rep_cliente, src)
print(f"  • Cliente: {n_cli} inserción(es)")

# ─── 2) Gestor: insertar "Historial movimientos" después de recarga_directa ───
patron_gestor = re.compile(
    r"(<a\s+href=\"\{%\s*url\s*'roles:recarga_directa'\s*%\}\"[^>]*>.*?</a>)",
    re.DOTALL,
)
bloque_rec = '''<a href="{% url 'roles:historial_movimientos' %}" class="menu-item">
      <i class="fas fa-book"></i>
      <span>Historial movimientos</span>
    </a>'''

def rep_gestor(m):
    original_a = m.group(1)
    idx = m.start()
    inicio_linea = src.rfind("\n", 0, idx) + 1
    indent = src[inicio_linea:idx]
    bloque = "\n" + indent + bloque_rec.replace("\n    ", "\n" + indent)
    return original_a + bloque

src, n_ges = patron_gestor.subn(rep_gestor, src)
print(f"  • Gestor: {n_ges} inserción(es)")

if src == original:
    print("  ○ Sin cambios (quizás ya estaba aplicado)")
    raise SystemExit(0)

# Sanity: no dejar duplicados si ya existe
if src.count("usuarios:mis_movimientos") > n_cli:
    print(f"  ⚠ Ya había enlaces previos — revisar manualmente")
if src.count("roles:historial_movimientos") > n_ges:
    print(f"  ⚠ Ya había enlaces previos — revisar manualmente")

p.write_text(src, encoding="utf-8")
print("  ✔ base.html guardado")
PYEOF

echo ""
echo -e "${G}🎉 SIDEBAR ACTUALIZADO${NC}"
echo "Backup: $BK/base.html"
echo "Rollback: cp $BK/base.html /home/LottoBooM/templates/base.html"
