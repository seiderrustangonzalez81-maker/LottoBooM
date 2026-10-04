from pathlib import Path

p = Path("/home/LottoBooM/jugadas/templates/jugadas/apostar.html")
src = p.read_text(encoding="utf-8")

if "api_limites_gestor' %}?gestor_id=\" + gestorId + \"&sorteo_id=\" + sid" in src and "_poolCache[key] = pools" in src:
    print("SKIP: ya aplicado")
    raise SystemExit(0)

# Cambiar el fetch del _fetchPool
viejo = """        fetch("{% url 'roles:api_pool_gestor' %}?gestor_id=" + gestorId + "&sorteo_id=" + sid + "&forma_pago_id=" + fpId, {
            headers: { 'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json' }
        })
        .then(function(r){ return r.json(); })
        .then(function(d){
            if (d && d.success) _poolCache[key] = d.pools || {};
        })
        .catch(function(){});"""

nuevo = """        fetch("{% url 'roles:api_limites_gestor' %}?gestor_id=" + gestorId + "&sorteo_id=" + sid, {
            headers: { 'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json' }
        })
        .then(function(r){ return r.json(); })
        .then(function(d){
            if (d && d.success){
                var pools = {};
                (d.formas || []).forEach(function(f){
                    var k = String(f.forma || '').toLowerCase().trim();
                    // El backend ya devuelve 'limite' = pool (limite + sobrelimite aplicados)
                    pools[k] = parseFloat(f.limite || 0);
                });
                _poolCache[key] = pools;
                console.log('[pool] Cargado para', key, pools);
            }
        })
        .catch(function(e){ console.warn('[pool] Error:', e); });"""

if viejo not in src:
    print("ERROR: no encontre el fetch actual")
    raise SystemExit(1)

src = src.replace(viejo, nuevo, 1)
p.write_text(src, encoding="utf-8")
print("OK: fetch cambiado a api_limites_gestor")
print("api_limites_gestor en apostar.html:", src.count("api_limites_gestor"))
