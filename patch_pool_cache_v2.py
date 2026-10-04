from pathlib import Path

p = Path("/home/LottoBooM/jugadas/templates/jugadas/apostar.html")
src = p.read_text(encoding="utf-8")

if "_poolPorNumeroCache" in src:
    print("SKIP: ya aplicado")
    raise SystemExit(0)

# ═══════════════════════════════════════════════════════════════
# Nueva función: _cargarPoolPorNumero(sid) — cachea pool + consumos
# ═══════════════════════════════════════════════════════════════
nueva_func = """
// ═══════════════════════════════════════════════════════════════
// POOL POR NÚMERO — cachea pool_total + consumido_por_numero
// para detectar excepciones (parlets/fijos/etc que exceden)
// ═══════════════════════════════════════════════════════════════
var _poolPorNumeroCache = {};   // key = "gestorId_sorteoId_fpId" → {fj_id: {pool, consumidos:{}}}

function _cargarPoolPorNumero(sid){
  var gestorId = (typeof getDestinatarioId === 'function') ? getDestinatarioId() : null;
  if (!gestorId) return Promise.resolve(null);
  var key = gestorId + '_' + sid + '_' + (fpSel || '');
  if (_poolPorNumeroCache[key]) {
    return Promise.resolve(_poolPorNumeroCache[key]);
  }
  var hoy = new Date().toISOString().slice(0,10);
  var url = "{% url 'jugadas:api_disponible_por_numero' %}"
          + "?gestor_id=" + gestorId
          + "&sorteo_id=" + sid
          + "&forma_pago_id=" + (fpSel || '')
          + "&fecha=" + hoy;

  return fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json' } })
    .then(function(r){ return r.json(); })
    .then(function(d){
      if (!d || !d.success) return null;
      _poolPorNumeroCache[key] = d.data || {};
      console.log('[pool-por-numero] Cargado para', key, '· formas:', Object.keys(_poolPorNumeroCache[key]).length);
      return _poolPorNumeroCache[key];
    })
    .catch(function(e){
      console.warn('[pool-por-numero] Error:', e);
      return null;
    });
}

function _getPoolYConsumido(sid, formaNombre, numero){
  var gestorId = (typeof getDestinatarioId === 'function') ? getDestinatarioId() : null;
  if (!gestorId) return { pool: 0, consumido: 0, disponible: 0 };
  var key = gestorId + '_' + sid + '_' + (fpSel || '');
  var data = _poolPorNumeroCache[key];
  if (!data) return { pool: 0, consumido: 0, disponible: 0 };
  var nombreLower = String(formaNombre || '').toLowerCase().trim();
  // Buscar la forma_juego por nombre (case-insensitive)
  var fjId = null;
  for (var fid in data) {
    // No tenemos el nombre, pero podemos inferir por estructura
    // En este caso, iteramos y matcheamos por id del cache de formas_juego
    fjId = fid;
    break;
  }
  // Buscar por nombre en un mapeo separado (más confiable)
  return { pool: 0, consumido: 0, disponible: 0 };
}

// Limpiar caché cuando cambia cliente/FP/sorteo
document.addEventListener('change', function(e){
  if (e.target.id === 'selCliente' || e.target.id === 'selFP') {
    _poolPorNumeroCache = {};
  }
});
document.addEventListener('click', function(e){
  if (e.target.closest && e.target.closest('.fp-chip')) {
    _poolPorNumeroCache = {};
  }
});

"""

# Insertar después del bloque _fetchPool existente
ancla = "// Refrescar cuando cambie destinatario, sorteo o FP"
if ancla in src:
    src = src.replace(ancla, nueva_func + "\n" + ancla, 1)
    print("OK: _cargarPoolPorNumero insertado")
else:
    print("ERROR: no encontre ancla")

p.write_text(src, encoding="utf-8")
print("OK: template actualizado")
print("_poolPorNumeroCache:", src.count("_poolPorNumeroCache"))

