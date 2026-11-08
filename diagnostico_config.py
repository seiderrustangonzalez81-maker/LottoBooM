from django.contrib.auth.models import User
from sorteos.models import Sorteo
from jugadas.models import FormaJuego
from pagos.models import FormaPago
from roles.models import Rol, Subordinacion, ViaPago, RecursoAsignado, ConfiguracionComision, Postpago, LimiteApuesta

print("=== DIAGNÓSTICO DE CONFIGURACIÓN ===")
print(f"Sorteos: {Sorteo.objects.filter(activo=True).count()}")
print(f"Formas de Juego: {FormaJuego.objects.filter(activo=True).count()}")
print(f"Formas de Pago: {FormaPago.objects.filter(activo=True).count()}")
print("-" * 30)
print(f"Bancos: {Rol.objects.filter(tipo='banco', activo=True).count()}")
print(f"Comerciales: {Rol.objects.filter(tipo='comercial', activo=True).count()}")
print(f"Clientes: {Rol.objects.filter(tipo='cliente', activo=True).count()}")
print("-" * 30)
print(f"Subordinaciones (Jefe->Subordinado): {Subordinacion.objects.count()}")
print(f"Vías de Pago registradas (Tarjetas/Cuentas): {ViaPago.objects.count()}")
print(f"Recursos Asignados a Gestores: {RecursoAsignado.objects.count()}")
print(f"Límites de Apuesta: {LimiteApuesta.objects.count()}")
print(f"Configuraciones de Comisión: {ConfiguracionComision.objects.count()}")
print(f"Postpagos (Deudas): {Postpago.objects.count()}")

print("\n=== COMERCIALES Y SUS BANCOS ===")
comerciales = Rol.objects.filter(tipo='comercial', activo=True)
for c in comerciales:
    print(f"Comercial: {c.usuario.username} | Banco asignado: {c.banco_asignado.username if c.banco_asignado else 'NINGUNO'}")
