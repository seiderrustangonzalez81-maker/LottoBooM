import json
import os
import time
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
    "New York 2:30 PM": "https://www.lotteryusa.com/new-york/numbers-midday/",
    "New Jersey 12:50 PM": "https://www.lotteryusa.com/new-jersey/pick-3-midday/",
    "Georgia 12:30 PM": "https://www.lotteryusa.com/georgia/cash-3-midday/",
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

# ═══════════════════════════════════════════════════════════════
# 1. SCRAPING ENLOTERIA (CON SCROLL DINÁMICO)
# ═══════════════════════════════════════════════════════════════
def scroll_hasta_estabilizar(page, max_intentos=20, pausa_ms=3000):
    """Baja la página hasta que el número de tarjetas deje de crecer."""
    tarjetas_previas = 0
    for intento in range(max_intentos):
        tarjetas_actuales = page.locator('div[data-lottery-name]').count()
        if tarjetas_actuales == tarjetas_previas:
            print(f"  ✅ Scroll completado. Tarjetas: {tarjetas_actuales}")
            return
        tarjetas_previas = tarjetas_actuales
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(pausa_ms)
    print(f"  ⚠️ Máximo de scrolls alcanzado. Tarjetas: {tarjetas_previas}")

def scrape_principal(page):
    print("Extrayendo enloteria (principal)...")
    resultados = []
    try:
        page.goto(URL_MAIN, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(10000)
        scroll_hasta_estabilizar(page)
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(1000)
    except Exception as e:
        print(f"  Error en scroll principal: {e}")

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
        except Exception:
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
    except Exception:
        pass
    return []

# ═══════════════════════════════════════════════════════════════
# 2. SCRAPING LOTTERYUSA (CON CACHE BUSTER Y VALIDACIÓN)
# ═══════════════════════════════════════════════════════════════
def scrape_lotteryusa():
    print("Extrayendo USA (lotteryusa.com)...")
    resultados = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    hoy_iso = fecha_cuba()
    
    for nombre_db, url in URLS_USA.items():
        try:
            # Cache Buster: agregamos timestamp para forzar datos frescos
            url_fresca = f"{url}?nocache={int(time.time())}"
            resp = requests.get(url_fresca, headers=headers, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            tarjeta = soup.find('tr', class_='c-draw-card')
            if not tarjeta: 
                print(f"  ⚠️ Sin tarjeta: {nombre_db}")
                continue
                
            fecha_nodo = tarjeta.find('time', class_='c-draw-card__draw-date')
            if not fecha_nodo: continue
            fecha_texto = fecha_nodo.get_text(strip=True)
            
            for dia in ['Sunday,', 'Monday,', 'Tuesday,', 'Wednesday,', 'Thursday,', 'Friday,', 'Saturday,']:
                fecha_texto = fecha_texto.replace(dia, '').strip()
                
            try:
                fecha_dt = datetime.strptime(fecha_texto, '%b %d, %Y')
                fecha_iso = fecha_dt.strftime('%Y-%m-%d')
            except ValueError:
                print(f"  ⚠️ Fecha inválida en {nombre_db}: {fecha_texto}")
                continue
            
            # Validación interna: solo agregar si es de hoy
            if fecha_iso != hoy_iso:
                print(f"  ⏭️ Saltando {nombre_db}: fecha {fecha_iso} != hoy ({hoy_iso})")
                continue
            
            numeros_nodos = tarjeta.select('ul.c-result.c-draw-card__ball-list > li.c-ball')
            numeros = [n.get_text(strip=True) for n in numeros_nodos]
            
            if numeros:
                resultados.append({
                    "sorteo_nombre": nombre_db,
                    "numeros": numeros,
                    "fecha": fecha_iso,
                    "fuente": "lotteryusa"
                })
                print(f"  ✅ OK {nombre_db} -> {', '.join(numeros)}")
                
        except Exception as e:
            print(f"  ❌ Error en {nombre_db}: {e}")
            
    return resultados

# ═══════════════════════════════════════════════════════════════
# 3. MAIN (UNIFICACIÓN Y GUARDADO)
# ═══════════════════════════════════════════════════════════════
def main():
    todos_nuevos = []
    
    # --- Scraping con Playwright (enloteria) ---
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

    # --- Scraping con Requests (lotteryusa) ---
    try: 
        todos_nuevos.extend(scrape_lotteryusa())
    except Exception as e:
        print(f"Error en lotteryusa: {e}")

    # --- Lógica de acumulación en JSON ---
    resultados_guardados = []
    if os.path.exists(ARCHIVO_JSON):
        try:
            with open(ARCHIVO_JSON, "r", encoding="utf-8") as f:
                resultados_guardados = json.load(f)
        except Exception:
            resultados_guardados = []

    diccionario_datos = {}
    for r in resultados_guardados:
        # Solo conservamos los de la fecha de hoy para evitar arrastrar basura de días anteriores
        if r.get("fecha") == fecha_cuba():
            llave = f"{r['sorteo_nombre']}|{r['fecha']}"
            diccionario_datos[llave] = r

    for nuevo in todos_nuevos:
        llave = f"{nuevo['sorteo_nombre']}|{nuevo['fecha']}"
        diccionario_datos[llave] = nuevo

    resultados_finales = list(diccionario_datos.values())
    with open(ARCHIVO_JSON, "w", encoding="utf-8") as f:
        json.dump(resultados_finales, f, ensure_ascii=False, indent=2)

    print(f"\nTotal sorteos en JSON: {len(resultados_finales)}")
    print(f"Fecha de hoy: {fecha_cuba()}")

if __name__ == "__main__":
    main()
