from pathlib import Path
import ast

p = Path("/home/LottoBooM/jugadas/views.py")
src = p.read_text(encoding="utf-8")

if "FIX_SELFVIEW_V1" in src:
    print("SKIP: ya aplicado")
    raise SystemExit(0)

cambios = 0

# ══════════════════════════════════════════════════════════════
# FIX 1: api_verificar_saldo — agregar rama self-view
# ══════════════════════════════════════════════════════════════
viejo1 = """    else:
        fondos_qs = Fondo.objects.filter(
            Q(usuario=user, asignado_por=seleccionado) |
            Q(usuario=seleccionado, asignado_por=user),
            activo=True
        ).select_related('forma_pago')
        filtro_bono = (
            Q(usuario=user, asignado_por=seleccionado) |
            Q(usuario=seleccionado, asignado_por=user)
        )"""

nuevo1 = """    elif user.id == seleccionado.id:
        # FIX_SELFVIEW_V1: el cliente se ve a sí mismo → mostrar TODOS sus fondos
        fondos_qs = Fondo.objects.filter(
            usuario=seleccionado, activo=True
        ).select_related('forma_pago')
        filtro_bono = Q(usuario=seleccionado)
        if gestor_id_raw.isdigit():
            filtro_postpago = Q(cliente=seleccionado, gestor_id=int(gestor_id_raw))
        else:
            filtro_postpago = Q(cliente=seleccionado)
    else:
        fondos_qs = Fondo.objects.filter(
            Q(usuario=user, asignado_por=seleccionado) |
            Q(usuario=seleccionado, asignado_por=user),
            activo=True
        ).select_related('forma_pago')
        filtro_bono = (
            Q(usuario=user, asignado_por=seleccionado) |
            Q(usuario=seleccionado, asignado_por=user)
        )"""

if viejo1 in src:
    src = src.replace(viejo1, nuevo1, 1)
    print("OK: api_verificar_saldo — rama self-view agregada")
    cambios += 1
else:
    print("WARN 1: no encontré el bloque exacto en api_verificar_saldo")
    # Intento alternativo
    viejo1b = """    else:
        fondos_qs = Fondo.objects.filter(
            Q(usuario=user, asignado_por=seleccionado) |
            Q(usuario=seleccionado, asignado_por=user),
            activo=True
        ).select_related('forma_pago')"""
    nuevo1b = """    elif user.id == seleccionado.id:
        # FIX_SELFVIEW_V1
        fondos_qs = Fondo.objects.filter(
            usuario=seleccionado, activo=True
        ).select_related('forma_pago')
        filtro_bono = Q(usuario=seleccionado)
        filtro_postpago = Q(cliente=seleccionado)
    else:
        fondos_qs = Fondo.objects.filter(
            Q(usuario=user, asignado_por=seleccionado) |
            Q(usuario=seleccionado, asignado_por=user),
            activo=True
        ).select_related('forma_pago')"""
    if viejo1b in src:
        src = src.replace(viejo1b, nuevo1b, 1)
        print("OK: api_verificar_saldo — rama self-view (variante)")
        cambios += 1
    else:
        print("FALLO 1: pégame sed -n '2480,2520p' para arreglar manual")

# ══════════════════════════════════════════════════════════════
# FIX 2: api_forma_pago_cliente — self-view + dedupe por (FP, gestor)
# ══════════════════════════════════════════════════════════════
viejo2 = """        if es_superadmin:
            fondos_qs = Fondo.objects.filter(
                usuario=seleccionado, activo=True
            ).select_related('forma_pago', 'asignado_por')
        else:
            fondos_qs = Fondo.objects.filter(
                Q(usuario=user, asignado_por=seleccionado) |
                Q(usuario=seleccionado, asignado_por=user),
                activo=True
            ).select_related('forma_pago', 'asignado_por')

        formas_pago = []
        visto = set()
        for f in fondos_qs:
            if not f.forma_pago or f.forma_pago.id in visto:
                continue
            visto.add(f.forma_pago.id)
            formas_pago.append({
                'id': f.forma_pago.id,
                'nombre': f.forma_pago.nombre,
                'gestor_id': f.asignado_por_id,
                'gestor_username': f.asignado_por.username if f.asignado_por else None,
            })"""

nuevo2 = """        if es_superadmin or user.id == seleccionado.id:
            # FIX_SELFVIEW_V1: self-view o superadmin → todos sus fondos
            fondos_qs = Fondo.objects.filter(
                usuario=seleccionado, activo=True
            ).select_related('forma_pago', 'asignado_por')
        else:
            fondos_qs = Fondo.objects.filter(
                Q(usuario=user, asignado_por=seleccionado) |
                Q(usuario=seleccionado, asignado_por=user),
                activo=True
            ).select_related('forma_pago', 'asignado_por')

        formas_pago = []
        visto = set()
        for f in fondos_qs:
            if not f.forma_pago:
                continue
            # FIX_SELFVIEW_V1: dedupe por (FP, gestor) para no perder gestores
            key = (f.forma_pago.id, f.asignado_por_id)
            if key in visto:
                continue
            visto.add(key)
            formas_pago.append({
                'id': f.forma_pago.id,
                'nombre': f.forma_pago.nombre,
                'gestor_id': f.asignado_por_id,
                'gestor_username': f.asignado_por.username if f.asignado_por else None,
            })"""

if viejo2 in src:
    src = src.replace(viejo2, nuevo2, 1)
    print("OK: api_forma_pago_cliente — self-view + dedupe por (FP, gestor)")
    cambios += 1
else:
    print("WARN 2: no encontré api_forma_pago_cliente exacto")
    print("       pégame sed -n '2630,2680p' jugadas/views.py")

# Validar sintaxis
if cambios > 0:
    try:
        ast.parse(src)
    except SyntaxError as e:
        print(f"ERROR sintaxis: {e}")
        raise SystemExit(1)
    p.write_text(src, encoding="utf-8")
    print(f"\n✅ {cambios} cambio(s) aplicado(s)")
else:
    print("\n❌ No se aplicó nada")
