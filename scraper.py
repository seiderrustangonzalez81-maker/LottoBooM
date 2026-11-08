import json
import traceback
import os
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# Zona horaria Cuba (UTC-4 hasta nov 2027)
CUBA_TZ = timezone(timedelta(hours=-4))

URL_MAIN = "https://enloteria.com/resultados-loterias-hoy"
URL_QUEMAITO = "https://enloteria.com/resultados-el-quemaito-mayor-hoy"
URL_QUINIELON = "https://enloteria.com/resultados-el-quinielon-dia-hoy"
ARCHIVO_JSON = "resultados.json"

def fecha_cuba():
    return datetime.now(CUBA_TZ).strftime("%Y-%m-%d")

def scrape_principal(page):
    print("Extrayendo pagina principal...")
    resultados = []
    try:
        page.goto(URL_MAIN, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(8000)
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(3000)
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(2000)
    except Exception as e:
        print(f"  Scroll fallo: {e}")

    soup = BeautifulSoup(page.content(), "html.parser")
    tarjetas = soup.find_all("div", attrs={"data-lottery-name": True})
    print(f"  Tarjetas encontradas: {len(tarjetas)}")

    for tarjeta in tarjetas:
        try:
            nombre = tarjeta.get("data-lottery-name", "").strip()
            if not nombre: continue
            bolas = tarjeta.find_all("div", class_="result-number")
            numeros = [b.get_text(strip=True) for b in bolas if b.get_text(strip=True)][:4]
            if numeros and len(numeros) >= 2:
                resultados.append({
                    "sorteo_nombre": nombre,
                    "numeros": numeros,
                    "fecha": fecha_cuba(),
                    "fuente": "enloteria"
                })
                print(f"  OK {nombre} -> {', '.join(numeros)}")
        except Exception as e:
            print(f"  Error en tarjeta: {e}")
    return resultados

def scrape_especifica(page, url, nombre_forzado):
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(4000)
        soup = BeautifulSoup(page.content(), "html.parser")
        bolas = soup.find_all("div", class_="result-number")
        numeros = [b.get_text(strip=True) for b in bolas if b.get_text(strip=True)][:3]
        if numeros and len(numeros) >= 2:
            print(f"  OK {nombre_forzado} -> {', '.join(numeros)}")
            return [{
                "sorteo_nombre": nombre_forzado,
                "numeros": numeros,
                "fecha": fecha_cuba(),
                "fuente": "enloteria"
            }]
    except Exception as e:
        print(f"  Error en {nombre_forzado}: {e}")
    return []

def main():
    todos_nuevos = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        page.set_default_timeout(60000)
        
        try: todos_nuevos.extend(scrape_principal(page))
        except Exception as e: print(f"Error principal: {e}")
        
        try: todos_nuevos.extend(scrape_especifica(page, URL_QUEMAITO, "El Quemaito Mayor"))
        except Exception as e: print(f"Error Quemaito: {e}")
        
        try: todos_nuevos.extend(scrape_especifica(page, URL_QUINIELON, "El Quinielon Dia"))
        except Exception as e: print(f"Error Quinielon: {e}")
        
        browser.close()

    # --- LÓGICA DE ACUMULACIÓN ---
    # 1. Leer el JSON existente
    resultados_guardados = []
    if os.path.exists(ARCHIVO_JSON):
        try:
            with open(ARCHIVO_JSON, "r", encoding="utf-8") as f:
                resultados_guardados = json.load(f)
        except Exception:
            resultados_guardados = []

    # 2. Organizar en un diccionario para evitar duplicados (usando nombre+fecha como clave)
    diccionario_datos = {}
    for r in resultados_guardados:
        llave = f"{r['sorteo_nombre']}|{r['fecha']}"
        diccionario_datos[llave] = r

    # 3. Agregar los nuevos resultados. Si uno ya existía, no se duplica, solo se actualiza.
    for nuevo in todos_nuevos:
        llave = f"{nuevo['sorteo_nombre']}|{nuevo['fecha']}"
        diccionario_datos[llave] = nuevo

    # 4. Guardar todo en el JSON
    resultados_finales = list(diccionario_datos.values())
    with open(ARCHIVO_JSON, "w", encoding="utf-8") as f:
        json.dump(resultados_finales, f, ensure_ascii=False, indent=2)

    print(f"Total sorteos en JSON: {len(resultados_finales)}")
    print(f"Fecha de hoy: {fecha_cuba()}")

if __name__ == "__main__":
    main()
