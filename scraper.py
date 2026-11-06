import json
import re
import traceback
from datetime import datetime
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

URL_CONECTATE = "https://www.conectate.com.do/loterias/pagina/ultimos-resultados"
URL_FLORIDA = "https://www.flalottery.com/winningNumbers.do"
URL_GEORGIA = "https://www.lotteryusa.com/georgia/"

def limpiar_numeros(lista_nums):
    # Filtra para quedarnos solo con números de 1 o 2 dígitos
    return [n for n in lista_nums if n.isdigit() and len(n) <= 2]

def scrape_conectate(page):
    print("🔍 Buscando en Conectate...")
    resultados = []
    page.goto(URL_CONECTATE, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(8000)
    soup = BeautifulSoup(page.content(), "html.parser")

    # Conectate usa tablas para mostrar los resultados
    for tabla in soup.find_all("table"):
        texto_tabla = tabla.get_text(" ", strip=True)
        # Verificamos si la tabla es de un sorteo conocido
        if any(k in texto_tabla for k in ["Leidsa", "Loteka", "Nacional", "Primera", "Quinielón"]):
            for fila in tabla.find_all("tr"):
                celdas = [c.get_text(" ", strip=True) for c in fila.find_all("td")]
                if len(celdas) >= 2:
                    nombre = celdas[0]
                    # Buscamos números en las celdas de resultados
                    nums = limpiar_numeros(re.findall(r"\b\d{1,2}\b", " ".join(celdas[1:])))
                    if len(nums) >= 2:
                        resultados.append({
                            "sorteo_nombre": nombre,
                            "fecha": datetime.now().strftime("%Y-%m-%d"),
                            "hora": datetime.now().strftime("%H:%M:%S"),
                            "numeros": nums[:3], # Pick 3
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

    # La página de Florida tiene tablas con la clase 'winning-numbers'
    for tabla in soup.find_all("table", class_=re.compile("winning-numbers", re.I)):
        for fila in tabla.find_all("tr"):
            celdas = [c.get_text(" ", strip=True) for c in fila.find_all("td")]
            if len(celdas) >= 2:
                nombre = celdas[0]
                if "PICK" in nombre.upper():
                    cant = 3 if "3" in nombre else (4 if "4" in nombre else (5 if "5" in nombre else 2))
                    nums = limpiar_numeros(re.findall(r"\b\d{1,2}\b", " ".join(celdas[1:])))
                    if len(nums) >= cant:
                        resultados.append({
                            "sorteo_nombre": nombre,
                            "fecha": datetime.now().strftime("%Y-%m-%d"),
                            "hora": datetime.now().strftime("%H:%M:%S"),
                            "numeros": nums[:cant],
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

    # LotteryUSA usa cajas con la clase 'game-card'
    for tarjeta in soup.find_all("div", class_=re.compile("game-card", re.I)):
        titulo = tarjeta.find("h3")
        if not titulo: continue
        
        nombre_juego = titulo.get_text(strip=True)
        if any(k in nombre_juego for k in ["Cash 3", "Cash 4", "Georgia Five", "Fantasy 5"]):
            # Los números están en una lista <ul> con clase 'numbers'
            lista_nums = tarjeta.find("ul", class_=re.compile("numbers", re.I))
            if lista_nums:
                nums = [li.get_text(strip=True) for li in lista_nums.find_all("li")]
                if nums:
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
