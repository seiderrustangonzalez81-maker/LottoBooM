from pathlib import Path
import ast

p = Path("/home/LottoBooM/roles/utils.py")
src = p.read_text(encoding="utf-8")

if "def calcular_saldos_cliente" in src:
    print("SKIP: función ya existe")
    raise SystemExit(0)

# Insertar al inicio del archivo (después de imports)
# Buscar dónde insertar
idx = src.find("def _aplicar_ingreso_a_fondo")
if idx < 0:
    print("ERROR: no encontré punto de inserción")
    raise SystemExit(1)

funcion = '''# ═══════════════════════════════════════════════════════════════
# SALDOS_UNIFICADOS_V1
# Fuente única de verdad para saldos de un cliente.
# ═══════════════════════════════════════════════════════════════
def calcular_saldos_cliente(cliente, gestor=None):
    """
    Calcula TODOS los saldos de un cliente de forma consistente.
    
    Args:
        cliente (User): El cliente a consultar
        gestor (User|None): 
            - Si se pasa: SOLO fondos con asignado_por=gestor
            - Si es None: agrupa por CADA gestor
    
    Returns:
        dict con:
        {
          'por_gestor': {
            gestor_id: {
              'gestor': User,
              'gestor_nombre': str,
              'por_fp': {
                fp_id: {
                  'forma_pago': FormaPago,
                  'fp_nombre': str,
                  'fondo': Decimal,
                  'bonos': Decimal,
                  'postpago': Decimal,
                  'saldo_total': Decimal,
                  'saldo_real': Decimal,
                }
              },
              'total_fondos': Decimal,
              'total_bonos': Decimal,
              'total_postpago': Decimal,
              'saldo_total': Decimal,
              'saldo_real': Decimal,
            }
          },
          'total_global': {
            'fondos': Decimal,
            'bonos': Decimal,
            'postpago': Decimal,
            'saldo_total': Decimal,
            'saldo_real': Decimal,
          }
        }
    """
    from decimal import Decimal
    from roles.models import Fondo, Bono, Postpago
    from pagos.models import FormaPago

    CERO = Decimal('0.00')

    # ─── FONDOS ───
    qs_fondos = Fondo.objects.filter(usuario=cliente, activo=True).select_related(
        'forma_pago', 'asignado_por'
    )
    if gestor:
        qs_fondos = qs_fondos.filter(asignado_por=gestor)

    # ─── BONOS ───
    from django.utils import timezone as _tz
    qs_bonos = Bono.objects.filter(
        usuario=cliente, estado='activo', saldo_restante__gt=0,
    ).select_related('forma_pago', 'asignado_por')
    if gestor:
        qs_bonos = qs_bonos.filter(asignado_por=gestor)
    # Excluir vencidos
    qs_bonos = qs_bonos.filter(
        models.Q(fecha_vencimiento__isnull=True) |
        models.Q(fecha_vencimiento__gte=_tz.now())
    )

    # ─── POSTPAGOS ───
    qs_pp = Postpago.objects.filter(
        cliente=cliente, activo=True, saldo__lt=0,
    ).select_related('forma_pago', 'gestor')
    if gestor:
        qs_pp = qs_pp.filter(gestor=gestor)

    # ═══════════════════════════════════════════════════════════
    # ESTRUCTURA por_gestor
    # ═══════════════════════════════════════════════════════════
    por_gestor = {}

    def _entrada_gestor(g):
        if g is None:
            return None
        gid = g.id
        if gid not in por_gestor:
            por_gestor[gid] = {
                'gestor': g,
                'gestor_nombre': g.username,
                'por_fp': {},
                'total_fondos': CERO,
                'total_bonos': CERO,
                'total_postpago': CERO,
            }
        return por_gestor[gid]

    def _entrada_fp(gid, fp):
        entry = por_gestor[gid]
        fpid = fp.id
        if fpid not in entry['por_fp']:
            entry['por_fp'][fpid] = {
                'forma_pago': fp,
                'fp_nombre': fp.nombre,
                'fondo': CERO,
                'bonos': CERO,
                'postpago': CERO,
            }
        return entry['por_fp'][fpid]

    # Sumar fondos
    for f in qs_fondos:
        if not f.forma_pago:
            continue
        g = f.asignado_por
        e_g = _entrada_gestor(g)
        if not e_g:
            continue
        e_fp = _entrada_fp(g.id, f.forma_pago)
        e_fp['fondo'] += f.monto

    # Sumar bonos
    for b in qs_bonos:
        g = b.asignado_por
        e_g = _entrada_gestor(g)
        if not e_g:
            continue
        # Bonos sin FP se agrupan en una FP especial
        fp = b.forma_pago
        if fp:
            e_fp = _entrada_fp(g.id, fp)
            e_fp['bonos'] += b.saldo_restante

    # Sumar postpagos
    for p in qs_pp:
        g = p.gestor
        e_g = _entrada_gestor(g)
        if not e_g:
            continue
        fp = p.forma_pago
        if fp:
            e_fp = _entrada_fp(g.id, fp)
            e_fp['postpago'] += abs(p.saldo)

    # Calcular totales por gestor + agregar saldo_total/saldo_real
    for gid, entry in por_gestor.items():
        for fpid, fp in entry['por_fp'].items():
            fp['saldo_total'] = fp['fondo'] + fp['bonos']
            fp['saldo_real'] = fp['saldo_total'] - fp['postpago']
            entry['total_fondos'] += fp['fondo']
            entry['total_bonos'] += fp['bonos']
            entry['total_postpago'] += fp['postpago']
        entry['saldo_total'] = entry['total_fondos'] + entry['total_bonos']
        entry['saldo_real'] = entry['saldo_total'] - entry['total_postpago']

    # Totales globales
    total_global = {
        'fondos': sum((e['total_fondos'] for e in por_gestor.values()), CERO),
        'bonos': sum((e['total_bonos'] for e in por_gestor.values()), CERO),
        'postpago': sum((e['total_postpago'] for e in por_gestor.values()), CERO),
    }
    total_global['saldo_total'] = total_global['fondos'] + total_global['bonos']
    total_global['saldo_real'] = total_global['saldo_total'] - total_global['postpago']

    return {
        'por_gestor': por_gestor,
        'total_global': total_global,
    }


'''

src = src[:idx] + funcion + src[idx:]

try:
    ast.parse(src)
except SyntaxError as e:
    print(f"ERROR sintaxis: {e}")
    raise SystemExit(1)

p.write_text(src, encoding="utf-8")
print("OK: calcular_saldos_cliente() agregada")
