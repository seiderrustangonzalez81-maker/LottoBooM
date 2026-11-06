import json
import traceback
from datetime import datetime
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

URL_ENLOTERIA = "https://enloteria.com/resultados-loterias-hoy"
URL_QUEMAITO = "https://enloteria.com/resultados-el-quemaito-mayor-hoy"
URL_QUINIELON = "https://enloteria.com/resultados-el-quinielon-dia-hoy"

def extraer_de_tarjetas(page, url, nombre_forzado):
    resultados = []
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(4000)
        soup = BeautifulSoup(page.content(), "html.parser")
        
        # En las páginas individuales, los números están en las bolitas
        bolas = soup.find_all("div", class_="result-number")
        numeros = [b.get_text(strip=True) for b in bolas]
        
        if numeros:
            resultados.append({
                "sorteo_nombre": nombre_forzado,
                "numeros": numeros,
                "fecha": datetime.now().strftime("%Y-%m-%d"),
                "fuente": "enloteria"
            })
    except Exception as e:
        print(f"⚠️ Error en {nombre_forzado}: {e}")
    return resultados

def scrape_enloteria_general(page):
    print("🔍 Extrayendo principales de EnLoteria...")
    resultados = []
    try:
        page.goto(URL_ENLOTERIA, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(5000)
        soup = BeautifulSoup(page.content(), "html.parser")
        
        tarjetas = soup.find_all("div", attrs={"data-lottery-name": True})
        for tarjeta in tarjetas:
            nombre_raw = tarjeta.get("data-lottery-name")
            bolas = tarjeta.find_all("div", class_="result-number")
            numeros = [b.get_text(strip=True) for b in bolas]
            
            if numeros:
                resultados.append({
                    "sorteo_nombre": nombre_raw,
                    "numeros": numeros,
                    "fecha": datetime.now().strftime("%Y-%m-%d"),
                    "fuente": "enloteria"
                })
    except Exception as e:
        print(f"⚠️ Error en EnLoteria general: {e}")
    return resultados

def main():
    todos = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_default_timeout(30000)
        
        # 1. Extraer los principales
        todos.extend(scrape_enloteria_general(page))
        
        # 2. Extraer los específicos
        todos.extend(extraer_de_tarjetas(page, URL_QUEMAITO, "El Quemaito Mayor"))
        todos.extend(extraer_de_tarjetas(page, URL_QUINIELON, "El Quinielón Día"))
        
        browser.close()

    # Guardar
    with open("resultados.json", "w", encoding="utf-8") as f:
        json.dump(todos, f, ensure_ascii=False, indent=2)
    print(f"💾 Archivo resultados.json guardado con {len(todos)} sorteos.")

if __name__ == "__main__":
    main()
