from pathlib import Path
import ast

p = Path("/home/LottoBooM/jugadas/views.py")
src = p.read_text(encoding="utf-8")

if "FIX_SELFVIEW_V2" in src:
    print("SKIP: ya aplicado")
    raise SystemExit(0)

# Bloque EXACTO a reemplazar (con comentarios)
viejo = """        if es_superadmin:
            fondos_qs = Fondo.objects.filter(
                usuario=seleccionado, activo=True
            ).select_related('forma_pago')
            filtro_bono = Q(usuario=seleccionado)
            # CONSISTENCIA_POSTPAGO_V1: si viene gestor_id, filtrar por gestor especifico
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

nuevo = """        if es_superadmin:
            fondos_qs = Fondo.objects.filter(
                usuario=seleccionado, activo=True
            ).select_related('forma_pago')
            filtro_bono = Q(usuario=seleccionado)
            # CONSISTENCIA_POSTPAGO_V1: si viene gestor_id, filtrar por gestor especifico
            if gestor_id_raw.isdigit():
                filtro_postpago = Q(cliente=seleccionado, gestor_id=int(gestor_id_raw))
            else:
                filtro_postpago = Q(cliente=seleccionado)
        elif user.id == seleccionado.id:
            # FIX_SELFVIEW_V2: el cliente se ve a sí mismo → TODOS sus fondos
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

if viejo not in src:
    print("ERROR: no encontré el bloque exacto")
    raise SystemExit(1)

src = src.replace(viejo, nuevo, 1)

try:
    ast.parse(src)
except SyntaxError as e:
    print(f"ERROR sintaxis: {e}")
    raise SystemExit(1)

p.write_text(src, encoding="utf-8")
print("OK: api_verificar_saldo — rama self-view agregada")
