import json
import re
import traceback
from datetime import datetime
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# --- URLs ---
URL_CONECTATE = "https://www.conectate.com.do/loterias/pagina/ultimos-resultados"
URL_FLORIDA = "https://www.flalottery.com/winningNumbers.do"
URL_GEORGIA = "https://www.lotteryusa.com/georgia/" # Usamos LotteryUSA que tiene tablas HTML limpias

def extraer_numeros(texto, cantidad_esperada):
    # Busca números de 1 o 2 dígitos
    nums = re.findall(r"\b\d{1,2}\b", texto)
    # Filtra para quedarnos solo con la cantidad exacta de números que necesita el sorteo
    if len(nums) >= cantidad_esperada:
        return nums[:cantidad_esperada]
    return []

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
            # Asumimos que los sorteos dominicanos suelen ser Pick 2 o Pick 3
            nums = extraer_numeros(texto, 3) 
            if len(nums) >= 2:
                nombre_juego = re.split(r"\d{2}-\d{2}-\d{4}", texto)[0].strip()
                resultados.append({
                    "sorteo_nombre": nombre_juego,
                    "fecha": datetime.now().strftime("%Y-%m-%d"),
                    "hora": datetime.now().strftime("%H:%M:%S"),
                    "numeros": nums,
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

    for texto_nodo in soup.find_all(string=re.compile(r"PICK\s*[2-5]", re.I)):
        padre = texto_nodo.find_parent()
        if not padre: continue
        
        # Determinamos cuántos números buscar según el nombre (Pick 3 = 3 números)
        nombre = texto_nodo.strip().upper()
        cant = 3 if "3" in nombre else (4 if "4" in nombre else (5 if "5" in nombre else 2))
        
        contenedor = padre.find_parent() or padre
        nums = extraer_numeros(contenedor.get_text(" ", strip=True), cant)
        
        if len(nums) == cant:
            resultados.append({
                "sorteo_nombre": texto_nodo.strip()[:20],
                "fecha": datetime.now().strftime("%Y-%m-%d"),
                "hora": datetime.now().strftime("%H:%M:%S"),
                "numeros": nums,
                "fuente": "florida",
            })
    print(f"✅ Florida: {len(resultados)} resultados.")
    return resultados

# --- 3. Georgia Lottery (Estrategia de Tabla) ---
def scrape_georgia(page):
    print("🔍 Buscando en Georgia Lottery...")
    resultados = []
    page.goto(URL_GEORGIA, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(6000)
    html = page.content()
    with open("debug_georgia.html", "w", encoding="utf-8") as f:
        f.write(html)
    soup = BeautifulSoup(html, "html.parser")

    # Buscamos las filas de las tablas
    for fila in soup.find_all("tr"):
        celdas = [c.get_text(" ", strip=True) for c in fila.find_all("td")]
        
        # Si la fila tiene al menos 2 columnas (Nombre y Números)
        if len(celdas) >= 2:
            nombre_juego = celdas[0].strip()
            texto_numeros = celdas[-1].strip() # Los números suelen estar al final
            
            # Verificamos que sea un juego de Georgia
            if any(k in nombre_juego for k in ["Cash 3", "Cash 4", "Georgia Five", "Fantasy 5"]):
                # Determinamos la cantidad de números
                cant = 5 if "Five" in nombre_juego or "Fantasy" in nombre_juego else (4 if "4" in nombre_juego else 3)
                
                nums = extraer_numeros(texto_numeros, cant)
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
                print(f"❌ Error en {funcion.__name__}:")
                print(traceback.format_exc())
                
        browser.close()

    # Limpieza final: eliminar duplicados exactos (mismo sorteo y mismos números)
    vistos = set()
    limpios = []
    for r in todos:
        firma = f"{r['sorteo_nombre']}-{'-'.join(r['numeros'])}"
        if firma not in vistos:
            vistos.add(firma)
            limpios.append(r)

    with open("resultados.json", "w", encoding="utf-8") as f:
        json.dump(limpios, f, ensure_ascii=False, indent=2)
    print(f"💾 Guardados {len(limpios)} resultados únicos en total.")

if __name__ == "__main__":
    main()
