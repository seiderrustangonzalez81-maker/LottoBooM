import json
import re
import traceback
from datetime import datetime
from playwright.sync_api import sync_playwright

URL_CONECTATE = "https://www.conectate.com.do/loterias/pagina/ultimos-resultados"
URL_TEXAS = "https://www.lotteryusa.com/texas/"
URL_TENNESSEE = "https://www.lotteryusa.com/tennessee/"
URL_NEW_JERSEY = "https://www.lotteryusa.com/new-jersey/"

def extraer_puros(texto):
    # Extrae solo números de 1 o 2 dígitos limpios
    return re.findall(r"(?<![A-Za-z0-9$])\d{1,2}(?![A-Za-z0-9$])", texto)

def scrape_conectate(page):
    print("🔍 Buscando en Conectate (Dominicanas)...")
    resultados = []
    try:
        page.goto(URL_CONECTATE, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(8000)
        lineas = page.inner_text("body").split("\n")
        
        # Mapeo directo a los nombres de tu base de datos
        juegos = ["Leidsa", "Loteka", "Nacional", "Primera", "Quinielón", "Anguila"]
        
        for juego in juegos:
            for i, linea in enumerate(lineas):
                if juego.lower() in linea.lower():
                    # Leemos las siguientes 3 líneas para atrapar los números
                    bloque = " ".join(lineas[i:i+3])
                    nums = extraer_puros(bloque)
                    if len(nums) >= 2:
                        resultados.append({
                            "sorteo_nombre": juego,
                            "numeros": nums[:3], # Tomamos 3 números
                            "fecha": datetime.now().strftime("%Y-%m-%d"),
                            "fuente": "conectate"
                        })
                    break
    except Exception as e:
        print(f"⚠️ Conectate falló: {e}")
    return resultados

def scrape_estado(page, url, estado, juegos_buscar):
    print(f"🔍 Buscando en {estado}...")
    resultados = []
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(5000)
        lineas = page.inner_text("body").split("\n")
        
        for juego in juegos_buscar:
            for i, linea in enumerate(lineas):
                if juego.lower() in linea.lower():
                    # Buscamos si es Midday, Evening o Night en las cercanías
                    contexto = " ".join(lineas[i:i+3]).lower()
                    turno = ""
                    if "midday" in contexto: turno = "Midday"
                    elif "evening" in contexto: turno = "Evening"
                    elif "night" in contexto: turno = "Night"
                    elif "morning" in contexto: turno = "Morning"
                    
                    bloque = " ".join(lineas[i:i+3])
                    nums = extraer_puros(bloque)
                    
                    if len(nums) >= 3:
                        resultados.append({
                            "sorteo_nombre": f"{estado} {juego} {turno}".strip(),
                            "numeros": nums[:4],
                            "fecha": datetime.now().strftime("%Y-%m-%d"),
                            "fuente": estado.lower()
                        })
                    break
    except Exception as e:
        print(f"⚠️ {estado} falló: {e}")
    return resultados

def main():
    todos = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_default_timeout(30000)
        
        # 1. Dominicanas
        try: todos.extend(scrape_conectate(page))
        except Exception as e: print(e)
        
        # 2. Texas (Pick 3, Pick 4, Cash 5)
        try: todos.extend(scrape_estado(page, URL_TEXAS, "Texas", ["Pick 3", "Pick 4", "Cash 5"]))
        except Exception as e: print(e)
        
        # 3. Tennessee (Cash 3, Cash 4)
        try: todos.extend(scrape_estado(page, URL_TENNESSEE, "Tennessee", ["Cash 3", "Cash 4"]))
        except Exception as e: print(e)

        # 4. New Jersey (Pick 3, Pick 4)
        try: todos.extend(scrape_estado(page, URL_NEW_JERSEY, "New Jersey", ["Pick 3", "Pick 4"]))
        except Exception as e: print(e)
        
        browser.close()

    # Limpieza de duplicados
    vistos = set()
    limpios = []
    for r in todos:
        if r['numeros']:
            firma = f"{r['sorteo_nombre']}-{'-'.join(r['numeros'])}"
            if firma not in vistos:
                vistos.add(firma)
                limpios.append(r)

    with open("resultados.json", "w", encoding="utf-8") as f:
        json.dump(limpios, f, ensure_ascii=False, indent=2)
    print(f"💾 Guardados {len(limpios)} resultados reales.")

if __name__ == "__main__":
    main()
