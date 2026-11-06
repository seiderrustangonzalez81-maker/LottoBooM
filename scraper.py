import json
import re
import traceback
from datetime import datetime
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

URL_CONECTATE = "https://www.conectate.com.do/loterias/pagina/ultimos-resultados"

def extraer_picks(texto):
    nums = re.findall(r"\b\d{1,5}\b", texto)
    nums = [n for n in nums if not (len(n) == 4 and n.startswith("20"))]
    return nums

def scrape_conectate():
    print("Iniciando Playwright...")
    resultados = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        print("Entrando a la página...")
        page.goto(URL_CONECTATE, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(8000) 
        
        html = page.content()
        with open("debug_conectate.html", "w", encoding="utf-8") as f:
            f.write(html)
        browser.close()

    soup = BeautifulSoup(html, "html.parser")

    # Buscar todos los enlaces que contengan resultados
    for enlace in soup.find_all("a"):
        texto = enlace.get_text(" ", strip=True)
        
        # Verificar si el texto tiene un patrón de fecha y números (ej: "Lotería Nacional 20-12-2025 21:05 72 38 25")
        if re.search(r"\d{2}-\d{2}-\d{4}\s+\d{2}:\d{2}", texto):
            nums = extraer_picks(texto)
            if len(nums) >= 2:
                # El nombre del sorteo es la parte del texto antes de la fecha
                nombre_juego = re.split(r"\d{2}-\d{2}-\d{4}", texto)[0].strip()
                
                resultados.append({
                    "sorteo_nombre": nombre_juego,
                    "fecha": datetime.now().strftime("%Y-%m-%d"),
                    "hora": datetime.now().strftime("%H:%M:%S"),
                    "pick2": nums[0] if len(nums) > 0 else None,
                    "pick3": nums[1] if len(nums) > 1 else None,
                    "pick4": nums[2] if len(nums) > 2 else None,
                    "pick5": nums[3] if len(nums) > 3 else None,
                    "fuente": "conectate",
                })

    print(f"Resultados extraidos: {len(resultados)}")
    return resultados

def main():
    todos = []
    try:
        todos.extend(scrape_conectate())
    except Exception as e:
        print("❌ OCURRIÓ UN ERROR:")
        print(traceback.format_exc())

    with open("resultados.json", "w", encoding="utf-8") as f:
        json.dump(todos, f, ensure_ascii=False, indent=2)
    print(f"Guardados {len(todos)} en resultados.json")

if __name__ == "__main__":
    main()
