#!/bin/bash
# =====================================================================
# apply_auditoria.sh — Auditoría de movimientos de fondo
# Idempotente. Hace backup. Verifica antes y después. Rollback listo.
# =====================================================================
set -euo pipefail

PROJECT="${PROJECT:-/home/LottoBooM}"
cd "$PROJECT"

# ─── Colores ───
G='\033[0;32m'; R='\033[0;31m'; Y='\033[0;33m'; B='\033[1;34m'; NC='\033[0m'
log()  { echo -e "${G}[✔]${NC} $*"; }
warn() { echo -e "${Y}[!]${NC} $*"; }
err()  { echo -e "${R}[✘]${NC} $*" >&2; exit 1; }
step() { echo -e "\n${B}══════════════════════════════════════════════════════════${NC}"; \
         echo -e "${B}  $*${NC}"; \
         echo -e "${B}══════════════════════════════════════════════════════════${NC}"; }

# ─────────────────────────────────────────────────────────────────────
step "1/8 · Backup"
# ─────────────────────────────────────────────────────────────────────
BACKUP_DIR="$PROJECT/_backup_auditoria_$(date +%Y%m%d_%H%M%S)"
FILES=(
  "roles/models.py"
  "roles/views.py"
  "roles/utils.py"
  "roles/urls.py"
  "jugadas/views.py"
  "usuarios/views.py"
  "usuarios/urls.py"
  "roles/templates/roles/recarga_directa.html"
)
mkdir -p "$BACKUP_DIR"
for f in "${FILES[@]}"; do
  if [ -f "$PROJECT/$f" ]; then
    mkdir -p "$BACKUP_DIR/$(dirname "$f")"
    cp "$PROJECT/$f" "$BACKUP_DIR/$f"
    log "Backup: $f"
  else
    warn "No existe: $f (se omite)"
  fi
done
echo "$BACKUP_DIR" > "$PROJECT/.last_backup_auditoria"
log "Backup completo en: $BACKUP_DIR"

# ─────────────────────────────────────────────────────────────────────
step "2/8 · Verificación previa"
# ─────────────────────────────────────────────────────────────────────
[ -f "$PROJECT/roles/models.py" ] || err "Falta roles/models.py"
[ -f "$PROJECT/roles/views.py" ] || err "Falta roles/views.py"
[ -f "$PROJECT/jugadas/views.py" ] || err "Falta jugadas/views.py"
grep -q "class MovimientoFondo" "$PROJECT/roles/models.py" || err "No hay MovimientoFondo"
grep -q "class Fondo" "$PROJECT/roles/models.py" || err "No hay Fondo"
grep -q "def recarga_directa" "$PROJECT/roles/views.py" || err "No hay recarga_directa"
log "Estructura mínima OK"

# ─────────────────────────────────────────────────────────────────────
step "3/8 · Activación de entorno Python"
# ─────────────────────────────────────────────────────────────────────
if [ -z "${VIRTUAL_ENV:-}" ]; then
  for v in venv .venv env; do
    if [ -f "$PROJECT/$v/bin/activate" ]; then
      # shellcheck disable=SC1091
      source "$PROJECT/$v/bin/activate"
      log "venv activado: $v"
      break
    fi
  done
fi
python3 --version

# ─────────────────────────────────────────────────────────────────────
step "4/8 · Parcheando archivos Python"
# ─────────────────────────────────────────────────────────────────────
python3 - "$PROJECT" << 'PYEOF'
import re, sys
from pathlib import Path

BASE = Path(sys.argv[1])
CHANGES = []  # (archivo, ok/skip/err, msg)

def patch(path, marker_skip, fn, label):
    """Aplica fn(src) -> new_src. Si marker_skip ya está, salta."""
    p = BASE / path
    if not p.exists():
        CHANGES.append((path, "ERR", f"no existe"))
        return False
    src = p.read_text(encoding="utf-8")
    if marker_skip in src:
        CHANGES.append((path, "SKIP", f"{label} ya aplicado"))
        return True
    try:
        new = fn(src)
    except Exception as e:
        CHANGES.append((path, "ERR", f"{label}: {e}"))
        return False
    if new == src:
        CHANGES.append((path, "ERR", f"{label}: sin cambios (anchor no encontrado)"))
        return False
    p.write_text(new, encoding="utf-8")
    CHANGES.append((path, "OK", label))
    return True


# ═══════════════════════════════════════════════════════════════════
# PATCH 1 — roles/models.py : motivo + saldo_antes + saldo_despues
# ═══════════════════════════════════════════════════════════════════
def patch_models(src):
    old = '''        creado_en = models.DateTimeField(auto_now_add=True)
        confirmado_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-creado_en']

    def __str__(self):
        return f"{self.tipo} - {self.monto} - {self.receptor.username}"'''

    new = '''        creado_en = models.DateTimeField(auto_now_add=True)
        confirmado_en = models.DateTimeField(null=True, blank=True)

        # ═══ NUEVOS · Motivo y snapshot de saldo (auditoría) ═══
        motivo = models.CharField(
            max_length=200, blank=True, default='',
            verbose_name='Motivo / Razón',
            help_text='Explicación corta. Obligatorio en ajustes manuales.',
        )
        saldo_antes = models.DecimalField(
            max_digits=12, decimal_places=2,
            null=True, blank=True,
            verbose_name='Saldo antes del movimiento',
        )
        saldo_despues = models.DecimalField(
            max_digits=12, decimal_places=2,
            null=True, blank=True,
            verbose_name='Saldo después del movimiento',
        )

    class Meta:
        ordering = ['-creado_en']
        indexes = [
            models.Index(fields=['receptor', '-creado_en']),
            models.Index(fields=['emisor', '-creado_en']),
            models.Index(fields=['tipo', '-creado_en']),
            models.Index(fields=['forma_pago', '-creado_en']),
        ]

    def __str__(self):
        return f"{self.tipo} - {self.monto} - {self.receptor.username}"'''

    if old not in src:
        raise RuntimeError("no encontré el bloque final de MovimientoFondo")
    return src.replace(old, new, 1)

patch("roles/models.py", "saldo_antes = models.DecimalField", patch_models, "models.py")


# ═══════════════════════════════════════════════════════════════════
# PATCH 2 — roles/utils.py : _aplicar_ingreso_a_fondo con auditoría
# ═══════════════════════════════════════════════════════════════════
def patch_utils(src):
    # Ancla: inicio y fin de la función
    m = re.search(
        r"def _aplicar_ingreso_a_fondo\(cliente,\s*gestor,\s*forma_pago,\s*monto\):.*?(?=\n\ndef |\n\n#|\Z)",
        src, re.DOTALL,
    )
    if not m:
        raise RuntimeError("no encontré _aplicar_ingreso_a_fondo")

    new_fn = '''def _aplicar_ingreso_a_fondo(cliente, gestor, forma_pago, monto):
    """
    Aplica un ingreso (recarga/premio) al cliente:
    1. Si hay Postpago con saldo < 0 para (gestor, forma_pago), paga la deuda.
    2. El resto va al Fondo.
    3. Registra MovimientoFondo de recarga + pago_deuda (si aplica).
    Devuelve (monto_al_fondo, monto_pagado_postpago).
    """
    from decimal import Decimal
    from django.db import transaction
    from roles.models import Postpago, Fondo, MovimientoFondo

    monto = Decimal(str(monto))
    if monto <= 0:
        return Decimal('0.00'), Decimal('0.00')

    with transaction.atomic():
        fondo_pre = Fondo.objects.filter(
            usuario=cliente, forma_pago=forma_pago, activo=True
        ).first()
        saldo_antes_fondo = fondo_pre.monto if fondo_pre else Decimal('0.00')

        # 1. Postpago (si hay deuda)
        pagado = Decimal('0.00')
        pp = Postpago.objects.select_for_update().filter(
            cliente=cliente, gestor=gestor, forma_pago=forma_pago,
        ).first()
        if pp and pp.saldo < 0:
            deuda = -pp.saldo
            pagado = min(monto, deuda)
            pp.saldo += pagado
            if pp.saldo == 0:
                pp.activo = False
            pp.save(update_fields=['saldo', 'activo', 'actualizado_en'])
            monto -= pagado

            MovimientoFondo.objects.create(
                emisor=gestor, receptor=cliente, forma_pago=forma_pago,
                monto=pagado, tipo='pago_deuda', estado='confirmado',
                motivo=f"Abono a deuda pendiente con {gestor.username}",
                nota=f"${pagado:.2f} abonado desde ingreso",
                datos_transferencia={
                    'postpago_id': pp.id,
                    'gestor': gestor.username,
                    'deuda_restante': float(-pp.saldo) if pp.saldo < 0 else 0.0,
                },
            )

        # 2. Resto al Fondo
        al_fondo = monto
        if al_fondo > 0:
            fondo, _ = Fondo.objects.select_for_update().get_or_create(
                usuario=cliente, forma_pago=forma_pago,
                defaults={'monto': Decimal('0.00'), 'activo': True, 'asignado_por': gestor},
            )
            fondo.monto += al_fondo
            fondo.activo = True
            if not fondo.asignado_por_id and gestor:
                fondo.asignado_por = gestor
            fondo.save(update_fields=['monto', 'activo', 'asignado_por'] if fondo.asignado_por_id else ['monto', 'activo'])

            MovimientoFondo.objects.create(
                emisor=gestor, receptor=cliente, forma_pago=forma_pago,
                monto=al_fondo, tipo='recarga', estado='confirmado',
                motivo=f"Ingreso aplicado a fondo · {gestor.username}",
                nota=(f"Al fondo: ${al_fondo:.2f} (postpago cubierto: ${pagado:.2f})"
                      if pagado > 0 else f"Al fondo: ${al_fondo:.2f}"),
                saldo_antes=saldo_antes_fondo,
                saldo_despues=fondo.monto,
                datos_transferencia={
                    'gestor': gestor.username,
                    'monto_bruto': float(al_fondo + pagado),
                    'postpago_descontado': float(pagado),
                },
            )

        return al_fondo, pagado
'''
    return src[:m.start()] + new_fn + src[m.end():]

patch("roles/utils.py", "'pago_deuda', estado='confirmado'", patch_utils, "utils.py")


# ════════════════════════════════════════════════�
��══════════════════
# PATCH 3 — jugadas/views.py : cancelar → tipo='ajuste' + guardar_apuesta
# ═══════════════════════════════════════════════════════════════════
def patch_jugadas_cancelar(src):
    # Buscar cualquier uso de tipo='cancelacion' dentro del archivo
    if "tipo='cancelacion'" not in src and '"cancelacion"' not in src:
        return src  # nada que hacer, es idempotente
    # Reemplazo directo
    src = src.replace("tipo='cancelacion'", "tipo='ajuste'")
    src = src.replace('"cancelacion"', "'ajuste'")
    return src

def patch_jugadas_import(src):
    # Asegurar import de MovimientoFondo
    if "MovimientoFondo" in src.split("\n\n")[0:10].__str__() or "MovimientoFondo" in src[:2000]:
        return src
    # Insertar tras el primer import de roles.models
    m = re.search(r"from roles\.models import ([^\n]+)", src)
    if m:
        line = m.group(0)
        if "MovimientoFondo" not in line:
            new_line = line.rstrip() + ", MovimientoFondo"
            src = src.replace(line, new_line, 1)
            return src
    # Fallback: agregar import aparte tras el primer import de roles
    if "from roles.models" not in src:
        src = "from roles.models import MovimientoFondo\n" + src
    return src

patch("jugadas/views.py", "tipo='ajuste'", patch_jugadas_cancelar, "jugadas cancelar→ajuste")
patch("jugadas/views.py", "MovimientoFondo", patch_jugadas_import, "jugadas import MovimientoFondo")


# ═══════════════════════════════════════════════════════════════════
# PATCH 4 — roles/views.py : imports + recarga_directa + historial
# ═══════════════════════════════════════════════════════════════════
def patch_roles_import(src):
    if "MovimientoFondo," in src or "MovimientoFondo " in src:
        return src
    # Buscar bloque "from .models import (" y añadir
    m = re.search(r"from \.models import \(([^)]+)\)", src)
    if m:
        block = m.group(0)
        new_block = block.replace("Fondo,", "Fondo, MovimientoFondo,", 1)
        if new_block == block:  # no tenía "Fondo,"
            new_block = block.replace("Fondo\n", "Fondo, MovimientoFondo\n", 1)
        return src.replace(block, new_block, 1)
    # Fallback
    return src.replace(
        "from .models import",
        "from .models import MovimientoFondo\nfrom .models import",
        1,
    )

patch("roles/views.py", "MovimientoFondo", patch_roles_import, "roles/views import MovimientoFondo")


def patch_recarga_directa(src):
    # Ancla: el `if request.method == 'POST':` dentro de recarga_directa
    # Buscamos la función y su POST block hasta el render final
    m = re.search(
        r"(def recarga_directa\(request\):.*?)(\n    if request\.method == 'POST':.*?)(\n    q = request\.GET\.get\('q'|$)",
        src, re.DOTALL,
    )
    if not m:
        raise RuntimeError("no encontré bloque POST de recarga_directa")

    nuevo_post = '''
    if request.method == 'POST':
        usuario_id    = request.POST.get('usuario_id', '').strip()
        monto_str     = request.POST.get('monto', '').strip()
        forma_pago_id = request.POST.get('forma_pago', '').strip()
        tipo_mov      = request.POST.get('tipo_movimiento', 'recarga').strip().lower()

        if tipo_mov not in ('recarga', 'postpago', 'ajuste'):
            messages.error(request, "Tipo inválido.")
            return redirect('roles:recarga_directa')

        try:
            usuario = User.objects.get(id=usuario_id, is_active=True)
        except User.DoesNotExist:
            messages.error(request, "Usuario no válido.")
            return redirect('roles:recarga_directa')

        try:
            monto = Decimal(monto_str)
            if monto <= 0:
                raise ValueError()
        except Exception:
            messages.error(request, "Monto inválido.")
            return redirect('roles:recarga_directa')

        try:
            forma_pago = FormaPago.objects.get(id=forma_pago_id, activo=True)
        except Exception:
            messages.error(request, "Forma de pago no válida.")
            return redirect('roles:recarga_directa')

        # ═══════════ AJUSTE MANUAL ═══════════
        if tipo_mov == 'ajuste':
            signo  = (request.POST.get('signo') or 'sumar').strip().lower()
            motivo = (request.POST.get('motivo_ajuste') or '').strip()[:200]

            if signo not in ('sumar', 'restar'):
                messages.error(request, "Signo inválido.")
                return redirect('roles:recarga_directa')
            if not motivo:
                messages.error(request, "El motivo del ajuste es obligatorio.")
                return redirect('roles:recarga_directa')

            fondo_qs = Fondo.objects.select_for_update().filter(
                usuario=usuario, forma_pago=forma_pago, activo=True
            )
            if not es_superadmin:
                fondo_qs = fondo_qs.filter(asignado_por=user)

            with transaction.atomic():
                fondo = fondo_qs.first()
                if not fondo:
                    if not es_superadmin and not Fondo.objects.filter(
                        usuario=usuario, asignado_por=user, activo=True
                    ).exists():
                        messages.error(request, "No tienes permiso para ajustar este cliente.")
                        return redirect('roles:recarga_directa')
                    fondo = Fondo.objects.create(
                        usuario=usuario, forma_pago=forma_pago,
                        asignado_por=user, monto=Decimal('0.00'), activo=True,
                    )

                saldo_antes = fondo.monto or Decimal('0.00')
                delta = monto if signo == 'sumar' else -monto
                fondo.monto = saldo_antes + delta
                fondo.save(update_fields=['monto', 'actualizado_en'])

                MovimientoFondo.objects.create(
                    emisor=user if signo == 'restar' else None,
                    receptor=usuario, forma_pago=forma_pago,
                    monto=delta, tipo='ajuste', estado='confirmado',
                    motivo=motivo,
                    nota=("Ajuste +" if signo == 'sumar' else "Ajuste −") + f" {forma_pago.nombre}: {motivo}",
                    saldo_antes=saldo_antes,
                    saldo_despues=fondo.monto,
                    datos_transferencia={
                        'ajuste_manual': True, 'signo': signo,
                        'gestor': user.username, 'gestor_id': user.id,
                    },
                )

            crear_notificacion(
                usuario=usuario, tipo='info',
                mensaje=("⚖️ Ajuste " + ("a favor" if signo == 'sumar' else "en contra") +
                         f" de ${monto} en {forma_pago.nombre}. Motivo: {motivo}"),
                datos={'monto': float(monto), 'signo': signo,
                       'forma_pago': forma_pago.nombre, 'gestor': user.username,
                       'saldo_antes': float(saldo_antes), 'saldo_despues': float(fondo.monto),
                       'motivo': motivo},
                prioridad='alta', categoria='financiera',
            )
            messages.success(request,
                f"⚖️ Ajuste {'+' if signo == 'sumar' else '−'}${monto} a {usuario.username} "
                f"({forma_pago.nombre}). Nuevo saldo: ${fondo.monto}")
            if volver == 'apostar':
                return redirect(reverse('jugadas:apostar') + f"?cliente_id={usuario.id}")
            return redirect('roles:recarga_directa')

        # ═══════════ RECARGA ═══════════
        if tipo_mov == 'recarga':
            solicitud = SolicitudRecarga.objects.create(
                cliente=usuario, gestor=user, forma_pago=forma_pago, monto=monto,
                estado='pagada', mensaje_cliente="Recarga directa por " + user.username,
                creado_por=user,
            )
            from .utils import _aplicar_ingreso_a_fondo
            monto_neto, descontado = _aplicar_ingreso_a_fondo(
                cliente=usuario, gestor=user, forma_pago=forma_pago, monto=monto,
            )
            msg = f"{user.username} te recargó ${monto} en {forma_pago.nombre}"
            if descontado > 0:
                msg += f". Aplicado al postpago: ${descontado}. Al fondo: ${monto_neto}"
            crear_notificacion(
                usuario=usuario, tipo='info', mensaje=msg,
                datos={'monto_bruto': float(monto), 'postpago_descontado': float(descontado),
                       'monto_neto': float(monto_neto), 'forma_pago': forma_pago.nombre,
                       'gestor': user.username},
                prioridad='alta', categoria='financiera',
            )
            messages.success(request, f"Recarga de ${monto} a {usuario.username}")
            if volver == 'apostar':
                return redirect(reverse('jugadas:apostar') + f"?cliente_id={usuario.id}&recarga_ok=1")
            return redirect('roles:recarga_directa')

        messages.error(request, "Postpago manual deshabilitado (Fase 1).")
        return redirect('roles:recarga_directa')
'''

    return src[:m.start(2)] + nuevo_post + src[m.end(2):]

patch("roles/views.py", "tipo_mov == 'ajuste'", patch_recarga_directa, "recarga_directa → ajuste")


# ═══════════════════════════════════════════════════════════════════
# PATCH 5 — roles/views.py : añadir historial_movimientos
# ═══════════════════════════════════════════════════════════════════
def patch_historial_view(src):
    if "def historial_movimientos(" in src:
        raise RuntimeError("ya existe")
    new_fn = '''

# ═══════════════════════════════════════════════════════════════════
# HISTORIAL DE MOVIMIENTOS DE FONDO (auditoría)
# ═══════════════════════════════════════════════════════════════════
@login_required
def historial_movimientos(request):
    """Historial de movimientos. Gestor → sus clientes. Superadmin → todos."""
    user = request.user
    es_superadmin = user.is_superuser or user.roles.filter(tipo='superadmin', activo=True).exists()
    es_banco      = user.roles.filter(tipo='banco', activo=True).exists()
    es_comercial  = user.roles.filter(tipo='comercial', activo=True).exists()

    if not (es_superadmin or es_banco or es_comercial):
        messages.error(request, "Sin permisos.")
        return redirect('publico:home')

    qs = MovimientoFondo.objects.select_related('emisor', 'receptor', 'forma_pago')

    # Permisos
    if es_superadmin:
        pass
    elif es_banco:
        comerciales_ids = list(Subordinacion.objects.filter(
            jefe=user, activo=True
        ).values_list('subordinado_id', flat=True))
        clientes_ids = list(Fondo.objects.filter(
            Q(asignado_por__in=comerciales_ids) | Q(asignado_por=user),
            activo=True
        ).values_list('usuario_id', flat=True).distinct())
        qs = qs.filter(Q(receptor_id__in=clientes_ids) | Q(emisor_id__in=clientes_ids))
    else:
        clientes_ids = list(Fondo.objects.filter(
            asignado_por=user, activo=True
        ).values_list('usuario_id', flat=True).distinct())
        qs = qs.filter(Q(receptor_id__in=clientes_ids) | Q(emisor_id__in=clientes_ids))

    # Filtros
    cliente_id = (request.GET.get('cliente') or '').strip()
    if cliente_id.isdigit():
        qs = qs.filter(Q(receptor_id=cliente_id) | Q(emisor_id=cliente_id))

    comercial_id = (request.GET.get('comercial') or '').strip()
    if comercial_id.isdigit() and (es_superadmin or es_banco):
        qs = qs.filter(Q(emisor_id=comercial_id) | Q(datos_transferencia__gestor_id=int(comercial_id)))

    tipo = (request.GET.get('tipo') or '').strip()
    if tipo:
        qs = qs.filter(tipo=tipo)

    fp_id = (request.GET.get('forma_pago') or '').strip()
    if fp_id.isdigit():
        qs = qs.filter(forma_pago_id=fp_id)

    fecha_desde = (request.GET.get('fecha_desde') or '').strip()
    if fecha_desde:
        qs = qs.filter(creado_en__date__gte=fecha_desde)
    fecha_hasta = (request.GET.get('fecha_hasta') or '').strip()
    if fecha_hasta:
        qs = qs.filter(creado_en__date__lte=fecha_hasta)

    q = (request.GET.get('q') or '').strip()
    if q:
        qs = qs.filter(Q(motivo__icontains=q) | Q(nota__icontains=q))

    # KPIs
    agg = qs.aggregate(
        creditos=Sum(Case(When(monto__gt=0, then='monto'), default=0)),
        debitos=Sum(Case(When(monto__lt=0, then='monto'), default=0)),
    )
    total_creditos = agg['creditos'] or Decimal('0.00')
    total_debitos  = agg['debitos']  or Decimal('0.00')
    neto = total_creditos + total_debitos

    qs = qs.order_by('-creado_en')
    paginator = Paginator(qs, 30)
    page_obj = paginator.get_page(request.GET.get('page'))

    # Selects
    if es_superadmin:
        clientes_sel = User.objects.filter(fondos__isnull=False, is_active=True).distinct().order_by('username')
        comerciales_sel = User.objects.filter(
            roles__tipo='comercial', roles__activo=True, is_active=True
        ).distinct().order_by('username')
    elif es_banco:
        clientes_sel = User.objects.filter(id__in=clientes_ids, is_active=True).order_by('username')
        comerciales_sel = User.objects.filter(id__in=comerciales_ids, is_active=True).order_by('username')
    else:
        clientes_sel = User.objects.filter(id__in=clientes_ids, is_active=True).order_by('username')
        comerciales_sel = User.objects.none()

    return render(request, 'roles/historial_movimientos.html', {
        'page_obj': page_obj,
        'total_creditos': total_creditos, 'total_debitos': total_debitos, 'neto': neto,
        'clientes_sel': clientes_sel, 'comerciales_sel': comerciales_sel,
        'formas_pago': FormaPago.objects.filter(activo=True).order_by('nombre'),
        'tipos': MovimientoFondo.TIPOS,
        'es_superadmin': es_superadmin, 'es_banco': es_banco, 'es_comercial': es_comercial,
        'filtros': {
            'cliente': cliente_id, 'comercial': comercial_id,
            'tipo': tipo, 'forma_pago': fp_id,
            'fecha_desde': fecha_desde, 'fecha_hasta': fecha_hasta, 'q': q,
        },
    })
'''
    return src + new_fn

patch("roles/views.py", "def historial_movimientos(", patch_historial_view, "historial_movimientos (nueva)")


# ═══════════════════════════════════════════════════════════════════
# PATCH 6 — usuarios/views.py : mis_movimientos
# ═══════════════════════════════════════════════════════════════════
def patch_usuarios_view(src):
    if "def mis_movimientos(" in src:
        raise RuntimeError("ya existe")
    # Asegurar imports
    if "Case, When" not in src:
        src = src.replace(
            "from django.db.models import Sum, Q",
            "from django.db.models import Sum, Q, Case, When",
            1,
        )
    new_fn = '''

# ═══════════════════════════════════════════════════════════════════
# MIS MOVIMIENTOS (cliente ve solo los suyos)
# ═══════════════════════════════════════════════════════════════════
@login_required
def mis_movimientos(request):
    """El cliente ve SOLO sus propios movimientos de fondo."""
    from django.core.paginator import Paginator
    qs = MovimientoFondo.objects.filter(
        Q(receptor=request.user) | Q(emisor=request.user)
    ).select_related('emisor', 'receptor', 'forma_pago').order_by('-creado_en')

    tipo = (request.GET.get('tipo') or '').strip()
    if tipo:
        qs = qs.filter(tipo=tipo)
    fp_id = (request.GET.get('forma_pago') or '').strip()
    if fp_id.isdigit():
        qs = qs.filter(forma_pago_id=fp_id)
    fecha_desde = (request.GET.get('fecha_desde') or '').strip()
    if fecha_desde:
        qs = qs.filter(creado_en__date__gte=fecha_desde)
    fecha_hasta = (request.GET.get('fecha_hasta') or '').strip()
    if fecha_hasta:
        qs = qs.filter(creado_en__date__lte=fecha_hasta)

    agg = qs.aggregate(
        creditos=Sum(Case(When(monto__gt=0, then='monto'), default=0)),
        debitos=Sum(Case(When(monto__lt=0, then='monto'), default=0)),
    )
    total_creditos = agg['creditos'] or Decimal('0.00')
    total_debitos  = agg['debitos']  or Decimal('0.00')
    neto = total_creditos + total_debitos

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'usuarios/mis_movimientos.html', {
        'page_obj': page_obj,
        'total_creditos': total_creditos, 'total_debitos': total_debitos, 'neto': neto,
        'clientes_sel': User.objects.none(), 'comerciales_sel': User.objects.none(),
        'formas_pago': FormaPago.objects.filter(activo=True).order_by('nombre'),
        'tipos': MovimientoFondo.TIPOS,
        'es_superadmin': False, 'es_banco': False, 'es_comercial': False,
        'filtros': {'tipo': tipo, 'forma_pago': fp_id,
                    'fecha_desde': fecha_desde, 'fecha_hasta': fecha_hasta,
                    'cliente': '', 'comercial': '', 'q': ''},
    })
'''
    return src + new_fn

patch("usuarios/views.py", "def mis_movimientos(", patch_usuarios_view, "mis_movimientos (nueva)")


# ═══════════════════════════════════════════════════════════════════
# PATCH 7 — URLs
# ═══════════════════════════════════════════════════════════════════
def patch_urls(path, marker, line):
    p = BASE / path
    if not p.exists():
        CHANGES.append((path, "ERR", "no existe"))
        return
    src = p.read_text(encoding="utf-8")
    if marker in src:
        CHANGES.append((path, "SKIP", "ya aplicado"))
        return
    m = re.search(r"urlpatterns\s*=\s*\[", src)
    if not m:
        CHANGES.append((path, "ERR", "no encontré urlpatterns"))
        return
    src = src[:m.end()] + "\n    " + line + src[m.end():]
    p.write_text(src, encoding="utf-8")
    CHANGES.append((path, "OK", "url añadida"))

patch_urls("roles/urls.py", "historial_movimientos",
           "path('historial-movimientos/', views.historial_movimientos, name='historial_movimientos'),")
patch_urls("usuarios/urls.py", "mis_movimientos",
           "path('mis-movimientos/', views.mis_movimientos, name='mis_movimientos'),")


# ═══════════════════════════════════════════════════════════════════
# PATCH 8 — recarga_directa.html : tab Ajuste + panel + JS
# ═══════════════════════════════════════════════════════════════════
def patch_recarga_html(src):
    # Añadir tab
    if 'data-tab="ajuste"' not in src:
        anchor = '</button>\n      </div>'  # cierre del último mov-tab + cierre del contenedor
        # Ancla más segura: justo tras el tab de postpago
        m = re.search(r'(<button[^>]*data-tab="postpago".*?</button>)\s*</div>', src, re.DOTALL)
        if not m:
            raise RuntimeError("no encontré bloque de mov-tabs")
        tab_ajuste = '''

        <button type="button" class="mov-tab tab-ajuste" data-tab="ajuste"
                style="border-color:#c7d2fe;background:linear-gradient(145deg,#eef2ff,#e0e7ff);color:#3730a3;">
          <i class="fas fa-balance-scale" style="color:#4f46e5;"></i>⚖️ Ajuste de fondo
          <span class="mt-sub">Corrección manual + / −</span>
        </button>
      </div>'''
        src = src[:m.end()] + tab_ajuste + src[m.end():]

    # Añadir panel formAjuste (antes del cierre del locked-panel)
    if 'id="formAjuste"' not in src:
        m = re.search(r'(</form>)\s*(</div>\s*{% else %})', src, re.DOTALL)
        if not m:
            raise RuntimeError("no encontré cierre del locked-panel")
        panel = '''

      <form method="post" class="mov-panel" id="formAjuste"
            style="background:linear-gradient(145deg,#eef2ff,#e0e7ff);border:2px solid #a5b4fc;border-radius:16px;padding:20px 22px;">
        {% csrf_token %}
        <input type="hidden" name="usuario_id" value="{{ usuario_preseleccionado.id }}">
        <input type="hidden" name="volver" value="{{ volver }}">
        <input type="hidden" name="tipo_movimiento" value="ajuste">

        <div class="mb-3">
          <label class="form-label" style="color:#3730a3;font-weight:800;">Forma de pago <span style="color:#DC2626;">*</span></label>
          <select name="forma_pago" class="form-select" required>
            <option value="">-- Selecciona forma de pago --</option>
            {% for fp in formas_pago %}
              <option value="{{ fp.id }}">{{ fp.nombre }}</option>
            {% endfor %}
          </select>
        </div>

        <div class="mb-3">
          <label class="form-label" style="color:#3730a3;font-weight:800;">Signo <span style="color:#DC2626;">*</span></label>
          <div style="display:flex;gap:10px;">
            <label style="flex:1;background:#dcfce7;border:2px solid #22c55e;border-radius:10px;padding:10px;text-align:center;font-weight:800;color:#065f46;cursor:pointer;">
              <input type="radio" name="signo" value="sumar" checked style="margin-right:6px;">➕ SUMAR
            </label>
            <label style="flex:1;background:#fee2e2;border:2px solid #ef4444;border-radius:10px;padding:10px;text-align:center;font-weight:800;color:#7f1d1d;cursor:pointer;">
              <input type="radio" name="signo" value="restar" style="margin-right:6px;">➖ RESTAR
            </label>
          </div>
        </div>

        <div class="mb-3">
          <label class="form-label" style="color:#3730a3;font-weight:800;">Monto <span style="color:#DC2626;">*</span></label>
          <input type="number" step="0.01" min="0.01" name="monto" class="form-control" placeholder="0.00" required>
        </div>

        <div class="mb-3">
          <label class="form-label" style="color:#3730a3;font-weight:800;">Motivo / razón <span style="color:#DC2626;">*</span></label>
          <input type="text" name="motivo_ajuste" class="form-control" maxlength="200" required
                 placeholder="Ej: corrección por transferencia externa, ajuste por redondeo...">
          <small style="font-size:.68rem;color:#4f46e5;font-weight:600;">Obligatorio. Queda en el historial del cliente.</small>
        </div>

        <button type="submit" class="btn-mov" style="background:linear-gradient(135deg,#6366f1,#4f46e5);">
          <i class="fas fa-balance-scale"></i> Aplicar ajuste
        </button>
      </form>'''
        src = src[:m.start()] + panel + src[m.start():]

    # Reemplazar el JS de tabs
    js_new = '''<script>
document.addEventListener('DOMContentLoaded', function(){
  var tabs = document.querySelectorAll('.mov-tab');
  if (!tabs.length) return;
  var map = { recarga: 'formRecarga', postpago: 'formPostpago', ajuste: 'formAjuste' };
  tabs.forEach(function(tab){
    tab.addEventListener('click', function(){
      var target = tab.dataset.tab;
      tabs.forEach(function(t){ t.classList.remove('active'); });
      tab.classList.add('active');
      document.querySelectorAll('.mov-panel').forEach(function(p){ p.classList.remove('active'); });
      var panel = document.getElementById(map[target]);
      if (panel){
        panel.classList.add('active');
        var inp = panel.querySelector('input[type="number"]');
        if (inp) setTimeout(function(){ inp.focus(); }, 120);
      }
    });
  });
});
</script>'''
    src = re.sub(
        r"<script>\s*document\.addEventListener\('DOMContentLoaded'.*?</script>",
        js_new, src, count=1, flags=re.DOTALL,
    )
    return src

patch("roles/templates/roles/recarga_directa.html", 'id="formAjuste"',
      patch_recarga_html, "recarga_directa.html tabs+panel")


# ═══════════════════════════════════════════════════════════════════
# REPORTE
# ═══════════════════════════════════════════════════════════════════
print("\n─── REPORTE DE PARCHES ───")
fail = 0
for path, status, msg in CHANGES:
    icon = {"OK": "✔", "SKIP": "○", "ERR": "✘"}.get(status, "?")
    print(f"  {icon} [{status}] {path} — {msg}")
    if status == "ERR":
        fail += 1

if fail:
    print(f"\n✘ {fail} parche(s) fallaron. Revisa los mensajes arriba.")
    sys.exit(1)
print("\n✔ Todos los parches aplicados o ya presentes.")
PYEOF

# ─────────────────────────────────────────────────────────────────────
step "5/8 · Creando templates"
# ─────────────────────────────────────────────────────────────────────
python3 - "$PROJECT" << 'PYEOF'
import sys
from pathlib import Path
BASE = Path(sys.argv[1])

TPL_HIST = r'''{% extends "base.html" %}
{% load static %}
{% block page_title %}📒 Historial de Movimientos{% endblock %}
{% block extra_css %}
<style>
:root{--g-pri:#10B981;--g-grad:linear-gradient(135deg,#10B981,#34D399);--rad:16px;}
.page-wrapper{background:#f0fdf4;min-height:100vh;padding-bottom:40px;}
.hdr{background:rgba(255,255,255,.85);backdrop-filter:blur(12px);border-radius:var(--rad);padding:22px 26px;margin-bottom:20px;box-shadow:0 8px 32px rgba(16,185,129,.10);}
.hdr h1{font-size:1.5rem;font-weight:800;color:#064E3B;margin:0;}
.filtros{background:rgba(255,255,255,.85);border-radius:var(--rad);padding:18px 20px;margin-bottom:18px;box-shadow:0 8px 32px rgba(16,185,129,.10);}
.filtros .row{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px;}
.filtros label{font-size:.7rem;font-weight:800;color:#065F46;text-transform:uppercase;letter-spacing:.4px;display:block;margin-bottom:3px;}
.filtros input,.filtros select{width:100%;padding:8px 10px;border:1.5px solid #b6e5c2;border-radius:8px;font-size:.82rem;font-weight:600;color:#064E3B;background:#fff;}
.filtros input:focus,.filtros select:focus{outline:none;border-color:#10B981;box-shadow:0 0 0 3px rgba(16,185,129,.15);}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px;margin-bottom:18px;}
.kpi{background:linear-gradient(145deg,#fff,#f4fbf6);border:1.5px solid #c8ead4;border-radius:12px;padding:14px 16px;box-shadow:3px 3px 0 #a7e8b8;}
.kpi .lbl{font-size:.65rem;font-weight:800;color:#065F46;text-transform:uppercase;letter-spacing:.5px;}
.kpi .val{font-size:1.15rem;font-weight:900;color:#064E3B;margin-top:4px;}
.kpi .val.c{color:#047857;} .kpi .val.d{color:#b91c1c;} .kpi .val.n{color:#0369a1;}
.tabla{background:#fff;border-radius:var(--rad);overflow:hidden;box-shadow:0 8px 32px rgba(16,185,129,.10);}
.tabla table{width:100%;border-collapse:collapse;font-size:.8rem;}
.tabla th{background:linear-gradient(180deg,#f0fdf4,#ecfdf5);padding:12px 10px;text-align:left;font-size:.62rem;text-transform:uppercase;letter-spacing:.5px;color:#065F46;font-weight:800;border-bottom:2px solid #c8ead4;}
.tabla td{padding:10px;border-bottom:1px solid #ecfdf5;vertical-align:middle;}
.tabla tr:hover td{background:#f0fdf4;}
.chip{display:inline-block;padding:2px 10px;border-radius:20px;font-size:.62rem;font-weight:800;text-transform:uppercase;letter-spacing:.4px;}
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
.motivo{font-size:.72rem;color:#374151;font-weight:600;}
.motivo .nota{display:block;font-size:.65rem;color:#6B7280;font-weight:500;margin-top:2px;}
.empty{padding:60px 20px;text-align:center;color:#6B7280;}
.empty i{font-size:3rem;color:#A7F3D0;display:block;margin-bottom:12px;}
.pag{display:flex;justify-content:center;gap:8px;margin-top:20px;}
.pag a,.pag span{padding:8px 14px;border-radius:10px;background:#fff;border:1.5px solid #b6e5c2;font-weight:700;color:#064E3B;text-decoration:none;}
.pag .cur{background:var(--g-grad);color:#fff;border-color:#047857;}
@media(max-width:768px){.tabla th:nth-child(5),.tabla td:nth-child(5){display:none;}}
</style>
{% endblock %}
{% block content %}
<div class="page-wrapper container-fluid py-3">
  <div class="hdr">
    <h1>📒 Historial de Movimientos de Fondo</h1>
    <p class="mb-0" style="color:#374151;font-size:.9rem;margin-top:6px;">Todos los movimientos con fecha, hora y motivo.</p>
  </div>
  <div class="kpis">
    <div class="kpi"><div class="lbl">Créditos</div><div class="val c">+${{ total_creditos|floatformat:2 }}</div></div>
    <div class="kpi"><div class="lbl">Débitos</div><div class="val d">${{ total_debitos|floatformat:2 }}</div></div>
    <div class="kpi"><div class="lbl">Neto</div><div class="val n">${{ neto|floatformat:2 }}</div></div>
    <div class="kpi"><div class="lbl">Movimientos</div><div class="val">{{ page_obj.paginator.count }}</div></div>
  </div>
  <form method="get" class="filtros">
    <div class="row">
      {% if es_superadmin or es_banco %}
      <div><label>Comercial</label>
        <select name="comercial" onchange="this.form.submit()">
          <option value="">— Todos —</option>
          {% for c in comerciales_sel %}<option value="{{ c.id }}" {% if filtros.comercial == c.id|stringformat:'s' %}selected{% endif %}>{{ c.username }}</option>{% endfor %}
        </select>
      </div>{% endif %}
      <div><label>Cliente</label>
        <select name="cliente" onchange="this.form.submit()">
          <option value="">— Todos —</option>
          {% for c in clientes_sel %}<option value="{{ c.id }}" {% if filtros.cliente == c.id|stringformat:'s' %}selected{% endif %}>{{ c.username }}</option>{% endfor %}
        </select>
      </div>
      <div><label>Tipo</label>
        <select name="tipo" onchange="this.form.submit()">
          <option value="">— Todos —</option>
          {% for t, lbl in tipos %}<option value="{{ t }}" {% if filtros.tipo == t %}selected{% endif %}>{{ lbl }}</option>{% endfor %}
        </select>
      </div>
      <div><label>Forma de pago</label>
        <select name="forma_pago" onchange="this.form.submit()">
          <option value="">— Todas —</option>
          {% for fp in formas_pago %}<option value="{{ fp.id }}" {% if filtros.forma_pago == fp.id|stringformat:'s' %}selected{% endif %}>{{ fp.nombre }}</option>{% endfor %}
        </select>
      </div>
      <div><label>Desde</label><input type="date" name="fecha_desde" value="{{ filtros.fecha_desde }}" onchange="this.form.submit()"></div>
      <div><label>Hasta</label><input type="date" name="fecha_hasta" value="{{ filtros.fecha_hasta }}" onchange="this.form.submit()"></div>
      <div><label>Buscar motivo</label><input type="text" name="q" value="{{ filtros.q }}" placeholder="motivo, nota..." onchange="this.form.submit()"></div>
    </div>
    <div style="margin-top:12px;text-align:right;"><a href="?" style="font-size:.78rem;color:#6B7280;font-weight:700;text-decoration:none;">✕ Limpiar</a></div>
  </form>
  <div class="tabla"><div style="overflow-x:auto;">
    <table>
      <thead><tr>
        <th>Fecha / Hora</th><th>Tipo</th><th>Cliente</th><th>Forma de pago</th>
        <th>Monto</th><th>Motivo</th><th>Gestor</th>
      </tr></thead>
      <tbody>
      {% for m in page_obj %}
      <tr>
        <td><div style="font-weight:800;color:#064E3B;">{{ m.creado_en|date:'d/m/Y' }}</div><div class="hora">{{ m.creado_en|date:'H:i:s' }}</div></td>
        <td><span class="chip {{ m.tipo }}">{{ m.get_tipo_display }}</span></td>
        <td><strong>{{ m.receptor.username }}</strong></td>
        <td>{{ m.forma_pago.nombre|default:"—" }}</td>
        <td>
          <span class="monto {% if m.monto >= 0 %}cred{% else %}deb{% endif %}">
            {% if m.monto >= 0 %}+{% endif %}${{ m.monto|floatformat:2 }}</span>
          {% if m.saldo_antes is not None %}<div class="hora">${{ m.saldo_antes|floatformat:2 }} → ${{ m.saldo_despues|floatformat:2 }}</div>{% endif %}
        </td>
        <td class="motivo">{{ m.motivo|default:m.nota|default:"—"|truncatechars:60 }}
          {% if m.nota and m.motivo %}<span class="nota">{{ m.nota|truncatechars:70 }}</span>{% endif %}
        </td>
        <td>{{ m.emisor.username|default:"—" }}</td>
      </tr>
      {% empty %}
      <tr><td colspan="7"><div class="empty"><i class="fas fa-inbox"></i>Sin movimientos con esos filtros.</div></td></tr>
      {% endfor %}
      </tbody>
    </table>
  </div></div>
  {% if page_obj.has_other_pages %}
  <div class="pag">
    {% if page_obj.has_previous %}<a href="?page={{ page_obj.previous_page_number }}{% for k,v in filtros.items %}{% if v %}&{{ k }}={{ v }}{% endif %}{% endfor %}">‹ Anterior</a>{% endif %}
    <span class="cur">{{ page_obj.number }} / {{ page_obj.paginator.num_pages }}</span>
    {% if page_obj.has_next %}<a href="?page={{ page_obj.next_page_number }}{% for k,v in filtros.items %}{% if v %}&{{ k }}={{ v }}{% endif %}{% endfor %}">Siguiente ›</a>{% endif %}
  </div>
  {% endif %}
</div>
{% endblock %}
'''

TPL_MIS = '''{% extends "base.html" %}
{% load static %}
{% block page_title %}📒 Mis Movimientos{% endblock %}
{% block extra_css %}{% include "roles/historial_movimientos.html" %}{% endblock %}
'''

# Escribir
p1 = BASE / "roles/templates/roles/historial_movimientos.html"
p1.parent.mkdir(parents=True, exist_ok=True)
p1.write_text(TPL_HIST, encoding="utf-8")
print(f"  ✔ {p1}")

p2 = BASE / "usuarios/templates/usuarios/mis_movimientos.html"
p2.parent.mkdir(parents=True, exist_ok=True)
# El template del cliente reusa el mismo body: usamos include completo
p2.write_text('''{% extends "base.html" %}
{% load static %}
{% block page_title %}📒 Mis Movimientos{% endblock %}
{% block content %}
  {% include "roles/historial_movimientos.html" with es_superadmin=False es_banco=False es_comercial=False %}
{% endblock %}
''', encoding="utf-8")
print(f"  ✔ {p2}")
PYEOF

# ─────────────────────────────────────────────────────────────────────
step "6/8 · Migraciones"
# ─────────────────────────────────────────────────────────────────────
python3 manage.py makemigrations roles --name add_motivo_saldos_movimientofondo 2>&1 | grep -v "^No changes" || true
python3 manage.py migrate roles

# ─────────────────────────────────────────────────────────────────────
step "7/8 · Verificación post-aplicación"
# ─────────────────────────────────────────────────────────────────────
python3 manage.py shell << 'PYEOF'
from roles.models import MovimientoFondo
import django
django.setup()

# Verificar campos
faltan = [f for f in ('motivo', 'saldo_antes', 'saldo_despues') if not hasattr(MovimientoFondo, f)]
if faltan:
    print(f"✘ FALTAN CAMPOS: {faltan}")
    exit(1)
print("  ✔ MovimientoFondo: motivo, saldo_antes, saldo_despues presentes")

# Verificar vista historial
try:
    from roles.views import historial_movimientos
    print("  ✔ roles.views.historial_movimientos importable")
except Exception as e:
    print(f"  ✘ historial_movimientos: {e}")
    exit(1)

try:
    from usuarios.views import mis_movimientos
    print("  ✔ usuarios.views.mis_movimientos importable")
except Exception as e:
    print(f"  ✘ mis_movimientos: {e}")
    exit(1)

# Verificar URL
try:
    from django.urls import reverse
    print(f"  ✔ URL: {reverse('roles:historial_movimientos')}")
    print(f"  ✔ URL: {reverse('usuarios:mis_movimientos')}")
except Exception as e:
    print(f"  ✘ URLs: {e}")
    exit(1)
PYEOF

# ─────────────────────────────────────────────────────────────────────
step "8/8 · Resumen"
# ─────────────────────────────────────────────────────────────────────
cat << EOF

🎉  AUDITORÍA DE MOVIMIENTOS APLICADA

📂  Backup:      $BACKUP_DIR
📝  Rollback:    bash $BACKUP_DIR/../rollback_auditoria.sh
                 (o: bash /home/LottoBooM/rollback_auditoria.sh)

🌐  URLs nuevas:
    → /roles/historial-movimientos/    (gestor)
    → /usuarios/mis-movimientos/       (cliente)

⚠️  PENDIENTE MANUAL (revisar):
    1. Añadir enlaces en el sidebar (base.html):
       <a href="{% url 'roles:historial_movimientos' %}">Historial movimientos</a>
       <a href="{% url 'usuarios:mis_movimientos' %}">Mis movimientos</a>
    2. Si jugadas/views.py NO tenía MovimientoFondo en guardar_apuesta,
       añadirlo manualmente (ver README_AUDITORIA.md sección "Pendientes").

✅  Prueba:
    - Ir a /roles/recarga-directa/?usuario_id=X → 3er tab "⚖️ Ajuste"
    - Hacer ajuste +$100 con motivo → verificar en /roles/historial-movimientos/
EOF

