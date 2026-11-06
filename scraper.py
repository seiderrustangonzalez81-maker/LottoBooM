import json
import re
import traceback
from datetime import datetime
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

URL_CONECTATE = "https://www.conectate.com.do/loterias/pagina/ultimos-resultados"
URL_FLORIDA = "https://www.flalottery.com/winningNumbers.do"
URL_GEORGIA = "https://www.lotteryusa.com/georgia/"

def extraer_numeros_limpios(texto, cantidad):
    # Busca números de 1 o 2 dígitos que NO estén pegados a letras (evita P24) ni a $ (evita $312)
    # El patrón (?<![A-Za-z$]) significa "que no venga precedido de letra o $"
    nums = re.findall(r"(?<![A-Za-z$])\b\d{1,2}\b(?![A-Za-z$])", texto)
    if len(nums) >= cantidad:
        return nums[:cantidad]
    return []

def scrape_conectate(page):
    print("🔍 Buscando en Conectate...")
    resultados = []
    page.goto(URL_CONECTATE, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(8000)
    html = page.content()
    with open("debug_conectate.html", "w", encoding="utf-8") as f:
        f.write(html)
        
    soup = BeautifulSoup(html, "html.parser")
    # Buscamos todas las filas de cualquier tabla
    for fila in soup.find_all("tr"):
        texto = fila.get_text(" ", strip=True)
        if any(k in texto for k in ["Leidsa", "Loteka", "Nacional", "Primera", "Quinielón"]):
            nombre = texto.split(" ")[0] # Tomamos la primera palabra como nombre
            nums = extraer_numeros_limpios(texto, 3)
            if len(nums) >= 2:
                resultados.append({
                    "sorteo_nombre": nombre,
                    "fecha": datetime.now().strftime("%Y-%m-%d"),
                    "numeros": nums[:3],
                    "fuente": "conectate",
                })
    print(f"✅ Conectate: {len(resultados)} resultados.")
    return resultados

def scrape_florida(page):
    print("🔍 Buscando en Florida Lottery...")
    resultados = []
    page.goto(URL_FLORIDA, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(8000)
    html = page.content()
    with open("debug_florida.html", "w", encoding="utf-8") as f:
        f.write(html)
        
    soup = BeautifulSoup(html, "html.parser")
    for fila in soup.find_all("tr"):
        texto = fila.get_text(" ", strip=True)
        if "PICK" in texto.upper():
            cant = 3 if "3" in texto else (4 if "4" in texto else (5 if "5" in texto else 2))
            nums = extraer_numeros_limpios(texto, cant)
            if len(nums) == cant:
                resultados.append({
                    "sorteo_nombre": texto.split(" ")[0] + " " + texto.split(" ")[1], # Ej: PICK 3
                    "fecha": datetime.now().strftime("%Y-%m-%d"),
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
    html = page.content()
    with open("debug_georgia.html", "w", encoding="utf-8") as f:
        f.write(html)
        
    soup = BeautifulSoup(html, "html.parser")
    # Buscamos en todas las filas de tablas (LotteryUSA usa tablas para los juegos)
    for fila in soup.find_all("tr"):
        texto = fila.get_text(" ", strip=True)
        if any(k in texto for k in ["Cash 3", "Cash 4", "Georgia Five"]):
            nombre = "Cash 3" if "Cash 3" in texto else ("Cash 4" if "Cash 4" in texto else "Georgia Five")
            cant = 4 if nombre == "Cash 4" else (5 if nombre == "Georgia Five" else 3)
            nums = extraer_numeros_limpios(texto, cant)
            if len(nums) == cant:
                # Intentamos sacar si es Midday o Evening del texto
                turno = "Midday" if "Midday" in texto else ("Evening" if "Evening" in texto else ("Night" if "Night" in texto else ""))
                nombre_completo = f"{nombre} {turno}".strip()
                
                resultados.append({
                    "sorteo_nombre": nombre_completo,
                    "fecha": datetime.now().strftime("%Y-%m-%d"),
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
            try: todos.extend(funcion(page))
            except Exception as e: print(f"❌ Error: {traceback.format_exc()}")
        browser.close()

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
