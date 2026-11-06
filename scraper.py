import json
import re
import traceback
from datetime import datetime
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

URL_CONECTATE = "https://www.conectate.com.do/loterias/pagina/ultimos-resultados"
URL_FLORIDA = "https://www.flalottery.com/winningNumbers.do"
URL_GEORGIA = "https://www.lotteryusa.com/georgia/"

def extraer_numeros(texto, cantidad_esperada):
    nums = re.findall(r"\b\d{1,2}\b", texto)
    if len(nums) >= cantidad_esperada:
        return nums[:cantidad_esperada]
    return []

def scrape_conectate(page):
    print("🔍 Buscando en Conectate...")
    resultados = []
    page.goto(URL_CONECTATE, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(8000)
    soup = BeautifulSoup(page.content(), "html.parser")

    # Buscamos cualquier bloque que contenga el nombre de la lotería
    for texto_nodo in soup.find_all(string=re.compile(r"Leidsa|Loteka|Nacional|Primera|Quinielón|Anguila", re.I)):
        padre = texto_nodo.find_parent()
        if not padre: continue
        
        # Subimos un par de niveles para agarrar los números
        contenedor = padre.find_parent() or padre
        texto_bloque = contenedor.get_text(" ", strip=True)
        nums = extraer_numeros(texto_bloque, 3) # Asumimos Pick 3 por defecto
        
        if len(nums) >= 2:
            resultados.append({
                "sorteo_nombre": texto_nodo.strip(),
                "fecha": datetime.now().strftime("%Y-%m-%d"),
                "hora": datetime.now().strftime("%H:%M:%S"),
                "numeros": nums,
                "fuente": "conectate",
            })
    print(f"✅ Conectate: {len(resultados)} resultados.")
    return resultados

def scrape_florida(page):
    print("🔍 Buscando en Florida Lottery...")
    resultados = []
    page.goto(URL_FLORIDA, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(10000)
    soup = BeautifulSoup(page.content(), "html.parser")

    # Buscamos por los nombres de los juegos de Florida
    for texto_nodo in soup.find_all(string=re.compile(r"PICK\s*[2-5]", re.I)):
        padre = texto_nodo.find_parent()
        if not padre: continue
        
        nombre = texto_nodo.strip().upper()
        cant = 3 if "3" in nombre else (4 if "4" in nombre else (5 if "5" in nombre else 2))
        
        contenedor = padre.find_parent() or padre
        nums = extraer_numeros(contenedor.get_text(" ", strip=True), cant)
        
        if len(nums) == cant:
            resultados.append({
                "sorteo_nombre": texto_nodo.strip(),
                "fecha": datetime.now().strftime("%Y-%m-%d"),
                "hora": datetime.now().strftime("%H:%M:%S"),
                "numeros": nums,
                "fuente": "florida",
            })
    print(f"✅ Florida: {len(resultados)} resultados.")
    return resultados

def scrape_georgia(page):
    print("🔍 Buscando en Georgia Lottery...")
    resultados = []
    page.goto(URL_GEORGIA, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(6000)
    soup = BeautifulSoup(page.content(), "html.parser")

    for fila in soup.find_all("tr"):
        celdas = [c.get_text(" ", strip=True) for c in fila.find_all("td")]
        if len(celdas) >= 2:
            nombre_juego = celdas[0].strip()
            if any(k in nombre_juego for k in ["Cash 3", "Cash 4", "Georgia Five", "Fantasy 5"]):
                cant = 5 if "Five" in nombre_juego or "Fantasy" in nombre_juego else (4 if "4" in nombre_juego else 3)
                nums = extraer_numeros(celdas[-1], cant)
                if len(nums) == cant:
                    resultados.append({
                        "sorteo_nombre": nombre_juego,
                        "fecha": datetime.now().strftime("%Y-%m-%d"),
                        "hora": datetime.now().strftime("%H:%M:%S"),
                        "numeros": nums,
                        "fuente": "georgia",
                    })
    print(f"✅ Georgia: {len(resultados)} resultados.")
    return resultados

def main():
    todos = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        for funcion in [scrape_conectate, scrape_florida, scrape_georgia]:
            try:
                todos.extend(funcion(page))
            except Exception as e:
                print(f"❌ Error en {funcion.__name__}: {traceback.format_exc()}")
        browser.close()

    with open("resultados.json", "w", encoding="utf-8") as f:
        json.dump(todos, f, ensure_ascii=False, indent=2)
    print(f"💾 Guardados {len(todos)} resultados en total.")

if __name__ == "__main__":
    main()
