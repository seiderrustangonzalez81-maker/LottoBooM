import json
import re
import traceback
from datetime import datetime
from playwright.sync_api import sync_playwright

URL_CONECTATE = "https://www.conectate.com.do/loterias/pagina/ultimos-resultados"
URL_FLORIDA = "https://www.lotteryusa.com/florida/"
URL_GEORGIA = "https://www.lotteryusa.com/georgia/"

def extraer_puros(texto):
    # Solo extrae números de 1 o 2 dígitos que NO estén pegados a letras o $.
    return re.findall(r"(?<![A-Za-z0-9$])\d{1,2}(?![A-Za-z0-9$])", texto)

def scrape_georgia(page):
    print("🔍 Georgia...")
    resultados = []
    try:
        page.goto(URL_GEORGIA, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(5000)
        lineas = page.inner_text("body").split("\n")
        
        reglas = [
            ("Cash 3 Midday", "Georgia 12:30 PM", 3, True),
            ("Cash 4 Midday", "Georgia 12:30 PM", 4, True),
            ("Cash 3 Evening", "Georgia 7 PM", 3, True),
            ("Cash 4 Evening", "Georgia 7 PM", 4, True),
            ("Cash 3 Night", "Georgia 11:34 PM", 3, True),
            ("Cash 4 Night", "Georgia 11:34 PM", 4, True)
        ]
        
        for buscar, nombre_db, cant, quitar_primer in reglas:
            for i, linea in enumerate(lineas):
                if buscar in linea:
                    bloque = " ".join(lineas[i:i+5])
                    nums = extraer_puros(bloque)
                    if quitar_primer and len(nums) > 0 and nums[0] == str(cant):
                        nums = nums[1:]
                    if len(nums) >= cant:
                        resultados.append({
                            "sorteo_nombre": nombre_db,
                            "numeros": nums[:cant],
                            "fecha": datetime.now().strftime("%Y-%m-%d"),
                            "fuente": "georgia"
                        })
                    break
    except Exception as e:
        print(f"⚠️ Georgia falló: {e}")
    return resultados

def scrape_florida(page):
    print("🔍 Florida...")
    resultados = []
    try:
        page.goto(URL_FLORIDA, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(5000)
        lineas = page.inner_text("body").split("\n")
        
        # Buscamos Pick 3, Pick 4, etc. en cualquier parte de la página
        reglas = [
            ("Pick 2", "Florida 1:35 PM", 2, True),
            ("Pick 3", "Florida 1:35 PM", 3, True),
            ("Pick 4", "Florida 1:35 PM", 4, True),
            ("Pick 5", "Florida 1:35 PM", 5, True)
        ]
        
        for buscar, nombre_db, cant, quitar_primer in reglas:
            for i, linea in enumerate(lineas):
                if buscar.lower() in linea.lower() and "midday" not in linea.lower():
                    bloque = " ".join(lineas[i:i+5])
                    nums = extraer_puros(bloque)
                    if quitar_primer and len(nums) > 0 and nums[0] == str(cant):
                        nums = nums[1:]
                    if len(nums) >= cant:
                        resultados.append({
                            "sorteo_nombre": nombre_db,
                            "numeros": nums[:cant],
                            "fecha": datetime.now().strftime("%Y-%m-%d"),
                            "fuente": "florida"
                        })
                    break
    except Exception as e:
        print(f"⚠️ Florida falló: {e}")
    return resultados

def scrape_conectate(page):
    print("🔍 Conectate...")
    resultados = []
    try:
        page.goto(URL_CONECTATE, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(8000)
        lineas = page.inner_text("body").split("\n")
        
        reglas = [
            ("Leidsa", "Leidsa 8:55 PM", 3),
            ("Loteka", "Loteka 7:55 PM", 3),
            ("Nacional", "Nacional", 3),
            ("Primera", "Primera", 3),
            ("Quinielón", "Quinielón", 3),
            ("Real", "Lotería Real 12:55 PM", 3),
        ]
        
        for buscar, nombre_db, cant in reglas:
            for i, linea in enumerate(lineas):
                if buscar.lower() in linea.lower():
                    bloque = " ".join(lineas[i:i+5])
                    nums = extraer_puros(bloque)
                    if len(nums) >= cant:
                        resultados.append({
                            "sorteo_nombre": nombre_db,
                            "numeros": nums[:cant],
                            "fecha": datetime.now().strftime("%Y-%m-%d"),
                            "fuente": "conectate"
                        })
                    break
    except Exception as e:
        print(f"⚠️ Conectate falló: {e}")
    return resultados

def main():
    todos = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_default_timeout(30000)
        
        for funcion in [scrape_georgia, scrape_florida, scrape_conectate]:
            try: todos.extend(funcion(page))
            except Exception as e: print(f"❌ Error: {e}")
        browser.close()

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
