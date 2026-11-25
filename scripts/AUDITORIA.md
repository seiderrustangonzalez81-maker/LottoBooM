# Auditoría LottoBooM (estática y de solo lectura)

Ejecutar desde la raíz del repositorio:

```bash
python scripts/auditar_sorteos.py
python scripts/auditar_sorteos.py --json audit-report.json
python scripts/auditar_sorteos.py --strict
python -m unittest discover -s scripts/tests -v
```

Compara catálogo de sorteos y formas entre `scraper.py`, `config_sorteos_formas.json`,
`sorteos_formas.csv`, fixture Django, choices de formulario y `resultados.json`.
También verifica sintaxis Python, IDs HTML repetidos y reporta módulos sospechosos vacíos.

**Seguridad:** no conecta a la base de datos, no hace scraping, no modifica registros ni
corrige automáticamente nombres/horarios. Las divergencias se reportan como warnings para
revisión, porque horarios y alias pueden ser ambiguos. `--strict` convierte warnings en
fallo de salida; CI inicialmente conserva warnings como reporte para evitar bloquear el
scraper mientras se establece una línea base.

La base de datos viva y el renderizado con datos reales quedan fuera. CI ejecuta aparte un smoke audit Django (checks del sistema, importación de modelos/forms/views/urls, carga de templates y resolución del URL root) con entorno aislado y sin conexión a DB. No equivale a pruebas de render de vistas con datos ni valida producción.

## Pruebas de la pantalla Apostar y cobros

CI añade estas comprobaciones aisladas:

```bash
node --test scripts/tests/test_apostar_text_validator.js
node --test scripts/tests_js/*.test.cjs
```

- Valida texto pegado y bloquea líneas incompletas o tokens desconocidos.
- Comprueba que el botón Procesar se deshabilite con texto vacío, errores, sorteos cargando, pestañas ausentes o formas no habilitadas.
- Verifica el enrutamiento actualmente soportado a Tradicional y Pick 3, y que los tipos de fila estándar, Posiciones y VS puedan mapearse a sus estructuras sin asumir campos inexistentes.
- Compara los totales calculados de las tablas con la suma de los items que realmente se recolectan para guardar (incluye Pick2, PF, Fijo, Corridos, Parlet, Candado, Pick3/4/5, Centenas, VS, Posiciones, Tripleta y Solo Parlet).
- Compila los bloques JavaScript inline de `apostar.html` después de sustituir las etiquetas Django.
- El cobro de premios se ejecuta con `transaction.atomic()` y `select_for_update()`; pruebas simuladas comprueban el bloqueo y que un premio ya pagado no vuelva a acreditar fondos.

Estas pruebas no ejecutan un navegador real, no prueban concurrencia contra el motor de producción y no usan apuestas, fondos ni premios reales. Las formas de texto que aún no tienen gramática explícita se rechazan en vez de descartarse silenciosamente.



## Correcciones seguras aplicadas en la rama de revisión

- El scraper ahora canoniza aliases inequívocos de feeds en el campo `sorteo_nombre` y conserva `nombre_fuente` para trazabilidad. La hora fuente sigue usándose para calcular la fecha del resultado.
- Se añadió Anguila 10 PM a `SORTEOS_ESPERADOS`.
- El fixture Loteka (PK 42) se renombró de Loteka 1:30 PM a Loteka 7:50 PM, preservando PK, horarios por día, formas y estado; el horario dominical ya era 19:50.
- Se acotó el override UTC-4 de Cuba a 2026-11-01–2027-11-07; las fechas anteriores vuelven a consultar tzdata.
- Choices globales de Django no usados en matriz son informativos, no errores; no se eliminan.

No se corrigen horarios oficiales sin verificar ni se eliminan sorteos como Real Noche.


## Auditoría integral final — 2026-11-24

**Snapshot funcional auditado:** `cdb532fb2eff85175e4de72f40123e5244b137ae` (`audit/repository-alignment`).  
**CI exacto:** [run #717 / 45361697887](https://github.com/seiderrustangonzalez81-maker/LottoBooM/actions/runs/45361697887) — SUCCESS.

### Checklist persistente

- [x] **A. Parser/entrada:** 63 pruebas Node pasan; líneas físicas y diagnósticos se preservan; errores y modalidades no soportadas bloquean; destinos y formas se validan. La muestra de estrés de 24 líneas contabiliza 16 aceptadas y 8 rechazadas explícitamente, sin pérdida silenciosa. La muestra válida multi-tab genera 21 filas en 12 destinos.
- [x] **B. UI Apostar (estático/automatizado):** semáforo y estado `disabled` nativo; prerequisitos de texto, modo Procesar, carga, sorteo y pestaña; modos Replicar/Procesar excluyentes; errores visibles; cambios invalidan la habilitación; guardas de procesamiento y reintento cubiertas.
- [x] **C. Staging/transacción:** frontend prepara destinos antes de mutar, restaura snapshots si falla el render, protege carga/reintento, confirma reemplazos y preserva tablas ajenas. Backend de guardar apuesta valida todas las tablas/sorteos y ejecuta creación, pool y ajustes dentro de `transaction.atomic()`; fallos por excepción revierten.
- [x] **D. Tablas/cálculos (automatizado):** se compara el total de tabla con los items realmente recolectados; las pruebas cubren Pick2, PF, Fijo, Corridos, Parlet, Candado, Pick3/4/5, Centenas, VS, Posiciones, Tripleta y variantes. Se conserva la función nativa de recolección/cálculo como fuente de los items enviados.
- [~] **E. Borrar/editar/restaurar/persistir:** cubiertos por tests el borrado de fila con guardado del borrador, restauración tras carga de sorteos, snapshots de edición con premios, reemplazo y conciliación de fondo. Falta interacción real de navegador, comprobación manual de deshacer/confirmaciones y comparación del payload final desde navegador.
- [x] **F. Roles/estados (servidor):** auditor bloqueado; sorteo abierto permitido a roles operativos autorizados por vista; cerrado solo banco/superadmin; salido/no programado bloqueado. Backend revalida el estado y los permisos para cada sorteo, también en Superparlet. Tests unitarios de permisos pasan.
- [x] **G. Django/backend (CI):** system checks OK; imports de modelos/forms/views/urls OK; 209 templates descubiertos y cargados; URL resolver OK; 35 tests de `jugadas` pasan. El smoke no renderiza todas las vistas con datos reales y no conecta a DB de producción.
- [~] **H. Catálogo/calendario/timezone:** límites UTC del override Cuba (2026-11-01 05:00Z a 2027-11-07 05:00Z, fin exclusivo), fechas/horas naive y aware y cruce nocturno de Georgia tienen pruebas. Persisten 4 warnings del auditor: `Real Noche` extra en fixture; URL de `Tennessee 6:30 PM` no alineada al catálogo; 15 nombres de resultados sin resolver; `sorteos/constants.py` y `rescue.db` vacíos/sospechosos. No se inventan alias ni horarios.
- [~] **I. Scraper:** revisión estática de Playwright, escritura atómica de `resultados.json`, reintentos fijos y workflow. Pendiente validar fuentes/horarios con evidencia oficial y política de cada sitio; el código visible usa esperas/reintentos fijos de 2–4 s y no se verificó manejo de `Retry-After`. No se ejecutó scraping en vivo ni se evadieron CAPTCHA/anti-bot. El cron `*/5` del workflow no se probó en esta rama (los schedules de Actions se ejecutan desde la rama por defecto).
- [~] **J. Premios/reversos:** el endpoint de cobro manual usa `transaction.atomic()` y `select_for_update()`, limita por propietario y evita acreditar un premio ya pagado; tests mock verifican el orden y la idempotencia del endpoint. Riesgo pendiente: el worker y `reconciliar_premio_jugada` hacen comprobación y creación de `Premio` sin una restricción única por jugada ni un bloqueo común probado; no se puede añadir una constraint con seguridad sin auditar duplicados históricos. Además, `jugada_es_ganadora` solo evalúa `fijo` y `corridos`; las demás modalidades devuelven no ganadora (Superparlet tiene una ruta separada). No hay evidencia de cálculo de premios para Pick2/Pick3/Pick4/Pick5, PF, Parlet/Candado, VS, Posiciones, Tripleta ni Centenas. Esto bloquea pruebas de premios y preparación para producción, pero no la prueba aislada de captura/procesamiento de Apostar. No se consultó DB real ni se ejecutaron premios.
- [~] **K. Calidad/CI del snapshot:** auditor estático 0 errores / 4 warnings / 3 informativos; Django smoke OK; 35 tests Django; 63 tests parser Node; 84 tests Python unittest; 24 tests JavaScript. El CI del commit `cdb532f` terminó SUCCESS. Un test de zona horaria falló inicialmente por un doble `Intl.DateTimeFormat` no constructible en el VM; se corrigió el test harness y el CI posterior pasó. El CI más reciente del HEAD `2b59abb` también terminó SUCCESS. **Pendiente:** no se revisó línea por línea el diff completo de los 405 commits del PR; la comparación con `main` sigue divergida (405 ahead / 153 behind), sin rebase ni merge. Esto debe resolverse antes de integrar el PR, no antes de probar Apostar de forma aislada.

### Límites y siguiente paso

La rama se comparó con `main` sin rebase/merge: estaba 399 commits ahead y 153 behind al snapshot. PR #2 sigue abierto en Draft y no mergeado. No se desplegó ni se usó DB de producción.  
**Listo para prueba práctica controlada de Apostar, no para producción.** Pendiente: navegador móvil real, payload/endpoint en DB aislada y riesgos H/I/J indicados arriba. La preparación manual debe verificar cliente/gestor, forma de pago, un sorteo y varios, Replicar, cada modalidad, error rojo, prerequisito ámbar, verde, reemplazo cancelar/confirmar, borrar/restaurar borrador y totales antes de enviar solo al entorno de prueba.


### Actualización de cobertura — Candado y semáforo (2026-11-24)

- Se detectó que una muestra de prueba y la documentación presentaban Candado como si pudiera usarse solo, aunque la validación de filas exige Parlet activo y Candado = Parlet × número de combinaciones.
- Se corrigió la muestra de estrés y el ejemplo documentado: `13 14 15 parlet 10 candado 30` (tres pares) y `12 34 56 parlet 2 candado 6`.
- Se añadieron regresiones de UI en vivo: Candado desajustado mantiene el semáforo rojo/deshabilitado; el importe espejo correcto permite verde. La validación existente bloquea el envío y la prevalidación de destinos bloquea Procesar.
- CI #720 del commit `fb9dadd`: SUCCESS (63 Node, 84 Python unittest, 24 JS, 35 Django). CI #721 del commit de documentación `a60e4d3`: SUCCESS.


## Continuidad de auditoría — 25 de noviembre de 2026

**Base comparativa:** HEAD previo de `audit/repository-alignment` = `0aa050589a28e8fe91fd4571ea6bf8fa6efc00c7` (corte del 24 de noviembre). Esta revisión se hizo por lectura del código en GitHub; no se ejecutó código financiero ni se accedió a bases de datos.

### Estado de rama, PR y CI

- Antes de esta actualización documental, la rama seguía exactamente en `0aa050589a28e8fe91fd4571ea6bf8fa6efc00c7`: comparación idéntica, 0 commits por delante y 0 por detrás del corte anterior. No había commits funcionales nuevos en la rama desde ese corte.
- PR #2 continúa abierto, Draft y sin merge. GitHub reporta actualmente `mergeable=true`; esto no significa que esté aprobado ni que deba integrarse.
- El CI #731 (run `45486037124`) del HEAD anterior terminó SUCCESS. Se verificaron sus pasos: auditoría estática, instalación de dependencias, smoke Django sin DB de producción, suite Django de `jugadas` con SQLite de prueba, parser Node, unittest, pruebas JavaScript y publicación del artefacto; todos terminaron SUCCESS.
- `main` avanzó hasta `4a48791b63ca3b918789eddc634ad27298dd0464` (`Update resultados`). La comparación actual indica 420 commits de la rama de auditoría por delante y 192 por detrás de `main`. No se hizo rebase, merge ni actualización de `main`. Las actualizaciones automáticas de resultados en `main` no se cuentan como avance de esta auditoría.

### Hallazgos de premios revalidados

1. `resultados/procesamiento.py`: el worker consulta premios existentes antes de crear, pero no bloquea una fila común de `Jugada` ni vuelve a comprobar la existencia bajo un bloqueo. Dos ejecuciones concurrentes pueden superar el chequeo previo. La creación está dentro de un `transaction.atomic()` por premio, pero no hay una restricción única por `Premio.jugada` en el modelo.
2. Si falla `_aplicar_ingreso_a_fondo`, el worker captura la excepción, deja el premio pendiente y puede marcar el resultado como `completado`. En una ejecución posterior, los premios ya existentes se omiten, sin reintentar automáticamente los que siguen pendientes.
3. `resultados/reconciliacion.py` consulta si existe el premio fuera de una transacción/bloqueo común y luego crea. Si ya existe, devuelve ese registro sin distinguir entre pendiente y pagado ni reintentar su acreditación.
4. El worker y la reconciliación son dos rutas de creación que deben compartir la misma estrategia de exclusión/idempotencia. No se añadió una constraint ni una migración: antes hay que revisar duplicados históricos en una DB aislada y diseñar recuperación de pendientes.
5. El endpoint manual `solicitar_cobro` sí conserva `transaction.atomic()` y `select_for_update()`; el test existente verifica el orden con mocks. Esto no cubre concurrencia real ni el worker/reconciliación.

**Prioridad:** crítica. Pendiente prueba de concurrencia con el motor de DB de destino, reintento de premio pendiente, fallo a mitad de acreditación, reprocesamiento y resultado corregido/revertido. No se inventan multiplicadores ni reglas de acierto.

### Hallazgos financieros revalidados

- `Prestamo.aprobar()`: el `select_for_update()` del fondo se evalúa antes de entrar en `transaction.atomic()`; el importe igual al saldo se permite, aunque la regla acordada exige que el aprobado sea estrictamente menor. La función usa `monto` como importe solicitado/aprobado, sin campo separado visible para la decisión del prestamista.
- `Prestamo.pagar_cuota()`: calcula saldo sobre varios fondos, no bloquea previamente el préstamo y todos los fondos, y acredita al prestamista usando la primera forma de pago encontrada. No garantiza la forma de pago acordada para el préstamo.
- `_aplicar_ingreso_a_fondo()`: la consulta de fondo y el `get_or_create` se basan en cliente/forma de pago, no en gestor; el modelo `Fondo` tiene `unique_together(usuario, sorteo, forma_pago)`, sin incluir `asignado_por`. La estructura actual no representa fondos independientes por cliente–gestor–forma de pago como exige la regla de no mezclar gestores. Resolverlo requiere diseño de datos y migración planificada; no se ejecuta aquí.
- En ese mismo helper se absorben excepciones al crear movimientos de pago de Postpago, al acreditar al prestamista y al crear movimientos de préstamo/ingreso. El saldo o préstamo puede cambiar aunque falte el asiento correspondiente. Requiere transacción y pruebas de fallo inducido; no basta con que el helper retorne.
- El helper aplica amortización FIFO de préstamos al recibir ingresos cuando `_skip_prestamos=False`; las rutas de premios inspeccionadas no pasan ese parámetro. La regla de negocio sobre si premios/recargas amortizan automáticamente préstamos cliente–cliente sigue sin confirmación final. El código actual no se toma como decisión de negocio.
- En `solicitar_cobro`, la llamada al helper pasa `gestor=request.user`, mientras el worker y la reconciliación usan `jugada.destinatario or jugada.usuario`. Para una jugada cuyo destinatario sea distinto del cliente, el cobro manual puede consultar otro registro de Postpago. Debe probarse y alinearse con la regla de acreedor/gestor antes de cambiarlo.
- `banco.views.recargar_usuario`: los querysets de destinatarios para banco y comercial incluyen usuarios activos en general; el POST solo comprueba pertenencia a ese mismo queryset amplio. No se observa aislamiento por clientes subordinados del banco/comercial en esta vista.

### Decisión de seguridad de esta revisión

No se modificó lógica de premios, fondos, préstamos ni permisos porque el entorno disponible en esta sesión permite inspección GitHub, pero no ejecutar la aplicación con una DB aislada del motor de destino ni pruebas de concurrencia. Tampoco se consultaron datos reales, se ejecutaron migraciones o se alteraron saldos, apuestas, premios o resultados. La única modificación de esta sesión es este registro documental en la rama de auditoría.

### Siguiente secuencia segura

1. Preparar DB aislada y fixtures sintéticos para premio duplicado, premio pendiente, fallo de acreditación y reproceso concurrente.
2. Definir bloqueo común de `Jugada` en worker y reconciliación; después decidir constraint única solo tras comprobar duplicados históricos en una copia de prueba.
3. Probar atomicidad de cada asiento en `_aplicar_ingreso_a_fondo`, sin excepciones silenciosas.
4. Resolver la decisión pendiente sobre amortización automática de préstamos cliente–cliente.
5. Diseñar la clave de fondos/acreedor por gestor y el alcance de recargas banco/comercial antes de migrar.
6. Corregir préstamos y permisos con pruebas de concurrencia/roles; no desplegar ni fusionar hasta completar revisión y CI.
