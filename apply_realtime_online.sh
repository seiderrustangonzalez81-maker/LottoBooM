#!/bin/bash
set -euo pipefail
PROJECT="${PROJECT:-/home/LottoBooM}"
cd "$PROJECT"

G='\033[0;32m'; R='\033[0;31m'; Y='\033[0;33m'; B='\033[1;34m'; NC='\033[0m'
log(){ echo -e "${G}[✔]${NC} $*"; }
warn(){ echo -e "${Y}[!]${NC} $*"; }
err(){ echo -e "${R}[✘]${NC} $*"; exit 1; }
step(){ echo -e "\n${B}═══ $* ═══${NC}"; }

# ═══════════════════════════════════════════════════════════════
step "1/10 · Backup"
# ═══════════════════════════════════════════════════════════════
BK="_backup_realtime_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BK"
FILES=(
  "roles/models.py"
  "roles/views.py"
  "roles/urls.py"
  "roles/utils.py"
  "LottoBooM/settings.py"
  "roles/templates/roles/lista_clientes.html"
  "roles/templates/roles/recarga_directa.html"
)
for f in "${FILES[@]}"; do
  if [ -f "$PROJECT/$f" ]; then
    mkdir -p "$BK/$(dirname "$f")"
    cp "$PROJECT/$f" "$BK/$f"
    log "bk $f"
  else
    warn "no existe: $f (se omite)"
  fi
done
echo "$BK" > .last_backup_realtime
log "Backup: $BK"

# ═══════════════════════════════════════════════════════════════
step "2/10 · Modelo UserActivity"
# ═══════════════════════════════════════════════════════════════
python3 << 'PYEOF'
from pathlib import Path
p = Path("/home/LottoBooM/roles/models.py")
src = p.read_text(encoding="utf-8")
if "class UserActivity" in src:
    print("○ UserActivity ya existe")
else:
    src += '''

# ═══════════════════════════════════════════════════════════════
# REALTIME_ONLINE_V1 · Actividad del usuario (para "en línea")
# ═══════════════════════════════════════════════════════════════
class UserActivity(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='activity'
    )
    last_activity = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        verbose_name = 'Actividad de usuario'
        verbose_name_plural = 'Actividades de usuario'
        indexes = [models.Index(fields=['-last_activity'])]

    def __str__(self):
        return f"{self.user.username} · {self.last_activity:%Y-%m-%d %H:%M:%S}"
'''
    p.write_text(src, encoding="utf-8")
    print("✔ UserActivity añadido a roles/models.py")
PYEOF

# ═══════════════════════════════════════════════════════════════
step "3/10 · Middleware"
# ═══════════════════════════════════════════════════════════════
cat > "$PROJECT/roles/middleware.py" << 'MW_EOF'
# -*- coding: utf-8 -*-
"""
REALTIME_ONLINE_V1 · Middleware que actualiza la actividad del usuario
en cada request autenticado. Permite calcular "en línea" con precisión.
"""
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin


class UserActivityMiddleware(MiddlewareMixin):
    """Actualiza UserActivity.last_activity en cada request autenticado."""

    def process_request(self, request):
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return None
        try:
            from roles.models import UserActivity
            UserActivity.objects.update_or_create(
                user=user,
                defaults={"last_activity": timezone.now()},
            )
        except Exception:
            # Nunca romper el request por culpa de la actividad
            pass
        return None
MW_EOF
log "roles/middleware.py creado"

# ═══════════════════════════════════════════════════════════════
step "4/10 · settings.py — registrar middleware"
# ═══════════════════════════════════════════════════════════════
python3 << 'PYEOF'
from pathlib import Path
import re

p = Path("/home/LottoBooM/LottoBooM/settings.py")
if not p.exists():
    # Buscar settings.py en otras rutas
    for cand in Path("/home/LottoBooM").glob("*/settings.py"):
        if "venv" not in str(cand):
            p = cand
            break

src = p.read_text(encoding="utf-8")
if "roles.middleware.UserActivityMiddleware" in src:
    print(f"○ ya registrado en {p}")
    raise SystemExit(0)

# Insertar después de AuthenticationMiddleware
patron = re.compile(
    r"([ \t]*['\"]django\.contrib\.auth\.middleware\.AuthenticationMiddleware['\"],?\n)",
    re.MULTILINE,
)
m = patron.search(src)
if not m:
    print("✘ No encontré AuthenticationMiddleware en settings.py")
    raise SystemExit(1)

insert = m.group(1) + "    'roles.middleware.UserActivityMiddleware',\n"
src = src[:m.start()] + insert + src[m.end():]
p.write_text(src, encoding="utf-8")
print(f"✔ middleware registrado en {p}")
PYEOF

# ═══════════════════════════════════════════════════════════════
step "5/10 · Helpers en roles/utils.py"
# ═══════════════════════════════════════════════════════════════
python3 << 'PYEOF'
from pathlib import Path
p = Path("/home/LottoBooM/roles/utils.py")
src = p.read_text(encoding="utf-8")
if "def get_online_ids(" in src:
    print("○ helpers ya presentes")
else:
    src += '''

# ═══════════════════════════════════════════════════════════════
# REALTIME_ONLINE_V1 · Helpers "en línea"
# ═══════════════════════════════════════════════════════════════
VENTANA_ONLINE_MINUTOS = 2


def esta_online(user):
    """True si el user tuvo actividad en los últimos N minutos."""
    if not user or not getattr(user, "is_authenticated", False):
        return False
    from datetime import timedelta
    from django.utils import timezone
    from roles.models import UserActivity
    try:
        act = UserActivity.objects.filter(user=user).values_list("last_activity", flat=True).first()
    except Exception:
        return False
    if not act:
        return False
    return act >= timezone.now() - timedelta(minutes=VENTANA_ONLINE_MINUTOS)


def get_online_ids(user_ids=None):
    """Set de IDs de users en línea, opcionalmente filtrado por lista."""
    from datetime import timedelta
    from django.utils import timezone
    from roles.models import UserActivity
    qs = UserActivity.objects.filter(
        last_activity__gte=timezone.now() - timedelta(minutes=VENTANA_ONLINE_MINUTOS)
    )
    if user_ids is not None:
        qs = qs.filter(user_id__in=list(user_ids))
    return set(qs.values_list("user_id", flat=True))
'''
    p.write_text(src, encoding="utf-8")
    print("✔ helpers añadidos a roles/utils.py")
PYEOF

# ═══════════════════════════════════════════════════════════════
step "6/10 · Endpoints JSON en roles/views.py"
# ═══════════════════════════════════════════════════════════════
python3 << 'PYEOF'
from pathlib import Path
import re

p = Path("/home/LottoBooM/roles/views.py")
src = p.read_text(encoding="utf-8")

if "def api_saldos_clientes" in src:
    print("○ endpoints ya presentes")
    raise SystemExit(0)

nuevo = '''

# ═══════════════════════════════════════════════════════════════
# REALTIME_ONLINE_V1 · Endpoints para polling
# ═══════════════════════════════════════════════════════════════
@login_required
def api_saldos_clientes(request):
    """Devuelve saldo + online de un set de IDs. Query: ?ids[]=1&ids[]=2"""
    from django.db.models import Sum
    from roles.utils import get_online_ids

    ids = request.GET.getlist("ids[]") or request.GET.getlist("ids")
    if not ids:
        return JsonResponse({"success": False, "error": "Faltan ids"}, status=400)

    try:
        ids = [int(i) for i in ids][:200]
    except (ValueError, TypeError):
        return JsonResponse({"success": False, "error": "IDs inválidos"}, status=400)

    user = request.user
    es_superadmin = user.is_superuser or user.roles.filter(tipo="superadmin", activo=True).exists()
    if not es_superadmin:
        permitidos = set(Fondo.objects.filter(
            asignado_por=user, activo=True
        ).values_list("usuario_id", flat=True))
        ids = [i for i in ids if i in permitidos]

    saldos = Fondo.objects.filter(
        usuario_id__in=ids, activo=True
    ).values("usuario_id").annotate(total=Sum("monto"))
    saldo_map = {r["usuario_id"]: float(r["total"] or 0) for r in saldos}

    online = get_online_ids(ids)

    clientes = []
    for u in User.objects.filter(id__in=ids).only("id", "username"):
        clientes.append({
            "id": u.id,
            "username": u.username,
            "saldo": saldo_map.get(u.id, 0.0),
            "online": u.id in online,
        })

    return JsonResponse({
        "success": True,
        "clientes": clientes,
        "server_ts": timezone.now().isoformat(),
    })


@login_required
def api_saldo_cliente(request, cliente_id):
    """Devuelve saldo total + desglose por FP + online de UN cliente."""
    from django.db.models import Sum
    from roles.utils import esta_online

    cliente = get_object_or_404(User, id=cliente_id)
    saldo_total = Fondo.objects.filter(
        usuario=cliente, activo=True
    ).aggregate(t=Sum("monto"))["t"] or 0

    fondos_por_fp = {}
    for f in Fondo.objects.filter(usuario=cliente, activo=True).select_related("forma_pago"):
        fp = f.forma_pago.nombre if f.forma_pago else "Sin FP"
        fondos_por_fp[fp] = float(f.monto or 0)

    return JsonResponse({
        "success": True,
        "cliente_id": cliente.id,
        "username": cliente.username,
        "saldo_total": float(saldo_total),
        "fondos_por_fp": fondos_por_fp,
        "online": esta_online(cliente),
        "server_ts": timezone.now().isoformat(),
    })
'''

src = src.rstrip() + "\n" + nuevo
p.write_text(src, encoding="utf-8")

# Verificar sintaxis
import ast
try:
    ast.parse(src)
    print("✔ endpoints añadidos + sintaxis OK")
except SyntaxError as e:
    print(f"✘ Error línea {e.lineno}: {e.msg}")
    raise SystemExit(1)
PYEOF

# ═══════════════════════════════════════════════════════════════
step "7/10 · URLs"
# ═══════════════════════════════════════════════════════════════
python3 << 'PYEOF'
from pathlib import Path
import re

p = Path("/home/LottoBooM/roles/urls.py")
src = p.read_text(encoding="utf-8")
if "api_saldos_clientes" in src:
    print("○ URLs ya presentes")
    raise SystemExit(0)

m = re.search(r"urlpatterns\s*=\s*\[", src)
if not m:
    print("✘ No encontré urlpatterns")
    raise SystemExit(1)

nuevas = '''
    path('api/saldos-clientes/', views.api_saldos_clientes, name='api_saldos_clientes'),
    path('api/saldo-cliente/<int:cliente_id>/', views.api_saldo_cliente, name='api_saldo_cliente'),
'''
src = src[:m.end()] + nuevas + src[m.end():]
p.write_text(src, encoding="utf-8")
print("✔ 2 URLs añadidas")
PYEOF

# ═══════════════════════════════════════════════════════════════
step "8/10 · JS cliente estático"
# ═══════════════════════════════════════════════════════════════
mkdir -p "$PROJECT/static/js"
cat > "$PROJECT/static/js/realtime.js" << 'JS_EOF'
/* ═══════════════════════════════════════════════════════════════
   REALTIME_ONLINE_V1 · Polling de saldos + estado online
   Uso:
     <tr data-cliente-id="42">
       <td class="cliente-saldo">$0.00</td>
       <td><span class="status-dot"></span></td>
     </tr>
     Realtime.initClientes([...ids], {interval: 4000});
   ═══════════════════════════════════════════════════════════════ */
window.Realtime = (function(){
  'use strict';

  function fetchSaldos(ids){
    var qs = ids.map(function(i){ return 'ids[]=' + encodeURIComponent(i); }).join('&');
    return fetch('/roles/api/saldos-clientes/?' + qs, {credentials:'same-origin'})
      .then(function(r){ return r.ok ? r.json() : null; })
      .catch(function(){ return null; });
  }

  function aplicar(rows, porId){
    var actualizados = 0;
    Object.keys(rows).forEach(function(id){
      var c = porId[id];
      var nodos = rows[id];
      if (!c) return;
      nodos.forEach(function(n){
        var s = n.querySelector('.cliente-saldo, .saldo-valor, [data-saldo]');
        if (s) s.textContent = '$' + (c.saldo || 0).toFixed(2);
        var d = n.querySelector('.status-dot, [data-online]');
        if (d) d.classList.toggle('online', !!c.online);
      });
      actualizados++;
    });
    var el = document.getElementById('realtime-ts');
    if (el) el.textContent = '· ' + new Date().toLocaleTimeString();
    return actualizados;
  }

  function initClientes(ids, opts){
    opts = opts || {};
    var interval = opts.interval || 4000;
    ids = (ids || []).filter(Boolean);
    if (!ids.length) return;

    function tick(){
      fetchSaldos(ids).then(function(d){
        if (!d || !d.success) return;
        var porId = {};
        d.clientes.forEach(function(c){ porId[c.id] = c; });
        var rows = {};
        document.querySelectorAll('[data-cliente-id]').forEach(function(n){
          var id = parseInt(n.dataset.clienteId, 10);
          if (!id) return;
          if (!rows[id]) rows[id] = [];
          rows[id].push(n);
        });
        aplicar(rows, porId);
      });
    }

    tick();
    setInterval(tick, interval);
  }

  function initSaldoUnico(clienteId, opts){
    opts = opts || {};
    var interval = opts.interval || 3000;
    if (!clienteId) return;

    function tick(){
      fetch('/roles/api/saldo-cliente/' + clienteId + '/', {credentials:'same-origin'})
        .then(function(r){ return r.ok ? r.json() : null; })
        .then(function(d){
          if (!d || !d.success) return;
          var s = document.getElementById('srSaldo') || document.querySelector('[data-saldo-cliente]');
          if (s) s.textContent = '$' + (d.saldo_total || 0).toFixed(2);
          var dot = document.getElementById('srDot') || document.querySelector('[data-online-cliente]');
          if (dot) dot.classList.toggle('online', !!d.online);
          var ts = document.getElementById('srTs') || document.getElementById('realtime-ts');
          if (ts) ts.textContent = 'Actualizado ' + new Date().toLocaleTimeString();
          var fps = document.getElementById('srFPs');
          if (fps && d.fondos_por_fp){
            var html = '';
            Object.keys(d.fondos_por_fp).forEach(function(k){
              html += '<span class="fp-chip-mini">' + k + ': $' +
                      (d.fondos_por_fp[k]||0).toFixed(2) + '</span>';
            });
            fps.innerHTML = html;
          }
        })
        .catch(function(){});
    }
    tick();
    setInterval(tick, interval);
  }

  return { initClientes: initClientes, initSaldoUnico: initSaldoUnico };
})();
JS_EOF
log "static/js/realtime.js creado"

# ═══════════════════════════════════════════════════════════════
step "9/10 · Parchear templates con polling"
# ═══════════════════════════════════════════════════════════════
python3 << 'PYEOF'
from pathlib import Path
import re

# ─────────────────────────────────────────────────────────────
# 9a) lista_clientes.html
# ─────────────────────────────────────────────────────────────
p = Path("/home/LottoBooM/roles/templates/roles/lista_clientes.html")
if not p.exists():
    print("⚠ lista_clientes.html no encontrado — se omite")
else:
    src = p.read_text(encoding="utf-8")
    modificado = False

    # Añadir data-cliente-id a cada <tr> si hay un anchor de recarga con usuario_id
    if "data-cliente-id" not in src:
        def add_data(m):
            tr = m.group(0)
            # Buscar usuario_id=N en cualquier url dentro del <tr>
            m2 = re.search(r"usuario_id=(\d+)", tr)
            if not m2:
                return tr
            if 'data-cliente-id=' in tr:
                return tr
            return tr.replace('<tr', f'<tr data-cliente-id="{m2.group(1)}"', 1)

        # Anclaje: bloques <tr>...</tr> que contengan "usuario_id="
        src2 = re.sub(r"<tr[\s\S]*?</tr>", add_data, src)
        if src2 != src:
            src = src2
            modificado = True
            print("  ✔ data-cliente-id añadido a filas")

    # Añadir dot online tras el username
    if "status-dot" not in src:
        # Insertar dot después del primer <strong> con username
        patron_username = re.compile(r"(<strong>[\s\S]{0,80}?</strong>)", re.DOTALL)
        def add_dot(m):
            return m.group(1) + ' <span class="status-dot" title="En línea"></span>'
        src2 = patron_username.sub(add_dot, src, count=1)
        if src2 != src:
            src = src2
            modificado = True
            print("  ✔ status-dot insertado")

    # Añadir KPI online (después de un KPI existente o antes del cierre de .kpis)
    if "kpi-online-realtime" not in src:
        patron_kpi = re.compile(r"(</div>\s*</div>\s*<!--\s*fin kpis|class=\"kpis\"[^>]*>[\s\S]*?)(</div>)", re.DOTALL)
        # Fallback: append al final del bloque .kpis
        m = re.search(r"(<div class=\"kpis\"[^>]*>)([\s\S]*?)(</div>)", src)
        if m:
            nuevo_kpi = (
                '\n      <div class="kpi kpi-online-realtime"><div class="lbl">En línea</div>'
                '<div class="val" id="kpiOnline">—</div></div>\n    '
            )
            src = src[:m.end(2)] + nuevo_kpi + src[m.end(2):]
            modificado = True
            print("  ✔ KPI online añadido")

    # Añadir CSS + script antes de {% endblock %}
    if "realtime.js" not in src:
        css = '''
<style>
.status-dot{display:inline-block;width:9px;height:9px;border-radius:50%;background:#D1D5DB;margin-right:5px;vertical-align:middle;transition:.3s;}
.status-dot.online{background:#10B981;box-shadow:0 0 0 3px rgba(16,185,129,.25);}
[data-cliente-id] .cliente-saldo,[data-cliente-id] .saldo-valor{transition:.3s;}
.realtime-ts{font-size:.65rem;color:#6B7280;font-weight:600;margin-left:6px;}
</style>
'''
        js = '''
<script src="{% static 'js/realtime.js' %}"></script>
<script>
document.addEventListener('DOMContentLoaded', function(){
  if (typeof Realtime === 'undefined') return;
  var ids = [];
  document.querySelectorAll('[data-cliente-id]').forEach(function(n){
    var id = parseInt(n.dataset.clienteId, 10);
    if (id) ids.push(id);
  });
  if (ids.length) {
    Realtime.initClientes(ids, { interval: 4000 });
  }
});
</script>
'''
        # Añadir {% load static %} si falta
        if "{% load static %}" not in src and "{% load static" not in src:
            src = src.replace("{% extends", "{% load static %}\n{% extends", 1)

        # Insertar CSS en extra_css, o al final del head. Fallback: append al inicio del body.
        if "{% block extra_css %}" in src:
            # Insertar al final del bloque extra_css
            m = re.search(r"(\{%\s*block\s+extra_css\s*%\})([\s\S]*?)(\{%\s*endblock\s*%\})", src)
            if m:
                src = src[:m.end(2)] + css + src[m.end(2):]
        else:
            # Sin extra_css: append CSS inline antes del script
            src = css + src

        # Insertar script antes del último endblock
        ultimo = src.rfind("{% endblock %}")
        if ultimo > 0:
            src = src[:ultimo] + js + "\n" + src[ultimo:]
        else:
            src += "\n" + js

        modificado = True
        print("  ✔ CSS + script añadidos")

    if modificado:
        p.write_text(src, encoding="utf-8")
        print(f"✔ {p} actualizado")
    else:
        print("○ lista_clientes.html sin cambios necesarios")

# ─────────────────────────────────────────────────────────────
# 9b) recarga_directa.html — mostrar saldo real + polling
# ─────────────────────────────────────────────────────────────
p2 = Path("/home/LottoBooM/roles/templates/roles/recarga_directa.html")
if not p2.exists():
    print("⚠ recarga_directa.html no encontrado — se omite")
else:
    src = p2.read_text(encoding="utf-8")
    modificado = False

    # Insertar bloque de saldo real si no está
    if "saldoRealBox" not in src and "srSaldo" not in src:
        # Anclaje: después de "locked-panel" opening div
        m = re.search(r"(<div class=\"locked-panel\">)", src)
        if m:
            saldo_box = '''
      <!-- REALTIME_ONLINE_V1 · Saldo real + online -->
      <div class="saldo-real-box" id="saldoRealBox">
        <div style="display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap;">
          <div>
            <div style="font-size:.7rem;font-weight:800;color:#065F46;text-transform:uppercase;letter-spacing:.5px;">Saldo real</div>
            <div style="font-size:1.6rem;font-weight:900;color:#064E3B;font-family:'Courier New',monospace;margin-top:2px;">
              <span id="srSaldo">—</span>
            </div>
            <div style="font-size:.68rem;color:#6B7280;margin-top:2px;">
              <span class="status-dot" id="srDot"></span>
              <span id="srOnlineTxt">Consultando…</span>
              <span id="srTs" class="realtime-ts"></span>
            </div>
          </div>
          <div id="srFPs" style="display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end;"></div>
        </div>
      </div>
'''
            src = src[:m.end(1)] + saldo_box + src[m.end(1):]
            modificado = True
            print("  ✔ bloque saldoRealBox añadido")

    # CSS
    if "saldo-real-box" not in src.split("<style>")[0] and ".saldo-real-box" not in src:
        css2 = '''
.saldo-real-box{background:linear-gradient(135deg,#ecfdf5,#d1fae5);border:2px solid #6ee7b7;border-radius:14px;padding:14px 18px;margin-bottom:14px;box-shadow:0 4px 16px rgba(16,185,129,.15);}
.saldo-real-box .status-dot{width:10px;height:10px;background:#D1D5DB;display:inline-block;border-radius:50%;margin-right:5px;transition:.3s;}
.saldo-real-box .status-dot.online{background:#10B981;box-shadow:0 0 0 3px rgba(16,185,129,.30);}
.realtime-ts{font-size:.65rem;color:#6B7280;font-weight:600;margin-left:6px;}
.fp-chip-mini{background:#fff;border:1.5px solid #86efac;border-radius:8px;padding:4px 10px;font-size:.7rem;font-weight:800;color:#065F46;font-family:'Courier New',monospace;}
'''
        # Añadir al primer <style>
        idx = src.find("</style>")
        if idx > 0:
            src = src[:idx] + css2 + src[idx:]
            modificado = True
            print("  ✔ CSS saldo-real-box añadido")

    # Script polling
    if "initSaldoUnico" not in src:
        js2 = '''
<script src="{% static 'js/realtime.js' %}"></script>
{% if usuario_preseleccionado %}
<script>
document.addEventListener('DOMContentLoaded', function(){
  if (typeof Realtime !== 'undefined') {
    Realtime.initSaldoUnico({{ usuario_preseleccionado.id }}, { interval: 3000 });
  }
});
</script>
{% endif %}
'''
        ultimo = src.rfind("{% endblock %}")
        if ultimo > 0:
            src = src[:ultimo] + js2 + "\n" + src[ultimo:]
        else:
            src += "\n" + js2
        modificado = True
        print("  ✔ script polling añadido")

    # Asegurar {% load static %}
    if "{% load static %}" not in src:
        src = src.replace("{% extends", "{% load static %}\n{% extends", 1)

    if modificado:
        p2.write_text(src, encoding="utf-8")
        print(f"✔ {p2} actualizado")
    else:
        print("○ recarga_directa.html sin cambios necesarios")
PYEOF

# ═══════════════════════════════════════════════════════════════
step "10/10 · Migración + verificación"
# ═══════════════════════════════════════════════════════════════
python3 manage.py makemigrations roles --name add_useractivity_realtime 2>&1 | grep -v "^No changes" || true
python3 manage.py migrate roles

echo ""
python3 manage.py shell << 'PYEOF'
# ─── Verificaciones ───
ok = True

# 1. Modelo
from roles.models import UserActivity
print("✔ UserActivity importable")

# 2. Middleware
from roles.middleware import UserActivityMiddleware
print("✔ Middleware importable")

# 3. Helpers
from roles.utils import esta_online, get_online_ids, VENTANA_ONLINE_MINUTOS
print(f"✔ Helpers OK · ventana={VENTANA_ONLINE_MINUTOS}min")

# 4. Endpoints
from roles.views import api_saldos_clientes, api_saldo_cliente
print("✔ Endpoints importables")

# 5. URLs
from django.urls import reverse
print(f"✔ URL: {reverse('roles:api_saldos_clientes')}")
print(f"✔ URL: {reverse('roles:api_saldo_cliente', args=[1])}")

# 6. Middleware en settings
from django.conf import settings
if 'roles.middleware.UserActivityMiddleware' in settings.MIDDLEWARE:
    print("✔ Middleware registrado en settings")
else:
    print("✘ Middleware NO registrado en settings")
    ok = False

# 7. Archivo JS
from pathlib import Path
if Path('/home/LottoBooM/static/js/realtime.js').exists():
    print("✔ realtime.js en disco")
else:
    print("✘ realtime.js NO existe")
    ok = False

if not ok:
    raise SystemExit(1)
PYEOF

echo ""
echo -e "${G}🎉 REALTIME ONLINE + SALDOS APLICADO${NC}"
echo ""
echo "📂 Backup: $BK"
echo "↩ Rollback:"
echo "   cp -r $BK/* $PROJECT/"
echo "   python3 manage.py migrate roles <migración_anterior>"
echo "   # Eliminar roles/middleware.py y static/js/realtime.js si quieres"
echo ""
echo "🌐 Endpoints nuevos:"
echo "   GET /roles/api/saldos-clientes/?ids[]=1&ids[]=2"
echo "   GET /roles/api/saldo-cliente/<id>/"
echo ""
echo -e "${Y}⚠ PENDIENTES MANUALES:${NC}"
echo "  1. En PA: recargar web (Web → Reload)"
echo "  2. Probar: /roles/lista-clientes/ → ver dots + saldos en vivo"
echo "  3. Probar: /roles/recarga-directa/?usuario_id=X → saldo real"
echo "  4. Añadir a selectores de clientes el data-cliente-id si quieres que actualicen"
