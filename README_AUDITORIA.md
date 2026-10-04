# Auditoría de Movimientos de Fondo

## Ejecución
    bash /home/LottoBooM/apply_auditoria.sh

## Rollback
    bash /home/LottoBooM/rollback_auditoria.sh

## Cambios
- roles/models.py: +motivo, +saldo_antes, +saldo_despues
- roles/utils.py: _aplicar_ingreso_a_fondo audita pago_deuda
- jugadas/views.py: cancelacion -> ajuste
- roles/views.py: recarga_directa + ajuste, historial_movimientos
- usuarios/views.py: mis_movimientos
- roles/urls.py + usuarios/urls.py: 2 rutas nuevas
- 2 templates nuevos

## Pendientes manuales
1. Sidebar (base.html):
   - roles:historial_movimientos
   - usuarios:mis_movimientos
2. Verificar grep MovimientoFondo en guardar_apuesta
