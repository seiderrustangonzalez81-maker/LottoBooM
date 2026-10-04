#!/bin/bash
set -euo pipefail
PROJECT="/home/LottoBooM"
cd "$PROJECT"

# colores
G='\033[0;32m'; R='\033[0;31m'; Y='\033[0;33m'; B='\033[1;34m'; NC='\033[0m'
log(){ echo -e "${G}[✔]${NC} $*"; }
err(){ echo -e "${R}[✘]${NC} $*" >&2; exit 1; }
step(){ echo -e "\n${B}═══ $* ═══${NC}"; }

# ═══════════════════════════════════════════════════════════════
step "1/7 Backup"
BACKUP_DIR="$PROJECT/_backup_auditoria_$(date +%Y%m%d_%H%M%S)"
FILES=(
  "roles/models.py" "roles/views.py" "roles/utils.py" "roles/urls.py"
  "jugadas/views.py" "usuarios/views.py" "usuarios/urls.py"
  "roles/templates/roles/recarga_directa.html"
)
mkdir -p "$BACKUP_DIR"
for f in "${FILES[@]}"; do
  [ -f "$PROJECT/$f" ] || { echo "  ! no existe: $f"; continue; }
  mkdir -p "$BACKUP_DIR/$(dirname "$f")"
  cp "$PROJECT/$f" "$BACKUP_DIR/$f"
  log "backup $f"
done
echo "$BACKUP_DIR" > "$PROJECT/.last_backup_auditoria"
log "Backup: $BACKUP_DIR"

# ═══════════════════════════════════════════════════════════════
step "2/7 Entorno Python"
[ -d "$PROJECT/venv" ] && source "$PROJECT/venv/bin/activate" && log "venv activado"
python3 --version

# ═══════════════════════════════════════════════════════════════
step "3/7 Aplicando parches Python"

# ──── Escritor #1: modelos + utils + jugadas + roles/usuarios views + urls ────
PATCHER=$(mktemp /tmp/patch_audit_XXXXXX.py)
cat > "$PATCHER" << 'PYEOF'
# -*- coding: utf-8 -*-
import re, sys
from pathlib import Path

BASE = Path(sys.argv[1])
CHANGES = []

def patch(path, skip_marker, fn, label):
    p = BASE / path
    if not p.exists():
        CHANGES.append((path, "ERR", "no existe")); return
    src = p.read_text(encoding="utf-8")
    if skip_marker in src:
        CHANGES.append((path, "SKIP", label + " ya aplicado")); return
    try:
        new = fn(src)
    except Exception as e:
        CHANGES.append((path, "ERR", label + ": " + str(e))); return
    if new == src:
        CHANGES.append((path, "ERR", label + ": anchor no encontrado")); return
    p.write_text(new, encoding="utf-8")
    CHANGES.append((path, "OK", label))

# 1) roles/models.py
def p_models(src):
    old = """        creado_en = models.DateTimeField(auto_now_add=True)
        confirmado_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-creado_en']

    def __str__(self):
        return f"{self.tipo} - {self.monto} - {self.receptor.username}\""""
    new = """        creado_en = models.DateTimeField(auto_now_add=True)
        confirmado_en = models.DateTimeField(null=True, blank=True)

        motivo = models.CharField(max_length=200, blank=True, default='', verbose_name='Motivo / Razon')
        saldo_antes = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, verbose_name='Saldo antes')
        saldo_despues = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, verbose_name='Saldo despues')

    class Meta:
        ordering = ['-creado_en']
        indexes = [
            models.Index(fields=['receptor', '-creado_en']),
            models.Index(fields=['emisor', '-creado_en']),
            models.Index(fields=['tipo', '-creado_en']),
            models.Index(fields=['forma_pago', '-creado_en']),
        ]

    def __str__(self):
        return f"{self.tipo} - {self.monto} - {self.receptor.username}\""""
    if old not in src:
        raise RuntimeError("anchor models.py no encontrado")
    return src.replace(old, new, 1)

patch("roles/models.py", "saldo_antes = models.DecimalField", p_models, "models.py campos")

# 2) jugadas/views.py: cancelacion -> ajuste (simple replace)
def p_jugadas_cancel(src):
    if "tipo='cancelacion'" not in src:
        return src
    return src.replace("tipo='cancelacion'", "tipo='ajuste'")

patch("jugadas/views.py", "tipo='ajuste', estado='confirmado',\n                motivo", p_jugadas_cancel, "jugadas cancelacion->ajuste (o ya aplicado)")

# 3) roles/views.py: import MovimientoFondo
def p_roles_import(src):
    if re.search(r"from \.models import \([^)]*MovimientoFondo", src):
        return src
    m = re.search(r"from \.models import \(([^)]+)\)", src)
    if not m:
        raise RuntimeError("no encontré from .models import ( ... )")
    block = m.group(0)
    # insertar "MovimientoFondo," tras "Fondo,"
    if "Fondo," in block and "MovimientoFondo" not in block:
        new_block = block.replace("Fondo,", "Fondo, MovimientoFondo,", 1)
    elif "\n    Fondo,\n" in block:
        new_block = block.replace("Fondo,", "Fondo, MovimientoFondo,", 1)
    else:
        # anexar antes del cierre
        new_block = block[:-1] + "    MovimientoFondo,\n)"
    return src.replace(block, new_block, 1)

patch("roles/views.py", "MovimientoFondo", p_roles_import, "roles/views import")

# 4) roles/views.py: recarga_directa POST
def p_recarga_directa(src):
    if "tipo_mov == 'ajuste'" in src:
        return src
    # Anchor: encontrar la función y su POST block
    m = re.search(
        r"(def recarga_directa\(request\):.*?)(\n    if request\.method == 'POST':)(.*?)(\n    q = request\.GET\.get\('q')",
        src, re.DOTALL)
    if not m:
        raise RuntimeError("no encontré bloque POST de recarga_directa")
    nuevo = r'''
    if request.method == 'POST':
        usuario_id    = request.POST.get('usuario_id', '').strip()
        monto_str     = request.POST.get('monto', '').strip()
        forma_pago_id = request.POST.get('forma_pago', '').strip()
        tipo_mov      = request.POST.get('tipo_movimiento', 'recarga').strip().lower()

        if tipo_mov not in ('recarga', 'postpago', 'ajuste'):
            messages.error(request, "Tipo invalido.")
            return redirect('roles:recarga_directa')
        try:
            usuario = User.objects.get(id=usuario_id, is_active=True)
        except User.DoesNotExist:
            messages.error(request, "Usuario no valido.")
            return redirect('roles:recarga_directa')
        try:
            monto = Decimal(monto_str)
            if monto <= 0: raise ValueError()
        except Exception:
            messages.error(request, "Monto invalido.")
            return redirect('roles:recarga_directa')
        try:
            forma_pago = FormaPago.objects.get(id=forma_pago_id, activo=True)
        except Exception:
            messages.error(request, "Forma de pago no valida.")
            return redirect('roles:recarga_directa')

        if tipo_mov == 'ajuste':
            signo  = (request.POST.get('signo') or 'sumar').strip().lower()
            motivo = (request.POST.get('motivo_ajuste') or '').strip()[:200]
            if signo not in ('sumar', 'restar'):
                messages.error(request, "Signo invalido.")
                return redirect('roles:recarga_directa')
            if not motivo:
                messages.error(request, "El motivo del ajuste es obligatorio.")
                return redirect('roles:recarga_directa')

            fondo_qs = Fondo.objects.select_for_update().filter(
                usuario=usuario, forma_pago=forma_pago, activo=True)
            if not es_superadmin:
                fondo_qs = fondo_qs.filter(asignado_por=user)

            with transaction.atomic():
                fondo = fondo_qs.first()
                if not fondo:
                    if not es_superadmin and not Fondo.objects.filter(
                        usuario=usuario, asignado_por=user, activo=True).exists():
                        messages.error(request, "Sin permiso para ajustar este cliente.")
                        return redirect('roles:recarga_directa')
                    fondo = Fondo.objects.create(
                        usuario=usuario, forma_pago=forma_pago,
                        asignado_por=user, monto=Decimal('0.00'), activo=True)

                saldo_antes = fondo.monto or Decimal('0.00')
                delta = monto if signo == 'sumar' else -monto
                fondo.monto = saldo_antes + delta
                fondo.save(update_fields=['monto', 'actualizado_en'])

                MovimientoFondo.objects.create(
                    emisor=user if signo == 'restar' else None,
                    receptor=usuario, forma_pago=forma_pago,
                    monto=delta, tipo='ajuste', estado='confirmado',
                    motivo=motivo,
                    nota=("Ajuste +" if signo == 'sumar' else "Ajuste -") + " " + forma_pago.nombre + ": " + motivo,
                    saldo_antes=saldo_antes, saldo_despues=fondo.monto,
                    datos_transferencia={'ajuste_manual': True, 'signo': signo,
                                         'gestor': user.username, 'gestor_id': user.id},
                )

            crear_notificacion(
                usuario=usuario, tipo='info',
                mensaje="Ajuste " + ("a favor" if signo == 'sumar' else "en contra") + " de $" + str(monto) + " en " + forma_pago.nombre + ". Motivo: " + motivo,
                datos={'monto': float(monto), 'signo': signo, 'forma_pago': forma_pago.nombre,
                       'gestor': user.username, 'saldo_antes': float(saldo_antes),
                       'saldo_despues': float(fondo.monto), 'motivo': motivo},
                prioridad='alta', categoria='financiera')
            messages.success(request, "Ajuste " + ("+" if signo == 'sumar' else "-") + "$" + str(monto) + " a " + usuario.username + ". Nuevo saldo: $" + str(fondo.monto))
            if volver == 'apostar':
                return redirect(reverse('jugadas:apostar') + "?cliente_id=" + str(usuario.id))
            return redirect('roles:recarga_directa')

        if tipo_mov == 'recarga':
            solicitud = SolicitudRecarga.objects.create(
                cliente=usuario, gestor=user, forma_pago=forma_pago, monto=monto,
                estado='pagada', mensaje_cliente="Recarga directa por " + user.username,
                creado_por=user)
            from .utils import _aplicar_ingreso_a_fondo
            monto_neto, descontado = _aplicar_ingreso_a_fondo(
                cliente=usuario, gestor=user, forma_pago=forma_pago, monto=monto)
            msg = user.username + " te recargo $" + str(monto) + " en " + forma_pago.nombre
            if descontado > 0:
                msg += ". Aplicado al postpago: $" + str(descontado) + ". Al fondo: $" + str(monto_neto)
            crear_notificacion(usuario=usuario, tipo='info', mensaje=msg,
                datos={'monto_bruto': float(monto), 'postpago_descontado': float(descontado),
                       'monto_neto': float(monto_neto), 'forma_pago': forma_pago.nombre,
                       'gestor': user.username},
                prioridad='alta', categoria='financiera')
            messages.success(request, "Recarga de $" + str(monto) + " a " + usuario.username)
            if volver == 'apostar':
                return redirect(reverse('jugadas:apostar') + "?cliente_id=" + str(usuario.id) + "&recarga_ok=1")
            return redirect('roles:recarga_directa')

        messages.error(request, "Postpago manual deshabilitado (Fase 1).")
        return redirect('roles:recarga_directa')
'''
    return src[:m.start(2)] + nuevo + src[m.end(3):]

patch("roles/views.py", "tipo_mov == 'ajuste'", p_recarga_directa, "recarga_directa ajuste")

# 5) roles/views.py: historial_movimientos (append al final)
def p_historial(src):
    if "def historial_movimientos(" in src:
        return src
    fn = '''

# ═══════════════════════════════════════════════════════════════
# HISTORIAL DE MOVIMIENTOS DE FONDO
# ═══════════════════════════════════════════════════════════════
@login_required
def historial_movimientos(request):
    user = request.user
    es_superadmin = user.is_superuser or user.roles.filter(tipo='superadmin', activo=True).exists()
    es_banco      = user.roles.filter(tipo='banco', activo=True).exists()
    es_comercial  = user.roles.filter(tipo='comercial', activo=True).exists()
    if not (es_superadmin or es_banco or es_comercial):
        messages.error(request, "Sin permisos.")
        return redirect('publico:home')
    qs = MovimientoFondo.objects.select_related('emisor', 'receptor', 'forma_pago')
    if es_superadmin:
        pass
    elif es_banco:
        comerciales_ids = list(Subordinacion.objects.filter(jefe=user, activo=True).values_list('subordinado_id', flat=True))
        clientes_ids = list(Fondo.objects.filter(Q(asignado_por__in=comerciales_ids) | Q(asignado_por=user), activo=True).values_list('usuario_id', flat=True).distinct())
        qs = qs.filter(Q(receptor_id__in=clientes_ids) | Q(emisor_id__in=clientes_ids))
    else:
        clientes_ids = list(Fondo.objects.filter(asignado_por=user, activo=True).values_list('usuario_id', flat=True).distinct())
        qs = qs.filter(Q(receptor_id__in=clientes_ids) | Q(emisor_id__in=clientes_ids))
    cliente_id = (request.GET.get('cliente') or '').strip()
    if cliente_id.isdigit():
        qs = qs.filter(Q(receptor_id=cliente_id) | Q(emisor_id=cliente_id))
    comercial_id = (request.GET.get('comercial') or '').strip()
    if comercial_id.isdigit() and (es_superadmin or es_banco):
        qs = qs.filter(emisor_id=comercial_id)
    tipo = (request.GET.get('tipo') or '').strip()
    if tipo:
        qs = qs.filter(tipo=tipo)
    fp_id = (request.GET.get('forma_pago') or '').strip()
    if fp_id.isdigit():
        qs = qs.filter(forma_pago_id=fp_id)
    fd = (request.GET.get('fecha_desde') or '').strip()
    if fd:
        qs = qs.filter(creado_en__date__gte=fd)
    fh = (request.GET.get('fecha_hasta') or '').strip()
    if fh:
        qs = qs.filter(creado_en__date__lte=fh)
    q = (request.GET.get('q') or '').strip()
    if q:
        qs = qs.filter(Q(motivo__icontains=q) | Q(nota__icontains=q))
    agg = qs.aggregate(
        creditos=Sum(Case(When(monto__gt=0, then='monto'), default=0)),
        debitos=Sum(Case(When(monto__lt=0, then='monto'), default=0)),
    )
    total_creditos = agg['creditos'] or Decimal('0.00')
    total_debitos  = agg['debitos']  or Decimal('0.00')
    qs = qs.order_by('-creado_en')
    paginator = Paginator(qs, 30)
    page_obj = paginator.get_page(request.GET.get('page'))
    if es_superadmin:
        clientes_sel = User.objects.filter(fondos__isnull=False, is_active=True).distinct().order_by('username')
        comerciales_sel = User.objects.filter(roles__tipo='comercial', roles__activo=True, is_active=True).distinct().order_by('username')
    elif es_banco:
        clientes_sel = User.objects.filter(id__in=clientes_ids, is_active=True).order_by('username')
        comerciales_sel = User.objects.filter(id__in=comerciales_ids, is_active=True).order_by('username')
    else:
        clientes_sel = User.objects.filter(id__in=clientes_ids, is_active=True).order_by('username')
        comerciales_sel = User.objects.none()
    return render(request, 'roles/historial_movimientos.html', {
        'page_obj': page_obj,
        'total_creditos': total_creditos, 'total_debitos': total_debitos,
        'neto': total_creditos + total_debitos,
        'clientes_sel': clientes_sel, 'comerciales_sel': comerciales_sel,
        'formas_pago': FormaPago.objects.filter(activo=True).order_by('nombre'),
        'tipos': MovimientoFondo.TIPOS,
        'es_superadmin': es_superadmin, 'es_banco': es_banco, 'es_comercial': es_comercial,
        'filtros': {'cliente': cliente_id, 'comercial': comercial_id,
                    'tipo': tipo, 'forma_pago': fp_id,
                    'fecha_desde': fd, 'fecha_hasta': fh, 'q': q},
    })
'''
    return src + fn

patch("roles/views.py", "def historial_movimientos(", p_historial, "historial_movimientos")

# 6) usuarios/views.py: mis_movimientos
def p_usuarios(src):
    if "def mis_movimientos(" in src:
        return src
    if "Case, When" not in src:
        src = src.replace("from django.db.models import Sum, Q", "from django.db.models import Sum, Q, Case, When", 1)
    fn = '''

@login_required
def mis_movimientos(request):
    from django.core.paginator import Paginator
    qs = MovimientoFondo.objects.filter(
        Q(receptor=request.user) | Q(emisor=request.user)
    ).select_related('emisor', 'receptor', 'forma_pago').order_by('-creado_en')
    tipo = (request.GET.get('tipo') or '').strip()
    if tipo: qs = qs.filter(tipo=tipo)
    fp_id = (request.GET.get('forma_pago') or '').strip()
    if fp_id.isdigit(): qs = qs.filter(forma_pago_id=fp_id)
    fd = (request.GET.get('fecha_desde') or '').strip()
    if fd: qs = qs.filter(creado_en__date__gte=fd)
    fh = (request.GET.get('fecha_hasta') or '').strip()
    if fh: qs = qs.filter(creado_en__date__lte=fh)
    agg = qs.aggregate(
        creditos=Sum(Case(When(monto__gt=0, then='monto'), default=0)),
        debitos=Sum(Case(When(monto__lt=0, then='monto'), default=0)),
    )
    total_creditos = agg['creditos'] or Decimal('0.00')
    total_debitos  = agg['debitos']  or Decimal('0.00')
    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'usuarios/mis_movimientos.html', {
        'page_obj': page_obj,
        'total_creditos': total_creditos, 'total_debitos': total_debitos,
        'neto': total_creditos + total_debitos,
        'clientes_sel': User.objects.none(), 'comerciales_sel': User.objects.none(),
        'formas_pago': FormaPago.objects.filter(activo=True).order_by('nombre'),
        'tipos': MovimientoFondo.TIPOS,
        'es_superadmin': False, 'es_banco': False, 'es_comercial': False,
        'filtros': {'tipo': tipo, 'forma_pago': fp_id, 'fecha_desde': fd, 'fecha_hasta': fh,
                    'cliente': '', 'comercial': '', 'q': ''},
    })
'''
    return src + fn

patch("usuarios/views.py", "def mis_movimientos(", p_usuarios, "mis_movimientos")

# 7) URLs
def p_urls(path, marker, line):
    p = BASE / path
    if not p.exists():
        CHANGES.append((path, "ERR", "no existe")); return
    src = p.read_text(encoding="utf-8")
    if marker in src:
        CHANGES.append((path, "SKIP", "url ya existe")); return
    m = re.search(r"urlpatterns\s*=\s*\[", src)
    if not m:
        CHANGES.append((path, "ERR", "no urlpatterns")); return
    src = src[:m.end()] + "\n    " + line + src[m.end():]
    p.write_text(src, encoding="utf-8")
    CHANGES.append((path, "OK", "url anadida"))

p_urls("roles/urls.py", "historial_movimientos",
       "path('historial-movimientos/', views.historial_movimientos, name='historial_movimientos'),")
p_urls("usuarios/urls.py", "mis_movimientos",
       "path('mis-movimientos/', views.mis_movimientos, name='mis_movimientos'),")

# Reporte
print("")
print("--- REPORTE ---")
fails = 0
for path, status, msg in CHANGES:
    print("  [" + status + "] " + path + " -> " + msg)
    if status == "ERR":
        fails += 1
sys.exit(1 if fails else 0)
PYEOF

python3 "$PATCHER" "$PROJECT"
RC=$?
rm -f "$PATCHER"
[ $RC -eq 0 ] || err "Parches fallaron. Revisa el reporte. Rollback: bash rollback_auditoria.sh"

log "Parches aplicados correctamente"

# ═══════════════════════════════════════════════════════════════
step "4/7 Templates"

TPL_DIR="$PROJECT/roles/templates/roles"
mkdir -p "$TPL_DIR"

cat > "$TPL_DIR/historial_movimientos.html" << 'TPLEOF'
{% extends "base.html" %}
{% load static %}
{% block page_title %}Historial de Movimientos{% endblock %}
{% block extra_css %}
<style>
.page-wrapper{background:#f0fdf4;min-height:100vh;padding-bottom:40px;}
.hdr{background:rgba(255,255,255,.85);border-radius:16px;padding:22px 26px;margin-bottom:20px;box-shadow:0 8px 32px rgba(16,185,129,.10);}
.hdr h1{font-size:1.5rem;font-weight:800;color:#064E3B;margin:0;}
.filtros{background:rgba(255,255,255,.85);border-radius:16px;padding:18px 20px;margin-bottom:18px;box-shadow:0 8px 32px rgba(16,185,129,.10);}
.filtros .row{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px;}
.filtros label{font-size:.7rem;font-weight:800;color:#065F46;text-transform:uppercase;display:block;margin-bottom:3px;}
.filtros input,.filtros select{width:100%;padding:8px 10px;border:1.5px solid #b6e5c2;border-radius:8px;font-size:.82rem;font-weight:600;color:#064E3B;background:#fff;}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px;margin-bottom:18px;}
.kpi{background:linear-gradient(145deg,#fff,#f4fbf6);border:1.5px solid #c8ead4;border-radius:12px;padding:14px 16px;box-shadow:3px 3px 0 #a7e8b8;}
.kpi .lbl{font-size:.65rem;font-weight:800;color:#065F46;text-transform:uppercase;}
.kpi .val{font-size:1.15rem;font-weight:900;color:#064E3B;margin-top:4px;}
.kpi .val.c{color:#047857;} .kpi .val.d{color:#b91c1c;} .kpi .val.n{color:#0369a1;}
.tabla{background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 8px 32px rgba(16,185,129,.10);}
.tabla table{width:100%;border-collapse:collapse;font-size:.8rem;}
.tabla th{background:linear-gradient(180deg,#f0fdf4,#ecfdf5);padding:12px 10px;text-align:left;font-size:.62rem;text-transform:uppercase;color:#065F46;font-weight:800;}
.tabla td{padding:10px;border-bottom:1px solid #ecfdf5;}
.chip{display:inline-block;padding:2px 10px;border-radius:20px;font-size:.62rem;font-weight:800;text-transform:uppercase;}
.chip.recarga{background:#d1fae5;color:#065F46;}
.chip.apuesta{background:#fee2e2;color:#991B1B;}
.chip.premio{background:#fef3c7;color:#92400E;}
.chip.ajuste{background:#e0e7ff;color:#3730A3;}
.chip.retiro{background:#fce7f3;color:#9d174d;}
.chip.postpago,.chip.pago_deuda{background:#fef2f2;color:#7f1d1d;}
.chip.comision{background:#f3e8ff;color:#6b21a8;}
.monto{font-weight:900;font-family:'Courier New',monospace;}
.monto.cred{color:#047857;} .monto.deb{color:#b91c1c;}
.hora{font-size:.68rem;color:#6B7280;font-weight:600;}
.empty{padding:60px 20px;text-align:center;color:#6B7280;}
.pag{display:flex;justify-content:center;gap:8px;margin-top:20px;}
.pag a,.pag span{padding:8px 14px;border-radius:10px;background:#fff;border:1.5px solid #b6e5c2;font-weight:700;color:#064E3B;text-decoration:none;}
.pag .cur{background:#10B981;color:#fff;}
</style>
{% endblock %}
{% block content %}
<div class="page-wrapper container-fluid py-3">
  <div class="hdr">
    <h1>Historial de Movimientos de Fondo</h1>
    <p class="mb-0" style="color:#374151;font-size:.9rem;margin-top:6px;">Todos los movimientos con fecha, hora y motivo.</p>
  </div>
  <div class="kpis">
    <div class="kpi"><div class="lbl">Creditos</div><div class="val c">+${{ total_creditos|floatformat:2 }}</div></div>
    <div class="kpi"><div class="lbl">Debitos</div><div class="val d">${{ total_debitos|floatformat:2 }}</div></div>
    <div class="kpi"><div class="lbl">Neto</div><div class="val n">${{ neto|floatformat:2 }}</div></div>
    <div class="kpi"><div class="lbl">Movimientos</div><div class="val">{{ page_obj.paginator.count }}</div></div>
  </div>
  <form method="get" class="filtros">
    <div class="row">
      {% if es_superadmin or es_banco %}
      <div><label>Comercial</label>
        <select name="comercial" onchange="this.form.submit()">
          <option value="">Todos</option>
          {% for c in comerciales_sel %}<option value="{{ c.id }}" {% if filtros.comercial == c.id|stringformat:'s' %}selected{% endif %}>{{ c.username }}</option>{% endfor %}
        </select>
      </div>{% endif %}
      <div><label>Cliente</label>
        <select name="cliente" onchange="this.form.submit()">
          <option value="">Todos</option>
          {% for c in clientes_sel %}<option value="{{ c.id }}" {% if filtros.cliente == c.id|stringformat:'s' %}selected{% endif %}>{{ c.username }}</option>{% endfor %}
        </select>
      </div>
      <div><label>Tipo</label>
        <select name="tipo" onchange="this.form.submit()">
          <option value="">Todos</option>
          {% for t, lbl in tipos %}<option value="{{ t }}" {% if filtros.tipo == t %}selected{% endif %}>{{ lbl }}</option>{% endfor %}
        </select>
      </div>
      <div><label>Forma de pago</label>
        <select name="forma_pago" onchange="this.form.submit()">
          <option value="">Todas</option>
          {% for fp in formas_pago %}<option value="{{ fp.id }}" {% if filtros.forma_pago == fp.id|stringformat:'s' %}selected{% endif %}>{{ fp.nombre }}</option>{% endfor %}
        </select>
      </div>
      <div><label>Desde</label><input type="date" name="fecha_desde" value="{{ filtros.fecha_desde }}" onchange="this.form.submit()"></div>
      <div><label>Hasta</label><input type="date" name="fecha_hasta" value="{{ filtros.fecha_hasta }}" onchange="this.form.submit()"></div>
      <div><label>Buscar motivo</label><input type="text" name="q" value="{{ filtros.q }}" onchange="this.form.submit()"></div>
    </div>
    <div style="margin-top:12px;text-align:right;"><a href="?">Limpiar</a></div>
  </form>
  <div class="tabla"><div style="overflow-x:auto;">
    <table>
      <thead><tr><th>Fecha / Hora</th><th>Tipo</th><th>Cliente</th><th>Forma de pago</th><th>Monto</th><th>Motivo</th><th>Gestor</th></tr></thead>
      <tbody>
      {% for m in page_obj %}
      <tr>
        <td><div style="font-weight:800;color:#064E3B;">{{ m.creado_en|date:'d/m/Y' }}</div><div class="hora">{{ m.creado_en|date:'H:i:s' }}</div></td>
        <td><span class="chip {{ m.tipo }}">{{ m.get_tipo_display }}</span></td>
        <td><strong>{{ m.receptor.username }}</strong></td>
        <td>{{ m.forma_pago.nombre|default:"-" }}</td>
        <td>
          <span class="monto {% if m.monto >= 0 %}cred{% else %}deb{% endif %}">
            {% if m.monto >= 0 %}+{% endif %}${{ m.monto|floatformat:2 }}</span>
          {% if m.saldo_antes is not None %}<div class="hora">${{ m.saldo_antes|floatformat:2 }} -> ${{ m.saldo_despues|floatformat:2 }}</div>{% endif %}
        </td>
        <td>{{ m.motivo|default:m.nota|default:"-"|truncatechars:60 }}</td>
        <td>{{ m.emisor.username|default:"-" }}</td>
      </tr>
      {% empty %}
      <tr><td colspan="7"><div class="empty">Sin movimientos.</div></td></tr>
      {% endfor %}
      </tbody>
    </table>
  </div></div>
  {% if page_obj.has_other_pages %}
  <div class="pag">
    {% if page_obj.has_previous %}<a href="?page={{ page_obj.previous_page_number }}">Anterior</a>{% endif %}
    <span class="cur">{{ page_obj.number }} / {{ page_obj.paginator.num_pages }}</span>
    {% if page_obj.has_next %}<a href="?page={{ page_obj.next_page_number }}">Siguiente</a>{% endif %}
  </div>
  {% endif %}
</div>
{% endblock %}
TPLEOF
log "creado roles/templates/roles/historial_movimientos.html"

mkdir -p "$PROJECT/usuarios/templates/usuarios"
cat > "$PROJECT/usuarios/templates/usuarios/mis_movimientos.html" << 'TPLEOF'
{% extends "roles/historial_movimientos.html" %}
TPLEOF
log "creado usuarios/templates/usuarios/mis_movimientos.html"

# ═══════════════════════════════════════════════════════════════
step "5/7 Migraciones"
python3 manage.py makemigrations roles --name add_motivo_saldos_movimientofondo 2>&1 | tail -5
python3 manage.py migrate roles 2>&1 | tail -5

# ═══════════════════════════════════════════════════════════════
step "6/7 Verificacion"
python3 manage.py shell << 'PYEOF'
# -*- coding: utf-8 -*-
from roles.models import MovimientoFondo
from django.urls import reverse
campos = [f.name for f in MovimientoFondo._meta.get_fields()]
faltan = [c for c in ('motivo', 'saldo_antes', 'saldo_despues') if c not in campos]
if faltan:
    print("FALTAN:", faltan); exit(1)
print("OK campos:", [c for c in campos if 'motivo' in c or 'saldo' in c])
try:
    print("OK url:", reverse('roles:historial_movimientos'))
    print("OK url:", reverse('usuarios:mis_movimientos'))
except Exception as e:
    print("ERR urls:", e); exit(1)
PYEOF

# ═══════════════════════════════════════════════════════════════
step "7/7 Resumen"
cat << 'EOF'

LISTO. Proximos pasos manuales:
1. Anade enlaces al sidebar (base.html):
   <a href="{% url 'roles:historial_movimientos' %}">Historial movimientos</a>
   <a href="{% url 'usuarios:mis_movimientos' %}">Mis movimientos</a>

2. Prueba:
   - /roles/recarga-directa/?usuario_id=X  -> veras tab Ajuste
   - /roles/historial-movimientos/  -> historial con filtros
EOF
