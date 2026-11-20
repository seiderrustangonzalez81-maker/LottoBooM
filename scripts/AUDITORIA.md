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

La comprobación de base de datos viva, rutas Django y renderizado de templates es una fase
dinámica aparte; este reporte lo declara explícitamente como omitido. No se debe interpretar
un audit estático como validación de producción.
