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
- [~] **J. Premios/reversos:** el endpoint de cobro manual usa `transaction.atomic()` y `select_for_update()`, limita por propietario y evita acreditar un premio ya pagado; tests mock verifican el orden y la idempotencia del endpoint. Riesgo pendiente: el worker y `reconciliar_premio_jugada` hacen comprobación y creación de `Premio` sin una restricción única por jugada ni un bloqueo común probado; no se puede añadir una constraint con seguridad sin auditar duplicados históricos. No se consultó DB real ni se ejecutaron premios.
- [x] **K. Calidad/CI del snapshot:** auditor estático 0 errores / 4 warnings / 3 informativos; Django smoke OK; 35 tests Django; 63 tests parser Node; 84 tests Python unittest; 24 tests JavaScript. El CI del commit `cdb532f` terminó SUCCESS. Un test de zona horaria falló inicialmente por un doble `Intl.DateTimeFormat` no constructible en el VM; se corrigió el test harness y el CI posterior pasó.

### Límites y siguiente paso

La rama se comparó con `main` sin rebase/merge: estaba 399 commits ahead y 153 behind al snapshot. PR #2 sigue abierto en Draft y no mergeado. No se desplegó ni se usó DB de producción.  
**Listo para prueba práctica controlada de Apostar, no para producción.** Pendiente: navegador móvil real, payload/endpoint en DB aislada y riesgos H/I/J indicados arriba. La preparación manual debe verificar cliente/gestor, forma de pago, un sorteo y varios, Replicar, cada modalidad, error rojo, prerequisito ámbar, verde, reemplazo cancelar/confirmar, borrar/restaurar borrador y totales antes de enviar solo al entorno de prueba.
