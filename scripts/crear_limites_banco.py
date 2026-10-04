# scripts/crear_limites_todos_bancos.py
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'LottoBooM.settings')
django.setup()

from decimal import Decimal
from django.contrib.auth.models import User
from roles.models import LimiteApuesta, DosisPago
from sorteos.models import DosisBase, SorteoFormaJuego
from pagos.models import FormaPago

# Obtener todos los bancos activos
bancos = User.objects.filter(roles__tipo='banco', roles__activo=True).distinct()
formas_pago = FormaPago.objects.filter(activo=True)
combinaciones = SorteoFormaJuego.objects.filter(activo=True).select_related('sorteo', 'forma_juego')

print(f"🏦 Bancos encontrados: {bancos.count()}")
print(f"💳 Formas de pago activas: {formas_pago.count()}")
print(f"🔗 Combinaciones Sorteo-Forma: {combinaciones.count()}")
print("=" * 60)

total_bancos_procesados = 0

for banco in bancos:
    print(f"\n🚀 Procesando banco: {banco.username}")
    total_limites = 0
    total_dosis = 0

    for sf in combinaciones:
        dosis_base = DosisBase.objects.filter(
            sorteo=sf.sorteo, forma_juego=sf.forma_juego, activo=True
        ).first()
        dosis_por_peso = dosis_base.dosis_por_peso if dosis_base else Decimal('1.0')
        if dosis_por_peso <= 0:
            dosis_por_peso = Decimal('1.0')

        # Valor base para límite y sobrelímite
        valor_base = Decimal('1000.00')

        for fp in formas_pago:
            # Límite + Sobrelímite (ambos con el mismo valor)
            _, created = LimiteApuesta.objects.get_or_create(
                banco=banco,
                comercial=None,
                sorteo=sf.sorteo,
                forma_juego=sf.forma_juego,
                forma_pago=fp,
                defaults={
                    'monto_maximo': valor_base,
                    'monto_sobrelimite': valor_base,  # ← IGUAL AL LÍMITE
                    'activo': True
                }
            )
            if created:
                total_limites += 1

            # Dosis
            _, created = DosisPago.objects.get_or_create(
                banco=banco,
                comercial=None,
                sorteo=sf.sorteo,
                forma_juego=sf.forma_juego,
                forma_pago=fp,
                defaults={'monto_por_peso': dosis_por_peso, 'activo': True}
            )
            if created:
                total_dosis += 1

    print(f"   ✅ Límites creados: {total_limites}")
    print(f"   ✅ Dosis creadas: {total_dosis}")
    total_bancos_procesados += 1

print("\n" + "=" * 60)
print(f"🎉 Procesados {total_bancos_procesados} bancos correctamente.")
print("📌 Ahora cada banco tiene límites y sobrelímites (iguales al límite).")
print("💡 Para asignarlos a los comerciales, usa el botón 'Copiar límites del banco' en la interfaz.")