# Auditoría financiera inicial — LottoBooM

Fecha de inspección: 2026-11-24
Rama inspeccionada: `audit/repository-alignment`
Commit inspeccionado: `92d70291786d540eeafe21c381776a95df8820c0`
PR: #2 (abierto, Draft, sin merge)

## Alcance y límites

Esta revisión se realizó leyendo el código de la rama indicada. Los hallazgos de esta hoja son **hallazgos estáticos**: no se han reproducido todavía en una base de datos de prueba ni en un navegador. No se accedió a producción ni se alteraron apuestas, fondos, premios, resultados o datos reales.

La ejecución de GitHub Actions asociada al commit inspeccionado aparece completada con conclusión `success` (run #729). Esto no equivale a una prueba integral de los flujos financieros.

## Hallazgos prioritarios

### F-01 — Apuesta autorizada puede duplicar el déficit

Archivo: `jugadas/models.py`, `Jugada.procesar_apuesta`.

Cuando un gestor autoriza una apuesta superior al fondo:
1. Se crea una `Deuda` por la diferencia entre apuesta y saldo.
2. Después se descuenta del fondo el importe completo de la apuesta.

Ejemplo estático: saldo $40 y apuesta $65: se registra deuda $25 y el fondo pasa a -$25, en vez de consumir los $40 y dejar el fondo en cero. Esto puede duplicar el déficit contable. Además, el método no muestra una transacción atómica que agrupe deuda, fondo, movimiento y estado de jugada.

**Prioridad: crítica.** Requiere pruebas de regresión antes de cambiar el flujo.

### F-02 — Aprobación de préstamos no protege correctamente la concurrencia

Archivo: `roles/models.py`, `Prestamo.aprobar`.

La consulta `Fondo.objects.select_for_update()` ocurre antes de entrar en `transaction.atomic()`. El bloqueo solicitado no protege la comprobación y descuento como una sola operación. Dos aprobaciones concurrentes pueden evaluar el mismo saldo.

La regla de negocio acordada también exige que el importe aprobado sea estrictamente inferior al fondo disponible en la forma de pago elegida. El código actual rechaza solo cuando el fondo es menor que el importe; permite que ambos valores sean iguales.

**Prioridad: crítica.** La corrección debe bloquear préstamo y fondo dentro de la misma transacción y revalidar saldo antes de descontar.

### F-03 — El prestamista no dispone de un importe aprobado independiente

Archivos: `roles/views.py` y `roles/models.py`.

La solicitud almacena el importe solicitado en `Prestamo.monto`. La vista de aprobación llama a `aprobar()` sin recoger un importe autorizado alternativo. No hay un campo independiente visible en este flujo para conservar importe solicitado e importe finalmente aprobado.

Regla confirmada: el prestamista decide cuánto concede, siempre por debajo del fondo disponible en la forma de pago acordada.

**Prioridad: alta.** Diseñar campo e historial de importe solicitado/aprobado y actualizar pantalla, validación y migración sin perder registros existentes.

### F-04 — Devolución de préstamo puede mezclar formas de pago

Archivo: `roles/models.py`, `Prestamo.pagar_cuota`.

El método suma fondos del prestatario de todas las formas de pago, descuenta recorriendo fondos de varias formas y después acredita al prestamista usando la forma de pago del primer fondo. Además, permite el estado `solicitado`, no bloquea explícitamente la fila del préstamo ni los fondos antes de calcular el saldo.

Esto no respeta la forma de pago acordada y abre riesgos de pagos concurrentes.

**Prioridad: crítica.** La devolución debe descontar únicamente de la forma de pago y relación autorizadas, con bloqueo y transacción atómica.

### F-05 — Tipo de movimiento de préstamo no está declarado en las opciones

Archivo: `roles/models.py`.

`Prestamo.aprobar` crea un `MovimientoFondo` con `tipo='prestamo'`, pero `MovimientoFondo.TIPOS` no declara ese valor. La base de datos puede aceptar el texto, pero formularios, validaciones y reportes basados en choices pueden tratarlo de forma inconsistente.

**Prioridad: alta.** Normalizar el catálogo de tipos y verificar todos los reportes y filtros dependientes.

### F-06 — Los ingresos pueden amortizar préstamos entre clientes automáticamente

Archivo: `roles/utils.py`, `_aplicar_ingreso_a_fondo`.

El helper descuenta automáticamente ingresos de préstamos con estado aprobado, por orden FIFO, y acredita al prestamista. La selección funcional anterior para préstamos entre clientes fue pago manual; esta automatización contradice esa selección y no debe mantenerse como regla por defecto.

También se capturan errores al acreditar al prestamista y al crear movimientos. En ciertos fallos el préstamo puede quedar reducido/saldado aunque el abono al prestamista o el movimiento no se hayan completado.

**Prioridad: crítica.** No cambiar la política hasta terminar el diseño del libro financiero; el comportamiento automático de préstamos entre clientes debe desactivarse o condicionarse explícitamente, preservando los registros existentes.

### F-07 — El helper de ingresos conserva descuentos de Postpago y silencia fallos de movimientos

Archivo: `roles/utils.py`, `_aplicar_ingreso_a_fondo`.

El helper todavía aplica ingresos a saldos de `Postpago` y contiene bloques `except: pass` al crear movimientos de pago de deuda y de ingreso al fondo. El nuevo diseño contempla deudas identificables por acreedor, forma de pago y operación; Postpago no debe eliminarse hasta mapear dependencias, migrar y probar, pero no puede seguir funcionando como una obligación paralela sin conciliación.

**Prioridad: crítica.** Centralizar la amortización en un servicio transaccional y hacer que un fallo contable revierta toda la operación.

### F-08 — Premios existentes pendientes no se reintentan

Archivos: `resultados/procesamiento.py` y `resultados/reconciliacion.py`.

El worker omite cualquier jugada que ya tenga un `Premio`, sin distinguir si está pagado o continúa pendiente tras un error. La reconciliación también devuelve un premio existente sin reintentar su pago.

Por tanto, un fallo de acreditación puede dejar un premio pendiente que no se recupere al reprocesar el resultado.

**Prioridad: crítica.** Separar creación del premio y estado de acreditación; procesar de forma idempotente premios pendientes y mantener una referencia única de pago.

### F-09 — Alcance de destinatarios de recarga requiere restricción por jerarquía

Archivo: `banco/views.py`, `recargar_usuario`.

Los querysets de destinatarios para banco y comercial parten de todos los usuarios activos. El POST verifica contra ese mismo queryset. No se aprecia en esta vista un filtro que limite a un banco a sus comerciales y clientes subordinados, ni a un comercial a sus propios clientes.

Esto debe contrastarse con el modelo de subordinación y con todas las rutas de recarga antes de corregir, pero representa un posible acceso excesivo frente a la regla de privacidad acordada.

**Prioridad: crítica de permisos.** Crear pruebas de aislamiento entre dos bancos, dos comerciales y clientes con varias relaciones.

## Observaciones de modelo y trazabilidad

- `Fondo` identifica usuario, sorteo, forma de pago y asignador, pero su restricción única declarada no incluye `asignado_por`. Debe revisarse la estrategia para separar fondos por relación comercial sin duplicar saldos.
- `Deuda` y `Prestamo` representan obligaciones diferentes y deben conservar su identidad. No fusionar modelos ni borrar datos durante la primera corrección.
- `Deuda` y `Prestamo` conservan campos de vencimiento opcionales. La regla acordada es no exigir fecha límite; las fechas relevantes son realización y devoluciones, con cálculo de tiempo transcurrido.
- La política de amortización automática de deudas de gestor/banco con recargas y premios está acordada en principio. La aplicación a préstamos entre clientes sigue siendo manual según la selección funcional previa, hasta nueva confirmación.
- Debe confirmarse el alcance exacto de la amortización entre varios gestores y el tratamiento de bonos antes de implementar el motor central.

## Orden recomendado de corrección

1. Añadir pruebas de regresión con base de datos aislada para F-01 a F-09.
2. Corregir primero los límites transaccionales y la idempotencia, sin cambiar todavía reglas comerciales.
3. Separar los libros de fondo, deuda de gestor/banco y préstamo entre clientes.
4. Implementar los importes solicitado/aprobado y pagos manuales de préstamos.
5. Restringir permisos y probar aislamiento de relaciones.
6. Hacer que el reprocesamiento de premios recupere pendientes sin duplicar pagos.
7. Verificar rectificaciones, cuadres y reportes afectados.
8. Ejecutar la suite completa y pruebas de navegador antes de considerar cualquier despliegue.

## Estado

- Inspección estática inicial: realizada.
- Reproducción en DB aislada: pendiente.
- Correcciones financieras: pendientes de pruebas de regresión.
- Cambios en producción/datos reales: ninguno.
- Merge y despliegue: no realizados ni autorizados.
