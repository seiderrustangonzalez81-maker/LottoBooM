#!/bin/bash
# =====================================================================
# rollback_auditoria.sh — Restaura desde el último backup
# =====================================================================
set -euo pipefail
PROJECT="${PROJECT:-/home/LottoBooM}"
cd "$PROJECT"

R='\033[0;31m'; G='\033[0;32m'; Y='\033[0;33m'; NC='\033[0m'

if [ ! -f ".last_backup_auditoria" ]; then
  echo -e "${R}✘ No hay registro de backup (.last_backup_auditoria)${NC}"
  exit 1
fi

BACKUP=$(cat .last_backup_auditoria)
if [ ! -d "$BACKUP" ]; then
  echo -e "${R}✘ Backup no existe: $BACKUP${NC}"
  exit 1
fi

echo -e "${Y}⚠  Restaurando desde: $BACKUP${NC}"
read -p "¿Confirmas? (s/N): " c
[[ "$c" =~ ^[sS]$ ]] || exit 1

for f in $(cd "$BACKUP" && find . -type f); do
  f="${f#./}"
  cp "$BACKUP/$f" "$PROJECT/$f"
  echo -e "${G}✔${NC} restaurado: $f"
done

echo ""
echo -e "${Y}⚠  Nota: los templates nuevos (historial_movimientos.html, mis_movimientos.html)${NC}"
echo -e "${Y}   NO se borran automáticamente. Para eliminarlos:${NC}"
echo -e "   rm -f $PROJECT/roles/templates/roles/historial_movimientos.html"
echo -e "   rm -f $PROJECT/usuarios/templates/usuarios/mis_movimientos.html"
echo ""
echo -e "${Y}⚠  Para revertir migración (si ya la corriste):${NC}"
echo -e "   python3 manage.py migrate roles <migración_anterior>"
echo -e "   Ejemplo: python3 manage.py migrate roles 00XX"
echo ""
echo -e "${G}✔ Rollback de archivos completado${NC}"
