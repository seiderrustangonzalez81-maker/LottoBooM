import json
import re
import traceback
from datetime import datetime
from playwright.sync_api import sync_playwright

URL_CONECTATE = "https://www.conectate.com.do/loterias/pagina/ultimos-resultados"
URL_FLORIDA = "https://www.flalottery.com/winningNumbers.do"
URL_GEORGIA = "https://www.lotteryusa.com/georgia/"

def extraer_numeros_puros(texto, cantidad):
    # Solo extrae números de 1 o 2 dígitos que NO estén pegados a letras (ignora P23, $45, etc.)
    nums = re.findall(r"(?<![A-Za-z$])\b\d{1,2}\b(?![A-Za-z$])", texto)
    if len(nums) >= cantidad:
        return nums[:cantidad]
    return []

def scrape_conectate(page):
    print("🔍 Buscando en Conectate...")
    resultados = []
    page.goto(URL_CONECTATE, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(8000)
    filas = page.locator("tr").all()
    for fila in filas:
        try:
            texto = fila.inner_text().strip()
            if any(k in texto for k in ["Leidsa", "Loteka", "Nacional", "Primera", "Quinielón"]):
                nombre = texto.split("\n")[0].strip()
                nums = extraer_numeros_puros(texto, 3)
                if len(nums) >= 2:
                    resultados.append({
                        "sorteo_nombre": nombre,
                        "fecha": datetime.now().strftime("%Y-%m-%d"),
                        "numeros": nums[:3],
                        "fuente": "conectate",
                    })
        except: pass
    return resultados

def scrape_florida(page):
    print("🔍 Buscando en Florida Lottery...")
    resultados = []
    page.goto(URL_FLORIDA, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(8000)
    filas = page.locator("tr").all()
    for fila in filas:
        try:
            texto = fila.inner_text().strip()
            if "PICK" in texto.upper():
                nombre = texto.split("\n")[0].strip()
                cant = 3 if "3" in nombre else (4 if "4" in nombre else (5 if "5" in nombre else 2))
                nums = extraer_numeros_puros(texto, cant)
                if len(nums) == cant:
                    resultados.append({
                        "sorteo_nombre": nombre,
                        "fecha": datetime.now().strftime("%Y-%m-%d"),
                        "numeros": nums,
                        "fuente": "florida",
                    })
        except: pass
    return resultados

def scrape_georgia(page):
    print("🔍 Buscando en Georgia Lottery...")
    resultados = []
    page.goto(URL_GEORGIA, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(6000)
    filas = page.locator("tr").all()
    for fila in filas:
        try:
            texto = fila.inner_text().strip()
            if any(k in texto for k in ["Cash 3", "Cash 4", "Georgia Five", "Fantasy 5"]):
                nombre = texto.split("\n")[0].strip()
                cant = 5 if "Five" in nombre or "Fantasy" in nombre else (4 if "4" in nombre else 3)
                nums = extraer_numeros_puros(texto, cant)
                if len(nums) == cant:
                    resultados.append({
                        "sorteo_nombre": nombre,
                        "fecha": datetime.now().strftime("%Y-%m-%d"),
                        "numeros": nums,
                        "fuente": "georgia",
                    })
        except: pass
    return resultados

def main():
    todos = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        for funcion in [scrape_conectate, scrape_florida, scrape_georgia]:
            try: todos.extend(funcion(page))
            except Exception as e: print(f"❌ Error: {traceback.format_exc()}")
        browser.close()

    # Limpieza de duplicados exactos
    vistos = set()
    limpios = []
    for r in todos:
        firma = f"{r['sorteo_nombre']}-{'-'.join(r['numeros'])}"
        if firma not in vistos:
            vistos.add(firma)
            limpios.append(r)

    with open("resultados.json", "w", encoding="utf-8") as f:
        json.dump(limpios, f, ensure_ascii=False, indent=2)
    print(f"💾 Guardados {len(limpios)} resultados reales.")

if __name__ == "__main__":
    main()
