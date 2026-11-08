#!/bin/bash
set -e
DB=/home/LottoBooM/db.sqlite3
LOGF=/home/LottoBooM/import_restore.log

{
echo "=== START $(date -Is) ==="
sqlite3 "$DB" <<'SQL'
.timeout 60000
PRAGMA foreign_keys=OFF;
PRAGMA journal_mode=DELETE;
PRAGMA synchronous=NORMAL;

DELETE FROM jugadas_jugada;
DELETE FROM jugadas_boleta;
DELETE FROM resultados_premio;
DELETE FROM resultados_resultado;
DELETE FROM usuarios_perfil;

.read /home/LottoBooM/rebuild/jugadas_boleta.sql
.read /home/LottoBooM/rebuild/jugadas_jugada.sql
.read /home/LottoBooM/rebuild/resultados_resultado.sql
.read /home/LottoBooM/rebuild/resultados_premio.sql
.read /home/LottoBooM/rebuild/usuarios_perfil.sql

PRAGMA foreign_keys=ON;
SQL
echo "=== sqlite3 exit code: $? ==="
echo "=== END $(date -Is) ==="
} >> "$LOGF" 2>&1
