from django.contrib.auth.models import User
from sorteos.models import Sorteo
from jugadas.models import FormaJuego
from pagos.models import FormaPago
from roles.models import RecursoAsignado, LimiteApuesta, DosisPago
from roles.dosis_default import get_dosis_global, get_limite_por_forma, get_sobre_por_forma

seider = User.objects.get(username__iexact='Seider')
sorteos = Sorteo.objects.filter(activo=True)
formas_juego = FormaJuego.objects.filter(activo=True)
formas_pago = FormaPago.objects.filter(activo=True)

# 1. Limpiar configuraciones viejas de Seider
RecursoAsignado.objects.filter(banco=seider).delete()
LimiteApuesta.objects.filter(banco=seider).delete()
DosisPago.objects.filter(banco=seider).delete()

# 2. Crear Recursos Asignados
for s in sorteos:
    RecursoAsignado.objects.create(banco=seider, tipo='sorteo', sorteo=s, activo=True)
for fj in formas_juego:
    RecursoAsignado.objects.create(banco=seider, tipo='forma_juego', forma_juego=fj, activo=True)
for fp in formas_pago:
    RecursoAsignado.objects.create(banco=seider, tipo='forma_pago', forma_pago=fp, activo=True)

# 3. Generar Límites y Dosis
limites_creados = 0
for s in sorteos:
    for fj in formas_juego:
        lim_val = get_limite_por_forma(fj.nombre)
        sobre_val = get_sobre_por_forma(fj.nombre)
        dosis_val = get_dosis_global(fj.nombre) or 1
        
        for fp in formas_pago:
            LimiteApuesta.objects.create(
                banco=seider, sorteo=s, forma_juego=fj, forma_pago=fp,
                monto_maximo=lim_val, monto_sobrelimite=sobre_val, activo=True
            )
            DosisPago.objects.create(
                banco=seider, sorteo=s, forma_juego=fj, forma_pago=fp,
                monto_por_peso=dosis_val, activo=True
            )
            limites_creados += 1

print(f"✅ Recursos asignados a Seider.")
print(f"✅ Se generaron {limites_creados} Límites y Dosis por defecto.")
