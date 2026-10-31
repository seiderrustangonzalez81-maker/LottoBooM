#!/bin/bash
# force-reload.sh — Fuerza la recarga de todos los usuarios autenticados.
# Uso: bash force-reload.sh

cd "$(dirname "$0")" || exit 1
F=LottoBooM/site_version.txt

if [ ! -f "$F" ]; then
  echo "1" > "$F"
  echo "✅ Archivo creado con versión 1"
else
  V=$(cat "$F")
  V=$((V+1))
  echo "$V" > "$F"
  echo "✅ Versión bump a $V"
fi

echo ""
echo "Los usuarios autenticados recargarán sus páginas en los próximos 45 segundos."
echo "(Los que tengan un modal o formulario activo esperarán al siguiente ciclo.)"
