#!/usr/bin/env python3
"""Read-only repository audit for draw catalog/configuration alignment.

Usage: python scripts/auditar_sorteos.py [--strict] [--json report.json]
No database writes, scraping, network calls, or automatic corrections.
"""
from __future__ import annotations
import argparse, ast, csv, json, re, sys, unicodedata
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DAYS = {"lunes", "martes", "miercoles", "miércoles", "jueves", "viernes", "sabado", "sábado", "domingo"}
ALIASES = {
    "anguilla 8am": "anguila 8 am", "anguilla 9am": "anguila 9 am",
    "anguilla 10am": "anguila 10 am", "anguilla 11am": "anguila 11 am",
    "anguilla 12pm": "anguila 12 pm", "anguilla 1pm": "anguila 1 pm",
    "anguilla 2pm": "anguila 2 pm", "anguilla 3pm": "anguila 3 pm",
    "anguilla 4pm": "anguila 4 pm", "anguilla 5pm": "anguila 5 pm",
    "anguilla 6pm": "anguila 6 pm", "anguilla 7pm": "anguila 7 pm",
    "anguilla 8pm": "anguila 8 pm", "anguilla 9pm": "anguila 9 pm",
    "anguilla 10pm": "anguila 10 pm",
    "haiti bolet 9:30 am": "haiti 1", "haiti bolet 10:30 am": "haiti 2",
    "haiti bolet 1:30 pm": "haiti 3", "haiti bolet 4:30 pm": "haiti 4",
    "haiti bolet 5:30 pm": "haiti 5", "haiti bolet 6:30 pm": "haiti 6",
    "el quemaito mayor": "quemaito", "el quinielon dia": "quinielon",
    "la primera": "primera", "lotedom": "lotedom",
}
def norm(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii","ignore").decode().lower()
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()
    s = re.sub(r"\b(\d{1,2})(am|pm)\b", r"\1 \2", s)
    return re.sub(r"\s+", " ", s)
def canon(s):
    n = norm(s)
    return next((norm(target) for alias, target in ALIASES.items() if norm(alias) == n), n)
def load_json(path):
    try: return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e: raise ValueError(f"{path.relative_to(ROOT)}: {e}")
def add(items, sev, code, message, path=None):
    items.append({"severity":sev,"code":code,"message":message, **({"path":path} if path else {})})
def read_csv_matrix(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))
def python_constants(path, names):
    tree=ast.parse(path.read_text(encoding="utf-8"))
    vals={}
    for node in tree.body:
        if isinstance(node,(ast.Assign,ast.AnnAssign)):
            targets=node.targets if isinstance(node,ast.Assign) else [node.target]
            value=node.value
            for target in targets:
                if isinstance(target,ast.Name) and target.id in names:
                    try: vals[target.id]=ast.literal_eval(value)
                    except Exception: pass
    return vals
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--strict", action="store_true", help="warnings also produce exit code 1")
    ap.add_argument("--json", metavar="FILE", help="write machine-readable report")
    args=ap.parse_args()
    report={"title":"Auditoría de alineación LottoBooM","findings":[],"counts":{},"sources":{}}
    findings=report["findings"]
    expected_file=ROOT/"scraper.py"
    matrix_json=ROOT/"config_sorteos_formas.json"
    matrix_csv=ROOT/"sorteos_formas.csv"
    fixture=ROOT/"sorteos/fixtures/sorteos.json"
    results=ROOT/"resultados.json"

    # Expected names and scraper source names are read from Python AST (no execution).
    expected=set(); scraper_keys=set()
    if expected_file.exists():
        try:
            constants=python_constants(expected_file,{"SORTEOS_ESPERADOS","URLS_MULTI"})
            expected=set(constants.get("SORTEOS_ESPERADOS",[]))
            scraper_keys=set((constants.get("URLS_MULTI") or {}).keys())
            report["sources"]["scraper_expected_count"]=len(expected)
            report["sources"]["scraper_url_keys_count"]=len(scraper_keys)
        except Exception as e: add(findings,"error","SCRAPER_PARSE",str(e),"scraper.py")
    else: add(findings,"error","MISSING_SOURCE","No se encontró scraper.py")

    config={}
    if matrix_json.exists():
        try:
            config=load_json(matrix_json)
            if not isinstance(config,dict): raise ValueError("Se esperaba objeto JSON nombre->formas")
            report["sources"]["config_draws"]=len(config)
        except Exception as e: add(findings,"error","CONFIG_INVALID",str(e),matrix_json.name)
    else: add(findings,"error","MISSING_CONFIG","Falta config_sorteos_formas.json")
    csv_rows=[]
    if matrix_csv.exists():
        try:
            csv_rows=read_csv_matrix(matrix_csv)
            csv_names={r.get("nombre_sorteo","").strip() for r in csv_rows if r.get("nombre_sorteo")}
            report["sources"]["csv_draws"]=len(csv_names)
            if len(csv_names)!=len(csv_rows): add(findings,"warning","CSV_DUPLICATE","Hay nombres duplicados o vacíos en CSV",matrix_csv.name)
        except Exception as e: add(findings,"error","CSV_INVALID",str(e),matrix_csv.name)
    else: add(findings,"error","MISSING_CSV","Falta sorteos_formas.csv")

    fixture_names=set(); fixture_forms={}
    if fixture.exists():
        try:
            data=load_json(fixture)
            for item in data:
                if item.get("model")=="sorteos.sorteo":
                    name=item.get("fields",{}).get("nombre","")
                    if name: fixture_names.add(name); fixture_forms[name]=set(item.get("fields",{}).get("formas_juego",[]))
            report["sources"]["fixture_draws"]=len(fixture_names)
        except Exception as e: add(findings,"error","FIXTURE_INVALID",str(e),str(fixture.relative_to(ROOT)))
    else: add(findings,"error","MISSING_FIXTURE","Falta fixture de Sorteo")

    def compare(label, source, reference, file=None):
        a={canon(x) for x in source}; b={canon(x) for x in reference}
        missing=sorted(b-a); extra=sorted(a-b)
        if missing: add(findings,"warning","MISSING_NAMES",f"{label}: faltan {len(missing)}: {', '.join(missing[:25])}",file)
        if extra: add(findings,"warning","EXTRA_NAMES",f"{label}: sobran {len(extra)}: {', '.join(extra[:25])}",file)
        report["sources"][label]={"count":len(source),"missing_vs_reference":missing,"extra_vs_reference":extra}
    # CSV is the declared ordered catalog used for cross-source comparisons.
    if csv_rows:
        csv_names={r.get("nombre_sorteo","").strip() for r in csv_rows if r.get("nombre_sorteo")}
        if config: compare("JSON_vs_CSV",config.keys(),csv_names,matrix_json.name)
        if fixture_names: compare("Fixture_vs_CSV",fixture_names,csv_names,str(fixture.relative_to(ROOT)))
        if expected: compare("Scraper_expected_vs_CSV",expected,csv_names,"scraper.py")
        if scraper_keys:
            unknown_url_keys=sorted(x for x in scraper_keys if canon(x) not in {canon(y) for y in csv_names})
            report["sources"]["scraper_url_keys"]={"count":len(scraper_keys),"unknown_vs_catalog":unknown_url_keys}
            if unknown_url_keys: add(findings,"warning","SCRAPER_URL_UNKNOWN",f"URLS_MULTI con nombre no reconocido: {unknown_url_keys}","scraper.py")
    # Forms consistency across JSON, CSV, fixture and Django choices.
    csv_forms=set()
    if csv_rows:
        for row in csv_rows:
            for key,value in row.items():
                if key!="nombre_sorteo" and str(value).strip().lower() in {"si","sí","1","true","x"}: csv_forms.add(norm(key))
    config_forms={norm(x) for forms in config.values() if isinstance(forms,list) for x in forms}
    fixture_form_keys={norm(x) for forms in fixture_forms.values() for x in forms}
    forms_file=ROOT/"sorteos/forms.py"
    django_choices=set()
    if forms_file.exists():
        text=forms_file.read_text(encoding="utf-8")
        django_choices={norm(k) for k in re.findall(r"\(\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]",text)}
    if csv_forms and config_forms and csv_forms!=config_forms:
        add(findings,"warning","FORM_MATRIX_MISMATCH",f"Formas CSV/JSON difieren. CSV no-blank={len(csv_forms)}, JSON={len(config_forms)}", "sorteos_formas.csv")
    if fixture_form_keys and config_forms:
        absent=sorted(fixture_form_keys-config_forms); added=sorted(config_forms-fixture_form_keys)
        if absent or added: add(findings,"warning","FORM_FIXTURE_MISMATCH",f"Fixture vs matriz: fixture extra={absent[:20]}; matriz extra={added[:20]}","sorteos/fixtures/sorteos.json")
    if django_choices and config_forms:
        missing=sorted(config_forms-django_choices); unused=sorted(django_choices-config_forms)
        if missing or unused: add(findings,"warning","FORM_CHOICES_MISMATCH",f"Choices Django vs catálogo: no definidas={missing}; choices no usadas={unused}","sorteos/forms.py")
    report["sources"]["forms"]={"csv":len(csv_forms),"json":len(config_forms),"fixture":len(fixture_form_keys),"django_choices":len(django_choices)}

    # Results names: aliases are normalized, unknowns and duplicate draw/date are reported.
    if results.exists():
        try:
            data=load_json(results)
            seen=Counter(); unknown=set(); date_errors=[]
            catalog={canon(x) for x in (csv_names if csv_rows else config.keys())}
            for rec in data:
                name=rec.get("sorteo_nombre","")
                date=rec.get("fecha","")
                key=(canon(name),date)
                seen[key]+=1
                if key[0] not in catalog: unknown.add(name)
                if date:
                    try: from datetime import date as _date; _date.fromisoformat(date)
                    except Exception: date_errors.append(f"{name}: {date}")
            duplicates=[f"{n} @ {d}" for (n,d),c in seen.items() if c>1]
            if duplicates: add(findings,"warning","RESULT_DUPLICATES",f"Duplicados sorteo/fecha: {duplicates[:20]}","resultados.json")
            if unknown: add(findings,"warning","RESULT_UNKNOWN_NAMES",f"Nombres de resultados no reconocidos ({len(unknown)}): {sorted(unknown)[:25]}","resultados.json")
            if date_errors: add(findings,"error","RESULT_BAD_DATES",f"Fechas inválidas: {date_errors[:10]}","resultados.json")
            report["sources"]["results"]={"records":len(data),"unknown_names":sorted(unknown),"duplicate_keys":duplicates,"invalid_dates":date_errors}
        except Exception as e: add(findings,"error","RESULTS_INVALID",str(e),"resultados.json")

    # Template scan: duplicate IDs and static catalog references, with unknowns left as review items.
    templates=list(ROOT.rglob("*.html"))
    duplicate_ids=[]
    static_draw_refs=set()
    catalog_names=(csv_names if csv_rows else set(config.keys()))
    catalog_norm={canon(x):x for x in catalog_names}
    for p in templates:
        try: content=p.read_text(encoding="utf-8")
        except Exception: continue
        ids=re.findall(r'\bid\s*=\s*["\']([^"\']+)["\']',content)
        dups=[x for x,c in Counter(ids).items() if c>1]
        if dups: duplicate_ids.append(f"{p.relative_to(ROOT)}: {dups[:8]}")
        # Only recognize explicit literal draw labels inside template text/attributes.
        for name in catalog_names:
            if name and name.lower() in content.lower(): static_draw_refs.add(name)
    if duplicate_ids: add(findings,"warning","HTML_DUPLICATE_IDS",f"IDs HTML duplicados en {len(duplicate_ids)} templates; ejemplos: {duplicate_ids[:15]}")
    report["sources"]["templates"]={"files":len(templates),"templates_with_catalog_literals":len(static_draw_refs),"duplicate_id_files":duplicate_ids}

    # Syntax-check all tracked-looking Python source files, excluding virtualenv/cache.
    syntax_errors=[]
    for p in ROOT.rglob("*.py"):
        if any(part in {".venv","venv","__pycache__",".git"} for part in p.parts): continue
        try: compile(p.read_text(encoding="utf-8"),str(p),"exec")
        except Exception as e: syntax_errors.append(f"{p.relative_to(ROOT)}: {type(e).__name__}: {e}")
    if syntax_errors: add(findings,"error","PYTHON_SYNTAX",f"{len(syntax_errors)} archivos con error: {syntax_errors[:20]}")
    report["sources"]["python_syntax"]={"files_checked":sum(1 for p in ROOT.rglob("*.py") if not any(part in {".venv","venv","__pycache__",".git"} for part in p.parts)),"errors":syntax_errors}

    # Empty source modules/scripts that are imported by the project are suspicious.
    empty_files=[]
    for rel in ["sorteos/constants.py","rescue.db"]:
        p=ROOT/rel
        if p.exists() and p.stat().st_size==0: empty_files.append(rel)
    if empty_files: add(findings,"warning","EMPTY_FILES",f"Archivos vacíos sospechosos: {empty_files}")
    # A read-only source audit cannot verify live DB or deployed HTML; state this explicitly.
    add(findings,"info","LIVE_DB_SKIPPED","Auditoría de base de datos en vivo omitida: no se usan credenciales ni conexión desde CI.")
    add(findings,"info","RUNTIME_SKIPPED","La comprobación dinámica de vistas/templates requiere entorno Django y base de datos; esta pasada es estática.")

    counts=Counter(f["severity"] for f in findings)
    report["counts"]={k:counts.get(k,0) for k in ("error","warning","info")}
    report["ok"]=counts["error"]==0 and (not args.strict or counts["warning"]==0)
    print(f"\n{report['title']} — {report['counts']}")
    for f in findings:
        print(f"[{f['severity'].upper()}] {f['code']}: {f['message']}" + (f" ({f['path']})" if f.get("path") else ""))
    if args.json:
        out=Path(args.json); out.parent.mkdir(parents=True,exist_ok=True)
        out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print(f"Reporte JSON: {out}")
    return 1 if counts["error"] or (args.strict and counts["warning"]) else 0
if __name__=="__main__": sys.exit(main())
