from django.contrib.auth.models import User
from roles.models import MovimientoFondo, Fondo
from jugadas.models import Boleta
from django.utils import timezone
from django.db.models import Q

# Buscar a Adile (sin importar mayúsculas/minúsculas)
adile = User.objects.filter(username__iexact='Adile').first()

if not adile:
    print("❌ Cliente Adile no encontrado.")
else:
    print(f"=== INFORMACIÓN DE ADILE (ID: {adile.id}) ===")
    hoy = timezone.localdate()
    print(f"Fecha de hoy: {hoy}\n")

    # 1. Movimientos de fondo (recargas, ajustes, premios) de hoy
    print("--- MOVIMIENTOS DE FONDO DE HOY ---")
    movs = MovimientoFondo.objects.filter(
        Q(emisor=adile) | Q(receptor=adile),
        creado_en__date=hoy
    ).order_by('creado_en')

    if not movs.exists():
        print("No hay movimientos de fondo registrados hoy.")
    else:
        for m in movs:
            emisor = m.emisor.username if m.emisor else "SISTEMA"
            receptor = m.receptor.username if m.receptor else "SISTEMA"
            fp = m.forma_pago.nombre if m.forma_pago else "Sin FP"
            print(f"[{m.creado_en.strftime('%H:%M:%S')}] Tipo: {m.tipo} | Monto: ${m.monto} | FP: {fp} | De: {emisor} -> Para: {receptor} | Motivo: {m.motivo}")

    # 2. Boletas jugadas hoy
    print("\n--- BOLETAS JUGADAS HOY ---")
    boletas = Boleta.objects.filter(usuario=adile, creado_en__date=hoy).order_by('creado_en')
    if not boletas.exists():
        print("No hay boletas jugadas hoy.")
    else:
        for b in boletas:
            print(f"[{b.creado_en.strftime('%H:%M:%S')}] Boleta #{b.id} | Monto: ${b.monto_total} | Premio: ${b.premios_total} | Estado: {b.estado}")

    # 3. Saldos actuales en la tabla de Fondos
    print("\n--- SALDOS ACTUALES (FONDOS) ---")
    fondos = Fondo.objects.filter(usuario=adile, activo=True)
    if not fondos.exists():
        print("No tiene fondos activos en este momento.")
    else:
        for f in fondos:
            fp = f.forma_pago.nombre if f.forma_pago else "Sin FP"
            asignado = f.asignado_por.username if f.asignado_por else "Nadie"
            print(f"{fp:<15} | Saldo: ${f.monto:<10} | Asignado por: {asignado}")
