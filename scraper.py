import json
import re
import traceback
from datetime import datetime
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# --- URLs ---
URL_CONECTATE = "https://www.conectate.com.do/loterias/pagina/ultimos-resultados"
URL_FLORIDA = "https://www.flalottery.com/winningNumbers.do"
URL_GEORGIA = "https://www.lotteryusa.com/georgia/"

def extraer_picks(texto):
    nums = re.findall(r"\b\d{1,5}\b", texto)
    # Ignorar años (ej. 2026) y horas
    nums = [n for n in nums if not (len(n) == 4 and n.startswith("20"))]
    return nums

# --- 1. Conectate (RD) ---
def scrape_conectate(page):
    print("🔍 Buscando en Conectate...")
    resultados = []
    page.goto(URL_CONECTATE, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(8000)
    html = page.content()
    with open("debug_conectate.html", "w", encoding="utf-8") as f:
        f.write(html)
    soup = BeautifulSoup(html, "html.parser")

    for enlace in soup.find_all("a"):
        texto = enlace.get_text(" ", strip=True)
        if re.search(r"\d{2}-\d{2}-\d{4}\s+\d{2}:\d{2}", texto):
            nums = extraer_picks(texto)
            if len(nums) >= 2:
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
    print(f"✅ Conectate: {len(resultados)} resultados.")
    return resultados

# --- 2. Florida Lottery ---
def scrape_florida(page):
    print("🔍 Buscando en Florida Lottery...")
    resultados = []
    page.goto(URL_FLORIDA, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(10000)
    html = page.content()
    with open("debug_florida.html", "w", encoding="utf-8") as f:
        f.write(html)
    soup = BeautifulSoup(html, "html.parser")

    for texto_nodo in soup.find_all(string=re.compile(r"PICK\s*[2-5]|FLORIDA LOTTO", re.I)):
        padre = texto_nodo.find_parent()
        if not padre:
            continue
        contenedor = padre.find_parent() or padre
        texto_bloque = contenedor.get_text(" ", strip=True)
        nums = extraer_picks(texto_bloque)
        if len(nums) >= 3:
            nombre_juego = texto_nodo.strip()[:20]
            resultados.append({
                "sorteo_nombre": nombre_juego,
                "fecha": datetime.now().strftime("%Y-%m-%d"),
                "hora": datetime.now().strftime("%H:%M:%S"),
                "pick2": nums[0] if len(nums) > 0 else None,
                "pick3": nums[1] if len(nums) > 1 else None,
                "pick4": nums[2] if len(nums) > 2 else None,
                "pick5": nums[3] if len(nums) > 3 else None,
                "fuente": "florida",
            })
    print(f"✅ Florida: {len(resultados)} resultados.")
    return resultados

# --- 3. Georgia Lottery (LotteryUSA) ---
def scrape_georgia(page):
    print("🔍 Buscando en Georgia Lottery (LotteryUSA)...")
    resultados = []
    page.goto(URL_GEORGIA, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(6000)
    html = page.content()
    with open("debug_georgia.html", "w", encoding="utf-8") as f:
        f.write(html)
    soup = BeautifulSoup(html, "html.parser")

    # En LotteryUSA los resultados están en tablas
    for fila in soup.find_all("tr"):
        celdas = [c.get_text(" ", strip=True) for c in fila.find_all("td")]
        if len(celdas) < 2:
            continue
        # La primera celda suele ser el nombre del juego, la última los números
        nombre_juego = celdas[0]
        texto_numeros = celdas[-1]
        nums = extraer_picks(texto_numeros)
        if len(nums) >= 2:
            resultados.append({
                "sorteo_nombre": nombre_juego,
                "fecha": datetime.now().strftime("%Y-%m-%d"),
                "hora": datetime.now().strftime("%H:%M:%S"),
                "pick2": nums[0] if len(nums) > 0 else None,
                "pick3": nums[1] if len(nums) > 1 else None,
                "pick4": nums[2] if len(nums) > 2 else None,
                "pick5": nums[3] if len(nums) > 3 else None,
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
                print(f"❌ Error en {funcion.__name__}:")
                print(traceback.format_exc())
        browser.close()

    with open("resultados.json", "w", encoding="utf-8") as f:
        json.dump(todos, f, ensure_ascii=False, indent=2)
    print(f"💾 Guardados {len(todos)} resultados en total.")

if __name__ == "__main__":
    main()
