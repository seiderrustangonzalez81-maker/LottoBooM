from jugadas.models import Boleta, Jugada
from django.db.models import Sum

print("=== VERIFICACIÓN DE BOLETAS Y PREMIOS ===")
total_boletas = Boleta.objects.count()
boletas_con_premio = Boleta.objects.filter(premios_total__gt=0).count()
print(f"Total de boletas en el sistema: {total_boletas}")
print(f"Boletas que tienen algún premio ganador: {boletas_con_premio}")

print("\n=== EJEMPLO CON EL USUARIO 'yusyyusy' ===")
from django.contrib.auth.models import User
u = User.objects.filter(username__iexact='yusyyusy').first()
if u:
    boletas_u = Boleta.objects.filter(usuario=u)
    print(f"El cliente {u.username} tiene {boletas_u.count()} boletas.")
    
    # Ver sus ultimas 3 boletas con premios
    for b in boletas_u.filter(premios_total__gt=0).order_by('-creado_en')[:3]:
        print(f" - Boleta ID: {b.id} | Monto Jugado: ${b.monto_total} | Premio Ganado: ${b.premios_total} | Estado: {b.estado}")
