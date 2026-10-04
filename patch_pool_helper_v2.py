from pathlib import Path
import re

p = Path("/home/LottoBooM/jugadas/templates/jugadas/apostar.html")
src = p.read_text(encoding="utf-8")

if "// POOL_HELPER_V2" in src:
    print("SKIP: ya aplicado")
    raise SystemExit(0)

# Buscar la versión actual de _getPoolYConsumido (la que tiene bugs)
patron = re.compile(
    r"function _getPoolYConsumido\(sid, formaNombre, numero\)\{.*?\n\}\n",
    re.DOTALL,
)

nueva_func = """function _getPoolYConsumido(sid, formaNombre, numero){
  // POOL_HELPER_V2: matchea por forma_nombre en el cache
  var gestorId = (typeof getDestinatarioId === 'function') ? getDestinatarioId() : null;
  if (!gestorId) return { pool: 0, consumido: 0, disponible: 0 };
  var key = gestorId + '_' + sid + '_' + (fpSel || '');
  var data = _poolPorNumeroCache[key];
  if (!data) return { pool: 0, consumido: 0, disponible: 0 };

  var nombreLower = String(formaNombre || '').toLowerCase().trim();
  // Buscar por nombre (case-insensitive) en las formas cacheadas
  for (var fjId in data) {
    var info = data[fjId];
    var infoNombre = String(info.forma_nombre || '').toLowerCase().trim();
    if (infoNombre === nombreLower) {
      var pool = parseFloat(info.pool_total) || 0;
      var numNorm = String(numero || '').toUpperCase().trim();
      var consumidos = info.consumido_por_numero || {};
      // Buscar consumo exacto (case-insensitive)
      var consumido = 0;
      for (var cNum in consumidos) {
        if (String(cNum).toUpperCase() === numNorm) {
          consumido = parseFloat(consumidos[cNum]) || 0;
          break;
        }
      }
      return {
        pool: pool,
        consumido: consumido,
        disponible: Math.max(0, pool - consumido)
      };
    }
  }
  return { pool: 0, consumido: 0, disponible: 0 };
}
"""

src_new, n = patron.subn(nueva_func, src, count=1)
if n == 0:
    print("ERROR: no encontre _getPoolYConsumido")
    # Ver si existe
    if "function _getPoolYConsumido" in src:
        print("  Existe pero no matchea — pégame el bloque")
    raise SystemExit(1)

src = src_new
p.write_text(src, encoding="utf-8")
print("OK: _getPoolYConsumido reescrito")
print("_getPoolYConsumido:", src.count("_getPoolYConsumido"))
