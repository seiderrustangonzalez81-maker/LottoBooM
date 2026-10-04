from pathlib import Path
import ast

p = Path("/home/LottoBooM/roles/models.py")
src = p.read_text(encoding="utf-8")

if "FIX_PRESTAMO_APROBAR_V1" in src:
    print("SKIP: ya aplicado")
    raise SystemExit(0)

# Reemplazar el método aprobar completo (líneas 777-837)
inicio = src.find("    def aprobar(self, aprobado_por=None):")
if inicio < 0:
    print("ERROR: no encontré def aprobar")
    raise SystemExit(1)

# Buscar el final del método (siguiente def)
fin = src.find("    def pagar_cuota(self, monto):", inicio)
if fin < 0:
    print("ERROR: no encontré el siguiente método")
    raise SystemExit(1)

nuevo_metodo = '''    def aprobar(self, aprobado_por=None):
        """FIX_PRESTAMO_APROBAR_V1: respeta forma_pago del préstamo."""
        from django.db import transaction
        if self.estado != 'solicitado':
            return False, "Este préstamo ya no está en estado de solicitud"

        if not self.forma_pago_id:
            return False, "El préstamo no tiene forma de pago definida."

        # Fondo del prestamista en ESA forma de pago (con ese gestor)
        fondo_prest = Fondo.objects.select_for_update().filter(
            usuario=self.prestamista,
            forma_pago=self.forma_pago,
            activo=True,
        )
        if self.gestor_id:
            fondo_prest = fondo_prest.filter(asignado_por=self.gestor)
        fondo_prest = fondo_prest.first()

        if not fondo_prest or fondo_prest.monto < self.monto:
            disp = fondo_prest.monto if fondo_prest else 0
            return False, f"El prestamista no tiene fondos suficientes en {self.forma_pago.nombre}. Disponible: ${disp}"

        with transaction.atomic():
            # 1. Descontar del fondo del prestamista
            fondo_prest.monto -= self.monto
            fondo_prest.save(update_fields=['monto'])

            # 2. Acreditar al solicitante en la misma forma de pago / gestor
            fondo_sol, _ = Fondo.objects.select_for_update().get_or_create(
                usuario=self.solicitante,
                forma_pago=self.forma_pago,
                asignado_por=self.gestor,
                defaults={'monto': 0, 'activo': True},
            )
            fondo_sol.monto += self.monto
            fondo_sol.activo = True
            fondo_sol.save(update_fields=['monto', 'activo'])

            # 3. Movimiento
            MovimientoFondo.objects.create(
                emisor=self.prestamista,
                receptor=self.solicitante,
                forma_pago=self.forma_pago,
                monto=self.monto,
                tipo='prestamo',
                estado='confirmado',
                datos_transferencia={
                    'prestamo_id': self.id,
                    'tipo_operacion': 'prestamo_entre_clientes',
                    'gestor': self.gestor.username if self.gestor else None,
                },
                nota=f"Préstamo de {self.prestamista.username} a {self.solicitante.username}",
                saldo_antes=fondo_prest.monto + self.monto,
                saldo_despues=fondo_prest.monto,
            )

            # 4. Estado
            self.estado = 'aprobado'
            self.fecha_aprobacion = timezone.now()
            self.aprobado_por = aprobado_por
            self.saldo_pendiente = self.monto
            self.save(update_fields=['estado', 'fecha_aprobacion', 'aprobado_por', 'saldo_pendiente'])

            # 5. Notificaciones
            _crear_notificacion(
                usuario=self.solicitante,
                tipo='prestamo',
                mensaje=f"💰 Préstamo de ${self.monto} en {self.forma_pago.nombre} aprobado por {self.prestamista.username}.",
                datos={'prestamo_id': self.id, 'monto': float(self.monto), 'url_detalle': '/roles/mis-prestamos/'},
                prioridad='alta',
                categoria='financiera'
            )
            _crear_notificacion(
                usuario=self.prestamista,
                tipo='prestamo',
                mensaje=f"💰 Has otorgado un préstamo de ${self.monto} a {self.solicitante.username}. Se cobrará automáticamente de sus próximos ingresos en {self.forma_pago.nombre}.",
                datos={'prestamo_id': self.id, 'monto': float(self.monto), 'url_detalle': '/roles/mis-prestamos/'},
                prioridad='alta',
                categoria='financiera'
            )
        return True, "Préstamo aprobado y fondos transferidos."

'''

src = src[:inicio] + nuevo_metodo + src[fin:]

try:
    ast.parse(src)
except SyntaxError as e:
    print(f"ERROR sintaxis: {e}")
    raise SystemExit(1)

p.write_text(src, encoding="utf-8")
print("OK: aprobar() reescrito con FIX_PRESTAMO_APROBAR_V1")
