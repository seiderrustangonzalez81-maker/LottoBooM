import json
import re
import traceback
from datetime import datetime
from playwright.sync_api import sync_playwright

URL_CONECTATE = "https://www.conectate.com.do/loterias/pagina/ultimos-resultados"
URL_FLORIDA = "https://www.flalottery.com/winningNumbers.do"
URL_GEORGIA = "https://www.lotteryusa.com/georgia/"

def limpiar_numeros(lista_nums):
    return [n for n in lista_nums if n.isdigit() and len(n) <= 2]

def scrape_conectate(page):
    print("🔍 Buscando en Conectate...")
    resultados = []
    page.goto(URL_CONECTATE, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(10000) # Esperar a que carguen los números (JavaScript)

    # Buscamos todas las filas de tabla (tr) en la página
    filas = page.locator("tr").all()
    for fila in filas:
        try:
            texto = fila.inner_text().strip()
            # Si la fila contiene el nombre de una lotería dominicana
            if any(k in texto for k in ["Leidsa", "Loteka", "Nacional", "Primera", "Quinielón", "Real"]):
                # Extraemos el nombre (primera palabra o frase)
                nombre = texto.split("\n")[0].strip()
                # Buscamos números en el texto de la fila
                nums = limpiar_numeros(re.findall(r"\b\d{1,2}\b", texto))
                if len(nums) >= 2:
                    resultados.append({
                        "sorteo_nombre": nombre,
                        "fecha": datetime.now().strftime("%Y-%m-%d"),
                        "hora": datetime.now().strftime("%H:%M:%S"),
                        "numeros": nums[:3], # Guardamos máximo 3 números
                        "fuente": "conectate",
                    })
        except:
            pass
    print(f"✅ Conectate: {len(resultados)} resultados.")
    return resultados

def scrape_florida(page):
    print("🔍 Buscando en Florida Lottery...")
    resultados = []
    page.goto(URL_FLORIDA, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(10000)

    filas = page.locator("tr").all()
    for fila in filas:
        try:
            texto = fila.inner_text().strip()
            if "PICK" in texto.upper():
                nombre = texto.split("\n")[0].strip()
                cant = 3 if "3" in nombre else (4 if "4" in nombre else (5 if "5" in nombre else 2))
                nums = limpiar_numeros(re.findall(r"\b\d{1,2}\b", texto))
                if len(nums) >= cant:
                    resultados.append({
                        "sorteo_nombre": nombre,
                        "fecha": datetime.now().strftime("%Y-%m-%d"),
                        "hora": datetime.now().strftime("%H:%M:%S"),
                        "numeros": nums[:cant],
                        "fuente": "florida",
                    })
        except:
            pass
    print(f"✅ Florida: {len(resultados)} resultados.")
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
                nums = limpiar_numeros(re.findall(r"\b\d{1,2}\b", texto))
                if len(nums) >= cant:
                    resultados.append({
                        "sorteo_nombre": nombre,
                        "fecha": datetime.now().strftime("%Y-%m-%d"),
                        "hora": datetime.now().strftime("%H:%M:%S"),
                        "numeros": nums[:cant],
                        "fuente": "georgia",
                    })
        except:
            pass
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
