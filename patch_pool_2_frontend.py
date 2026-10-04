from pathlib import Path

p = Path("/home/LottoBooM/jugadas/templates/jugadas/apostar.html")
src = p.read_text(encoding="utf-8")

if "_poolCache" in src:
    print("SKIP: ya aplicado")
    raise SystemExit(0)

# Añadir sistema de caché + fetch al inicio del script (antes de "const ES_CLIENTE")
inyeccion = """
// ═══════════════════════════════════════════════════════════════
// _poolCache: pool por (gestor, sorteo, FP) para capar parlet/candado
// ═══════════════════════════════════════════════════════════════
var _poolCache = {};   // key = "gestorId_sorteoId_fpId" → {parlet: X, pick2: Y, ...}

function _fetchPool() {
    var gestorId = (typeof getDestinatarioId === 'function') ? getDestinatarioId() : null;
    if (!gestorId || !ordenSorteos.length) return;
    var fpId = fpSel || '';
    ordenSorteos.forEach(function(sid){
        var key = gestorId + '_' + sid + '_' + fpId;
        if (_poolCache[key] !== undefined) return;
        fetch("{% url 'roles:api_pool_gestor' %}?gestor_id=" + gestorId + "&sorteo_id=" + sid + "&forma_pago_id=" + fpId, {
            headers: { 'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json' }
        })
        .then(function(r){ return r.json(); })
        .then(function(d){
            if (d && d.success) _poolCache[key] = d.pools || {};
        })
        .catch(function(){});
    });
}

function _getPool(sid, forma) {
    var gestorId = (typeof getDestinatarioId === 'function') ? getDestinatarioId() : null;
    if (!gestorId) return 0;
    var key = gestorId + '_' + sid + '_' + (fpSel || '');
    var p = _poolCache[key];
    if (!p) return 0;
    return p[String(forma).toLowerCase()] || 0;
}

// Refrescar cuando cambie destinatario, sorteo o FP
document.addEventListener('change', function(e){
    if (e.target.id === 'selCliente' || e.target.id === 'selFP' || (e.target.closest && e.target.closest('.fp-chip'))) {
        _poolCache = {};   // limpiar
        setTimeout(_fetchPool, 500);
    }
});

"""

# Insertar antes de "const ES_CLIENTE"
anchor = "const ES_CLIENTE = "
if anchor not in src:
    print("ERROR: no encontre const ES_CLIENTE")
    raise SystemExit(1)
idx = src.find(anchor)
src = src[:idx] + inyeccion + src[idx:]
print("OK: inyeccion de cache")

# Llamar _fetchPool después de cargar config de sorteo
viejo_config = """  fetch("{% url 'jugadas:api_configuracion_sorteo' %}?sorteo_id=" + sid)"""
nuevo_config = """  // Programar fetch del pool
  setTimeout(_fetchPool, 800);
  fetch("{% url 'jugadas:api_configuracion_sorteo' %}?sorteo_id=" + sid)"""

if viejo_config in src:
    src = src.replace(viejo_config, nuevo_config, 1)
    print("OK: llamada fetchPool")

p.write_text(src, encoding="utf-8")
print("OK: template actualizado")
