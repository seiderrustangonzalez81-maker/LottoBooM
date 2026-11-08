import json
import os
import requests
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# Zona horaria Cuba (UTC-4 hasta nov 2027)
CUBA_TZ = timezone(timedelta(hours=-4))

URL_MAIN = "https://enloteria.com/resultados-loterias-hoy"
URL_QUEMAITO = "https://enloteria.com/resultados-el-quemaito-mayor-hoy"
URL_QUINIELON = "https://enloteria.com/resultados-el-quinielon-dia-hoy"
ARCHIVO_JSON = "resultados.json"

# Mapeo de URLs de EE. UU. en LotteryUSA
URLS_USA = {
    "Texas 1:20 PM": "https://www.lotteryusa.com/texas/pick-3-day/",
    "Florida 1:35 PM": "https://www.lotteryusa.com/florida/midday-pick-3/",
    "New York 2:30 PM": "https://www.lotteryusa.com/new-york/numbers/",
    "New Jersey 12:50 PM": "https://www.lotteryusa.com/new-jersey/pick-3/",
    "Georgia 12:30 PM": "https://www.lotteryusa.com/georgia/cash-3/",
    "Tennessee 1:20 PM": "https://www.lotteryusa.com/tennessee/cash-3-midday/"
}

def fecha_cuba():
    return datetime.now(CUBA_TZ).strftime("%Y-%m-%d")

def extraer_numeros_validos(tarjeta_o_soup):
    bolas = tarjeta_o_soup.find_all("div", class_="result-number")
    numeros_validos = []
    for b in bolas:
        texto = b.get_text(strip=True)
        if texto.isdigit() and len(texto) >= 2:
            numeros_validos.append(texto)
    return numeros_validos[:4]

def scrape_principal(page):
    print("Extrayendo pagina principal (enloteria)...")
    resultados = []
    try:
        page.goto(URL_MAIN, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(15000)
        for _ in range(3):
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(3000)
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(2000)
    except Exception as e:
        print(f"  Scroll fallo: {e}")

    soup = BeautifulSoup(page.content(), "html.parser")
    tarjetas = soup.find_all("div", attrs={"data-lottery-name": True})
    
    for tarjeta in tarjetas:
        try:
            nombre = tarjeta.get("data-lottery-name", "").strip()
            if not nombre: continue
            numeros = extraer_numeros_validos(tarjeta)
            if numeros and len(numeros) >= 2:
                resultados.append({
                    "sorteo_nombre": nombre,
                    "numeros": numeros,
                    "fecha": fecha_cuba(),
                    "fuente": "enloteria"
                })
        except Exception as e:
            pass
    return resultados

def scrape_especifica(page, url, nombre_forzado):
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(4000)
        soup = BeautifulSoup(page.content(), "html.parser")
        numeros = extraer_numeros_validos(soup)[:3]
        if numeros and len(numeros) >= 2:
            return [{
                "sorteo_nombre": nombre_forzado,
                "numeros": numeros,
                "fecha": fecha_cuba(),
                "fuente": "enloteria"
            }]
    except Exception as e:
        pass
    return []

# ═══════════════════════════════════════════════════════════════
# NUEVA FUNCIÓN PARA LOTTERYUSA.COM (EE. UU.)
# ═══════════════════════════════════════════════════════════════
def scrape_lotteryusa():
    print("Extrayendo resultados de USA (lotteryusa.com)...")
    resultados = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    for nombre_db, url in URLS_USA.items():
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # Buscamos la primera tarjeta (la más reciente)
            tarjeta = soup.find('tr', class_='c-draw-card')
            if not tarjeta: continue
                
            # Extraer la fecha ("Sunday, Nov 8, 2026" -> "2026-11-08")
            fecha_nodo = tarjeta.find('time', class_='c-draw-card__draw-date')
            if not fecha_nodo: continue
            fecha_texto = fecha_nodo.get_text(strip=True)
            
            # Limpiamos el texto para quedarnos con "Nov 8, 2026"
            for dia in ['Sunday,', 'Monday,', 'Tuesday,', 'Wednesday,', 'Thursday,', 'Friday,', 'Saturday,']:
                fecha_texto = fecha_texto.replace(dia, '').strip()
                
            try:
                fecha_dt = datetime.strptime(fecha_texto, '%b %d, %Y')
                fecha_iso = fecha_dt.strftime('%Y-%m-%d')
            except ValueError:
                print(f"  Error parseando fecha: {fecha_texto}")
                continue
            
            # Extraer los números (ignorando el Fireball)
            numeros_nodos = tarjeta.select('ul.c-result.c-draw-card__ball-list > li.c-ball')
            numeros = [n.get_text(strip=True) for n in numeros_nodos]
            
            if numeros:
                resultados.append({
                    "sorteo_nombre": nombre_db,
                    "numeros": numeros,
                    "fecha": fecha_iso,
                    "fuente": "lotteryusa"
                })
                print(f"  OK {nombre_db} -> {', '.join(numeros)} (Fecha: {fecha_iso})")
                
        except Exception as e:
            print(f"  Error en {nombre_db}: {e}")
            
    return resultados

def main():
    todos_nuevos = []
    
    # 1. Scraping con Playwright (enloteria)
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
        except Exception as e: pass
        try: todos_nuevos.extend(scrape_especifica(page, URL_QUINIELON, "El Quinielon Dia"))
        except Exception as e: pass
        
        browser.close()

    # 2. Scraping con Requests (lotteryusa)
    try: 
        todos_nuevos.extend(scrape_lotteryusa())
    except Exception as e:
        print(f"Error en lotteryusa: {e}")

    # 3. Lógica de acumulación en JSON
    resultados_guardados = []
    if os.path.exists(ARCHIVO_JSON):
        try:
            with open(ARCHIVO_JSON, "r", encoding="utf-8") as f:
                resultados_guardados = json.load(f)
        except Exception:
            resultados_guardados = []

    diccionario_datos = {}
    for r in resultados_guardados:
        llave = f"{r['sorteo_nombre']}|{r['fecha']}"
        diccionario_datos[llave] = r

    for nuevo in todos_nuevos:
        llave = f"{nuevo['sorteo_nombre']}|{nuevo['fecha']}"
        diccionario_datos[llave] = nuevo

    resultados_finales = list(diccionario_datos.values())
    with open(ARCHIVO_JSON, "w", encoding="utf-8") as f:
        json.dump(resultados_finales, f, ensure_ascii=False, indent=2)

    print(f"Total sorteos en JSON: {len(resultados_finales)}")
    print(f"Fecha de hoy: {fecha_cuba()}")

if __name__ == "__main__":
    main()
