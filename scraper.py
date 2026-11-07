import json
import traceback
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# Zona horaria Cuba (UTC-4 hasta nov 2027)
CUBA_TZ = timezone(timedelta(hours=-4))

URL_MAIN = "https://enloteria.com/resultados-loterias-hoy"
URL_QUEMAITO = "https://enloteria.com/resultados-el-quemaito-mayor-hoy"
URL_QUINIELON = "https://enloteria.com/resultados-el-quinielon-dia-hoy"


def fecha_cuba():
    return datetime.now(CUBA_TZ).strftime("%Y-%m-%d")


def scrape_principal(page):
    print("Extrayendo pagina principal...")
    resultados = []
    page.goto(URL_MAIN, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(8000)
    try:
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(3000)
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(2000)
    except Exception as e:
        print(f"  Scroll fallo: {e}")

    soup = BeautifulSoup(page.content(), "html.parser")
    tarjetas = soup.find_all("div", attrs={"data-lottery-name": True})
    print(f"  Tarjetas encontradas: {len(tarjetas)}")

    for tarjeta in tarjetas:
        try:
            nombre = tarjeta.get("data-lottery-name", "").strip()
            if not nombre:
                continue
            bolas = tarjeta.find_all("div", class_="result-number")
            numeros = [b.get_text(strip=True) for b in bolas if b.get_text(strip=True)]
            numeros = numeros[:4]
            if numeros and len(numeros) >= 2:
                resultados.append({
                    "sorteo_nombre": nombre,
                    "numeros": numeros,
                    "fecha": fecha_cuba(),
                    "fuente": "enloteria"
                })
                print(f"  OK {nombre} -> {', '.join(numeros)}")
            else:
                print(f"  Sin numeros: {nombre}")
        except Exception as e:
            print(f"  Error en tarjeta: {e}")
    return resultados


def scrape_especifica(page, url, nombre_forzado):
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(4000)
        soup = BeautifulSoup(page.content(), "html.parser")
        bolas = soup.find_all("div", class_="result-number")
        numeros = [b.get_text(strip=True) for b in bolas if b.get_text(strip=True)]
        numeros = numeros[:3]  # FIX: solo 3 numeros (Fijo, Corrido 1, Corrido 2)
        if numeros and len(numeros) >= 2:
            print(f"  OK {nombre_forzado} -> {', '.join(numeros)}")
            return [{
                "sorteo_nombre": nombre_forzado,
                "numeros": numeros,
                "fecha": fecha_cuba(),
                "fuente": "enloteria"
            }]
        else:
            print(f"  Sin numeros: {nombre_forzado}")
    except Exception as e:
        print(f"  Error en {nombre_forzado}: {e}")
    return []


def main():
    todos = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        page.set_default_timeout(60000)
        try:
            todos.extend(scrape_principal(page))
        except Exception as e:
            print(f"Error principal: {e}")
            traceback.print_exc()
        try:
            todos.extend(scrape_especifica(page, URL_QUEMAITO, "El Quemaito Mayor"))
        except Exception as e:
            print(f"Error Quemaito: {e}")
        try:
            todos.extend(scrape_especifica(page, URL_QUINIELON, "El Quinielon Dia"))
        except Exception as e:
            print(f"Error Quinielon: {e}")
        browser.close()

    vistos = set()
    limpios = []
    for r in todos:
        firma = f"{r['sorteo_nombre']}|{'-'.join(r['numeros'])}"
        if firma not in vistos:
            vistos.add(firma)
            limpios.append(r)

    with open("resultados.json", "w", encoding="utf-8") as f:
        json.dump(limpios, f, ensure_ascii=False, indent=2)

    print(f"Total guardados: {len(limpios)} sorteos")
    print(f"Fecha aplicada: {fecha_cuba()}")


if __name__ == "__main__":
    main()
