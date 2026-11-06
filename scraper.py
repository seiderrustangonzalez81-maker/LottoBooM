import json
import re
import traceback
from datetime import datetime
from playwright.sync_api import sync_playwright

# --- URLs de las fuentes oficiales ---
URL_CONECTATE = "https://www.conectate.com.do/loterias/pagina/ultimos-resultados"
URL_FLORIDA = "https://www.flalottery.com/winningNumbers.do"
# URL oficial de la Lotería de Georgia
URL_GEORGIA_OFICIAL = "https://www.galottery.com/en-us/games/cash-3.html" 

def extraer_numeros_puros(texto, cantidad):
    # Extrae solo números de 1 o 2 dígitos que no estén pegados a letras o símbolos
    nums = re.findall(r"(?<![A-Za-z0-9$])\d{1,2}(?![A-Za-z0-9$])", texto)
    if len(nums) >= cantidad:
        return nums[:cantidad]
    return []

def scrape_georgia_oficial(page):
    print("🔍 Buscando en Georgia Lottery (Oficial)...")
    resultados = []
    try:
        # 1. Navegar a la página oficial de Cash 3
        page.goto(URL_GEORGIA_OFICIAL, wait_until="domcontentloaded", timeout=60000)
        # 2. Esperar un tiempo prudencial a que el JavaScript cargue los números
        page.wait_for_timeout(8000) 
        
        # 3. Buscar en todas las filas de la tabla de resultados
        filas = page.locator("tr").all()
        for fila in filas:
            try:
                texto = fila.inner_text().strip()
                # Buscamos filas que contengan "Midday", "Evening" o "Night"
                if any(k in texto for k in ["Midday", "Evening", "Night"]):
                    # Intentamos extraer el nombre del sorteo y los 3 números
                    nombre = texto.split("\n")[0].strip()
                    nums = extraer_numeros_puros(texto, 3)
                    if len(nums) == 3:
                        resultados.append({
                            "sorteo_nombre": f"Georgia Cash 3 {nombre}",
                            "fecha": datetime.now().strftime("%Y-%m-%d"),
                            "numeros": nums,
                            "fuente": "georgia_oficial",
                        })
            except: pass
    except Exception as e:
        print(f"❌ Error en Georgia Oficial: {traceback.format_exc()}")
    
    print(f"✅ Georgia Oficial: {len(resultados)} resultados.")
    return resultados

# (Las funciones scrape_conectate y scrape_florida se mantienen igual que en el código anterior)

def main():
    todos = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        # Ahora solo ejecutamos la extracción de Georgia desde la fuente oficial
        try:
            todos.extend(scrape_georgia_oficial(page))
        except Exception as e:
            print(f"❌ Error general: {traceback.format_exc()}")
        browser.close()

    # Limpieza de duplicados
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
