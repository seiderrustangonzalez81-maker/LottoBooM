from roles.models import Fondo, Rol, Postpago
from django.db.models import Sum

print("\n=== 🏦 USUARIOS CON ROL BANCO ===")
for r in Rol.objects.filter(tipo='banco'):
    print(f"Usuario: {r.usuario.username} | Activo: {r.activo}")

print("\n=== 💰 FONDOS POR CLIENTE Y GESTOR (Solo Activos) ===")
fondos = Fondo.objects.filter(activo=True).values('usuario__username', 'asignado_por__username').annotate(total=Sum('monto'))
if not fondos:
    print("⚠️ No hay fondos activos registrados.")
for f in fondos:
    gestor = f['asignado_por__username'] or 'SIN GESTOR (Sistema)'
    print(f"👤 Cliente: {f['usuario__username']} | 💼 Gestor: {gestor} | 💰 Monto: ${f['total']}")

print("\n=== 💳 POSTPAGOS ===")
try:
    for p in Postpago.objects.all():
        print(f"👤 Cliente: {p.cliente.username} | 💰 Saldo: ${p.saldo} | Activo: {p.activo}")
except Exception as e:
    print(f"Error leyendo Postpagos: {e}")

print("\n=== 🔍 ANÁLISIS ESPECÍFICO: SEIDER ===")
# 1. Ver si Seider tiene rol banco
seider = Rol.objects.filter(usuario__username__icontains='seider', tipo='banco').first()
if seider:
    print(f"✅ Seider ({seider.usuario.username}) SÍ tiene rol de banco. Activo: {seider.activo}")
else:
    print("❌ No se encontró rol de 'banco' para Seider (quizás cambió de rol o está inactivo).")

# 2. Ver clientes que tienen fondos asignados por Seider
print("\nClientes con fondos asignados por 'seider':")
f_seider = Fondo.objects.filter(asignado_por__username__icontains='seider', activo=True).values('usuario__username').annotate(total=Sum('monto'))
if not f_seider:
    print("⚠️ Ningún cliente tiene fondos activos asignados a Seider.")
for f in f_seider:
    print(f" 👤 {f['usuario__username']}: ${f['total']}")
