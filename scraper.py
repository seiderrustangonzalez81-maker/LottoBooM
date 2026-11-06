import json
import traceback
from datetime import datetime
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

URL_ENLOTERIA = "https://enloteria.com/resultados-loterias-hoy"

def scrape_enloteria(page):
    print("🔍 Extrayendo resultados de EnLoteria...")
    resultados = []
    
    try:
        page.goto(URL_ENLOTERIA, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(5000) # Esperamos a que la página cargue completa
        
        html = page.content()
        soup = BeautifulSoup(html, "html.parser")
        
        # Buscamos todas las tarjetas de sorteos (tienen el atributo data-lottery-name)
        tarjetas = soup.find_all("div", attrs={"data-lottery-name": True})
        
        for tarjeta in tarjetas:
            nombre_raw = tarjeta.get("data-lottery-name")
            
            # Buscamos las bolitas con los números dentro de esa tarjeta
            bolas = tarjeta.find_all("div", class_="result-number")
            numeros = [b.get_text(strip=True) for b in bolas]
            
            # Si la tarjeta tiene números (es decir, el sorteo ya salió), los guardamos
            if numeros:
                resultados.append({
                    "sorteo_nombre": nombre_raw,
                    "numeros": numeros,
                    "fecha": datetime.now().strftime("%Y-%m-%d"),
                    "fuente": "enloteria"
                })
                
    except Exception as e:
        print(f"⚠️ Error en EnLoteria: {e}")
        print(traceback.format_exc())
        
    print(f"✅ Se extrajeron {len(resultados)} sorteos con números reales.")
    return resultados

def main():
    todos = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_default_timeout(30000)
        
        try:
            todos.extend(scrape_enloteria(page))
        except Exception as e:
            print(f"❌ Error general: {e}")
            
        browser.close()

    # Guardar en JSON
    with open("resultados.json", "w", encoding="utf-8") as f:
        json.dump(todos, f, ensure_ascii=False, indent=2)
    print(f"💾 Archivo resultados.json guardado con {len(todos)} sorteos.")

if __name__ == "__main__":
    main()
