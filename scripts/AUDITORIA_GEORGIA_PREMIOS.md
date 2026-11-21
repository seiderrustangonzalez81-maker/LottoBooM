# Auditoría crítica: Georgia nocturno y procesamiento de premios

Rama de trabajo: `audit/repository-alignment`. No modificar `main` ni fusionar PR #2 como parte de esta auditoría.

## Hallazgos confirmados en el código de la rama

### Georgia / fechas efectivas
- `sorteos/fixtures/sorteos.json`, sorteo PK 54: nombre `Georgia 11:40 PM`, horario de salida configurado `23:30` en las dos temporadas y cierre de 10 minutos (por tanto, 23:20).
- `scraper.py`: LotteryUSA se identifica como `Georgia 11:34 PM`; alias lo canoniza a `Georgia 11:40 PM`. Georgia usa America/New_York. El cálculo convierte el instante de sorteo a fecha Cuba.
- `jugadas/templates/jugadas/apostar.html`: selección del ID 54 fuerza mañana con `Date.toISOString()`, que puede producir desfase de fecha por zona horaria y usa ID fijo.
- `jugadas/views.py`: normalización para clientes transforma fechas cercanas a hoy; un bloque especial busca el nombre exacto `Georgia 11:34 PM` (no coincide con el fixture) y en la ventana 00:00–00:24 cambia hoy a ayer. Esa combinación es inconsistente con la fecha efectiva de Cuba.
- `sorteos/utils.py`: si no se pasa fecha, aplica otro ajuste especial para `Georgia 11:34 PM` a la fecha anterior, nombre que tampoco coincide con el fixture.
- La ruta de guardar apuestas usa una sola `fecha_apuesta` para todo el POST y la reutiliza en jugadas, boletas, validaciones de pool y comprobaciones de duplicados. Si Georgia tiene una fecha efectiva distinta a los demás sorteos del mismo envío, no se puede corregir solo cambiando el input global del HTML.

### Premios / reprocesamiento
- `resultados/views.py`: `jugada_es_ganadora()` solo implementa de forma explícita fijo y corridos; otras formas devuelven falso. Los corridos incluyen pares consecutivos de Pick4 además de corridos manuales.
- `resultados/procesamiento.py`: procesamiento asíncrono en hilo. Calcula ganadoras, marca perdedoras y crea/paga premios; el conjunto de premios existentes se comprueba solo para las ganadoras nuevas. Una jugada que deje de ganar puede conservar premio existente; un premio existente no se reconcilia por importe/resultado cambiado; los errores de pago pueden dejar premio pendiente y el resultado global se marca completado.
- `resultados/views.py`: modificación y eliminación de resultado tienen reversión financiera manual y no uniforme. En eliminación se intenta crear el movimiento de reversión, pero los fallos de movimiento se capturan y se continúa eliminando premio/resultado.
- La ruta de apuesta tardía invoca reconciliación de premios, pero se debe verificar su comportamiento en resultado ya procesado y premio previamente existente.
- La edición de jugada y boleta necesita una reconciliación del premio anterior antes de cambiar sorteo, fecha, número, forma, monto o destinatario.

## Diseño de corrección requerido (no aplicar reglas de premio ambiguas sin validar)

1. Fecha efectiva **por sorteo**, no una única fecha global cuando un POST incluya varios sorteos.
2. Fuente canónica de identidad para Georgia nocturno, sin nombres exactos contradictorios ni ID fijo en JS.
3. El horario de cierre Georgia debe verificarse con el requisito operativo: 00:24 Cuba, diez minutos antes de 00:34 Cuba. Confirmar que las horas del fixture se interpretan en Cuba antes de cambiar el horario.
4. Cliente y comercial no deben poder alterar fecha/sorteo para evadir cierres; servidor valida.
5. Banco/superadmin pueden autorizar jugadas tardías, pero la fecha del resultado debe ser la exacta y debe disparar reconciliación.
6. Un motor único e idempotente para evaluar, crear, actualizar, invalidar y revertir premios, con control transaccional y trazabilidad de movimientos. No marcar procesamiento completado si quedan errores que requieren recuperación.
7. Definir/validar reglas de Pick2/Pick3/Pick4/Pick5, PF, fijo, corridos, centenas corridas, parlet, VS, posición, tripleta y Superparlet contra las reglas de negocio antes de activar premios automáticos.

## Casos de aceptación mínimos

- Georgia en 23:59 Cuba: fecha efectiva del próximo resultado 00:34 Cuba.
- Georgia en 00:00, 00:23, 00:24: permanece asociado al sorteo del día actual; confirmar política exacta de inclusión del minuto 00:24.
- Georgia 00:25: el siguiente sorteo debe ser el de la fecha siguiente, no aceptar el sorteo ya cerrado.
- En POST con Georgia y otros sorteos, fechas y boletas se asignan individualmente según sorteo.
- Rechazo de fecha alterada por cliente; fecha/rol autorizados por servidor.
- Pick3 234 / Pick4 3456: fijo 34, PF 23, corrido1 34, corrido2 56; validar derivaciones adicionales con reglas.
- Procesar resultado, volver a procesar sin duplicar, modificar resultado, borrar/recrear resultado.
- Insertar jugada tardía por banco y superadmin; editar jugada después de resultados; mover jugada a otro sorteo/fecha.
- Si premio deja de ser válido o cambia su importe, ajustar y revertir movimiento previo de manera trazable.
- Superparlet al modificar/eliminar cualquiera de sus dos resultados.
- Fallo simulado de pago/reversión: estado recuperable, sin perder historial ni marcar éxito engañoso.

## Estado

Este documento registra hallazgos de lectura del código; no certifica pruebas ejecutadas ni una corrección terminada. Los cambios de lógica financiera/fechas deben ir acompañados de tests y ejecución de CI antes de declarar el paquete listo.

## Regla operativa de fecha y ventana para Georgia (establecida por el usuario)

Esta regla prevalece sobre cualquier ajuste automático anterior que reste o sume días por el nombre del sorteo, el ID fijo, la zona horaria del navegador o una fecha enviada por el cliente. Hora de referencia: **America/Havana**.

- **00:00:00–00:26:59:** la apuesta de Georgia corresponde al resultado cuya fecha efectiva es **el día Cuba en curso**. Se acepta hasta el minuto 00:26 inclusive; a partir de 00:27 se cierra esta ventana.
- **00:27:00–01:00:59:** Georgia está cerrado para el ciclo de madrugada. No se acepta a clientes/comerciales ni se traslada silenciosamente al siguiente ciclo. Banco/superadmin pueden cargar fuera de tiempo conforme a sus permisos, pero deben conservar la fecha del ciclo que cargan explícitamente y quedar sujetos a validación/reconciliación.
- **01:01:00–23:59:59:** la apuesta corresponde al **próximo ciclo de Georgia**, cuya fecha efectiva se deriva del instante de sorteo convertido a hora Cuba; el selector debe mostrar la fecha del siguiente ciclo (normalmente el día siguiente), y no una fecha basada en UTC del navegador.
- La regla se aplica únicamente a Georgia nocturno; si el envío contiene otros sorteos, sus fechas no se desplazan por la regla Georgia.
- El backend es autoritativo; el frontend solo refleja el cálculo. Se rechaza la manipulación de fecha para clientes/comerciales y no se debe guardar una fecha de Georgia inferida por `toISOString()` ni por un ID hard-coded.
- La fecha efectiva guardada debe ser estable para jugadas, boletas, premios, resultados, reportes y auditoría. Cambiar el día del sistema no debe reetiquetar registros ya persistidos.

### Pruebas obligatorias de límites

- Cuba 00:00, 00:26:59 → fecha efectiva del día en curso; aceptada.
- Cuba 00:27:00, 00:59:59 y 01:00:59 → ciclo de madrugada cerrado para clientes/comerciales; rechazada sin auto-traslado.
- Cuba 01:01:00 y 23:59:59 → siguiente ciclo Georgia; fecha efectiva del siguiente resultado.
- Verificar cambios de offset de Georgia y Cuba y el override UTC−4 vigente hasta la fecha documentada; conversión debe basarse en el instante del sorteo, no en el offset del navegador.
- POST mixto Georgia + otro sorteo → fecha especial solo para Georgia.

**Estado:** regla de negocio establecida y documentada; aún no certificada como implementada en runtime. La implementación debe resolver fecha por sorteo en backend y actualizar UI/tests antes de declararla completa.
