#!/bin/bash
set -euo pipefail
PROJECT="/home/LottoBooM"; cd "$PROJECT"
G='\033[0;32m'; B='\033[1;34m'; NC='\033[0m'
step(){ echo -e "\n${B}═══ $* ═══${NC}"; }

step "1/2 · Backup"
BK="_backup_dd_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BK/roles"
cp roles/views.py "$BK/roles/"
echo "$BK" > .last_backup_dd
echo -e "${G}[✔]${NC} backup: $BK"

step "2/2 · Fix dropdown comerciales/clientes"
python3 << 'PYEOF'
from pathlib import Path
import re

p = Path("/home/LottoBooM/roles/views.py")
src = p.read_text(encoding="utf-8")
original = src
cambios = 0

# ─── Fix 1: clientes_sel con fondos__isnull=False → excluir banco/comercial/superadmin
patron1 = re.compile(
    r"clientes_sel\s*=\s*User\.objects\.filter\(\s*\n?\s*fondos__isnull=False,\s*is_active=True\s*\n?\s*\)\.distinct\(\)\.order_by\('username'\)",
    re.DOTALL,
)
nuevo1 = (
    "clientes_sel = User.objects.filter(\n"
    "            roles__tipo='cliente', roles__activo=True, is_active=True\n"
    "        ).exclude(\n"
    "            roles__tipo__in=['comercial', 'banco', 'superadmin'],\n"
    "            roles__activo=True\n"
    "        ).distinct().order_by('username')"
)
src, n1 = patron1.subn(nuevo1, src)
cambios += n1
print(f"  Fix 1 (fondos__isnull=False): {n1} ocurrencia(s)")

# ─── Fix 2: clientes_sel con id__in=clientes_ids → asegurar rol cliente
patron2 = re.compile(
    r"clientes_sel\s*=\s*User\.objects\.filter\(id__in=clientes_ids,\s*is_active=True\)\.order_by\('username'\)",
)
nuevo2 = (
    "clientes_sel = User.objects.filter(\n"
    "            id__in=clientes_ids, is_active=True,\n"
    "            roles__tipo='cliente', roles__activo=True,\n"
    "        ).exclude(\n"
    "            roles__tipo__in=['comercial', 'banco', 'superadmin'],\n"
    "            roles__activo=True\n"
    "        ).distinct().order_by('username')"
)
src, n2 = patron2.subn(nuevo2, src)
cambios += n2
print(f"  Fix 2 (id__in=clientes_ids): {n2} ocurrencia(s)")

# ─── Fix 3: comerciales_sel → excluir bancos explícitamente
patron3 = re.compile(
    r"comerciales_sel\s*=\s*User\.objects\.filter\(\s*\n?\s*roles__tipo='comercial',\s*roles__activo=True,\s*is_active=True\s*\n?\s*\)\.distinct\(\)\.order_by\('username'\)",
    re.DOTALL,
)
nuevo3 = (
    "comerciales_sel = User.objects.filter(\n"
    "            roles__tipo='comercial', roles__activo=True, is_active=True\n"
    "        ).exclude(\n"
    "            roles__tipo='banco', roles__activo=True\n"
    "        ).distinct().order_by('username')"
)
src, n3 = patron3.subn(nuevo3, src)
cambios += n3
print(f"  Fix 3 (comerciales_sel): {n3} ocurrencia(s)")

# ─── Fix 4: comerciales_sel con id__in → excluir banco
patron4 = re.compile(
    r"comerciales_sel\s*=\s*User\.objects\.filter\(id__in=comerciales_ids,\s*is_active=True\)\.order_by\('username'\)",
)
nuevo4 = (
    "comerciales_sel = User.objects.filter(\n"
    "            id__in=comerciales_ids, is_active=True,\n"
    "            roles__tipo='comercial', roles__activo=True,\n"
    "        ).exclude(\n"
    "            roles__tipo='banco', roles__activo=True\n"
    "        ).distinct().order_by('username')"
)
src, n4 = patron4.subn(nuevo4, src)
cambios += n4
print(f"  Fix 4 (comerciales con id__in): {n4} ocurrencia(s)")

if cambios == 0:
    print("⚠ No se aplicó ningún cambio — quizás ya estaba fixeado")
else:
    p.write_text(src, encoding="utf-8")
    print(f"✔ Total cambios: {cambios}")

import ast
try:
    ast.parse(src)
    print("✔ Sintaxis OK")
except SyntaxError as e:
    print(f"✘ Error línea {e.lineno}: {e.msg}")
    raise SystemExit(1)
PYEOF

python3 manage.py check 2>&1 | tail -3

echo ""
echo -e "${G}🎉 FIX DROPDOWN COMPLETO${NC}"
echo "Backup: $BK"
