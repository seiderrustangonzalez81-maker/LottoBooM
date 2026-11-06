import json
import re
import traceback
from datetime import datetime
from playwright.sync_api import sync_playwright

URL_CONECTATE = "https://www.conectate.com.do/loterias/pagina/ultimos-resultados"
URL_FLORIDA = "https://www.flalottery.com/winningNumbers.do"
URL_GEORGIA = "https://www.lotteryusa.com/georgia/"

def scrape_conectate(page):
    print("🔍 Buscando en Conectate...")
    resultados = []
    try:
        page.goto(URL_CONECTATE, wait_until="domcontentloaded", timeout=25000)
        page.wait_for_timeout(5000)
        # Buscamos los enlaces que tengan los resultados
        enlaces = page.locator("a").all()
        for enlace in enlaces:
            texto = enlace.inner_text().strip()
            if any(k in texto for k in ["Leidsa", "Loteka", "Nacional", "Primera"]):
                nums = re.findall(r"\b\d{1,2}\b", texto)
                if len(nums) >= 3:
                    resultados.append({
                        "sorteo_nombre": texto.split("\n")[0].strip(),
                        "fecha": datetime.now().strftime("%Y-%m-%d"),
                        "numeros": nums[:3],
                        "fuente": "conectate",
                    })
    except Exception as e:
        print(f"⚠️ Conectate falló: {e}")
    print(f"✅ Conectate: {len(resultados)} resultados.")
    return resultados

def scrape_florida(page):
    print("🔍 Buscando en Florida Lottery...")
    resultados = []
    try:
        page.goto(URL_FLORIDA, wait_until="domcontentloaded", timeout=25000)
        page.wait_for_timeout(5000)
        # Buscamos los contenedores de resultados
        bloques = page.locator("div.winning-numbers, table").all()
        for bloque in bloques:
            texto = bloque.inner_text().strip()
            if "PICK" in texto.upper():
                cant = 3 if "3" in texto else (4 if "4" in texto else 2)
                nums = re.findall(r"(?<![A-Za-z$])\b\d{1,2}\b(?![A-Za-z$])", texto)
                if len(nums) >= cant:
                    nombre = "PICK 3" if "3" in texto else ("PICK 4" if "4" in texto else "PICK 2")
                    resultados.append({
                        "sorteo_nombre": nombre,
                        "fecha": datetime.now().strftime("%Y-%m-%d"),
                        "numeros": nums[:cant],
                        "fuente": "florida",
                    })
    except Exception as e:
        print(f"⚠️ Florida falló: {e}")
    print(f"✅ Florida: {len(resultados)} resultados.")
    return resultados

def scrape_georgia(page):
    print("🔍 Buscando en Georgia Lottery...")
    resultados = []
    try:
        page.goto(URL_GEORGIA, wait_until="domcontentloaded", timeout=25000)
        page.wait_for_timeout(5000)
        
        # ESTA ES LA MAGIA: Buscamos las tarjetas de juego (game-card)
        tarjetas = page.locator("div.game-card").all()
        for tarjeta in tarjetas:
            try:
                titulo_elem = tarjeta.locator("h3").first
                if not titulo_elem.is_visible(): continue
                titulo = titulo_elem.inner_text().strip()
                
                if any(k in titulo for k in ["Cash 3", "Cash 4", "Georgia Five"]):
                    # Buscamos SOLO los elementos de lista <li> que son las bolitas de números
                    numeros_bolitas = tarjeta.locator("ul li").all_inner_texts()
                    nums = [n.strip() for n in numeros_bolitas if n.strip().isdigit()]
                    
                    if len(nums) > 0:
                        resultados.append({
                            "sorteo_nombre": titulo,
                            "fecha": datetime.now().strftime("%Y-%m-%d"),
                            "numeros": nums,
                            "fuente": "georgia",
                        })
            except:
                pass
    except Exception as e:
        print(f"⚠️ Georgia falló: {e}")
    print(f"✅ Georgia: {len(resultados)} resultados.")
    return resultados

def main():
    todos = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_default_timeout(25000) 
        
        # Ponemos Georgia primero para asegurar que atrapamos sus números
        for funcion in [scrape_georgia, scrape_florida, scrape_conectate]: 
            try: todos.extend(funcion(page))
            except Exception as e: print(f"❌ Error general: {e}")
        browser.close()

    # Limpieza de duplicados exactos
    vistos = set()
    limpios = []
    for r in todos:
        # Solo agregamos si tiene números válidos y el nombre no está vacío
        if r['numeros'] and r['sorteo_nombre']:
            firma = f"{r['sorteo_nombre']}-{'-'.join(r['numeros'])}"
            if firma not in vistos:
                vistos.add(firma)
                limpios.append(r)

    with open("resultados.json", "w", encoding="utf-8") as f:
        json.dump(limpios, f, ensure_ascii=False, indent=2)
    print(f"💾 Guardados {len(limpios)} resultados reales.")

if __name__ == "__main__":
    main()
