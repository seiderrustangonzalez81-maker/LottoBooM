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
