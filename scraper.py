import json
import os
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

CUBA_TZ = timezone(timedelta(hours=-4))
URL_MAIN = "https://enloteria.com/resultados-loterias-hoy"
URL_QUEMAITO = "https://enloteria.com/resultados-el-quemaito-mayor-hoy"
URL_QUINIELON = "https://enloteria.com/resultados-el-quinielon-dia-hoy"
ARCHIVO_JSON = "resultados.json"

def fecha_cuba():
    return datetime.now(CUBA_TZ).strftime("%Y-%m-%d")

def extraer_numeros_validos(contenedor):
    bolas = contenedor.find_all("div", class_="result-number")
    numeros = [b.get_text(strip=True) for b in bolas if b.get_text(strip=True).isdigit() and len(b.get_text(strip=True)) >= 2]
    return numeros[:4]

def scroll_hasta_estabilizar(page, max_intentos=20, pausa_ms=4000):
    """Baja hasta que el número de tarjetas deje de aumentar."""
    tarjetas_previas = 0
    for intento in range(max_intentos):
        tarjetas_actuales = page.locator('div[data-lottery-name]').count()
        if tarjetas_actuales == tarjetas_previas:
            print(f"✅ Scroll estabilizado en {tarjetas_actuales} tarjetas tras {intento} intentos.")
            return
        tarjetas_previas = tarjetas_actuales
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(pausa_ms)
    print(f"⚠️ Máximo de intentos alcanzado. Tarjetas: {tarjetas_previas}")

def scrape_principal(page):
    print("Extrayendo página principal...")
    resultados = []
    try:
        page.goto(URL_MAIN, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(15000)  # Espera inicial generosa
        # Espera opcional a que la red se calme (solo si es fiable)
        # page.wait_for_load_state('networkidle', timeout=15000)
        scroll_hasta_estabilizar(page)  # Scroll inteligente
        page.wait_for_timeout(2000)    # Pequeña pausa final
    except Exception as e:
        print(f"  Error durante la carga/scroll: {e}")

    soup = BeautifulSoup(page.content(), "html.parser")
    tarjetas = soup.find_all("div", attrs={"data-lottery-name": True})
    print(f"  Tarjetas encontradas en el HTML: {len(tarjetas)}")

    for tarjeta in tarjetas:
        try:
            nombre = tarjeta.get("data-lottery-name", "").strip()
            if not nombre:
                continue
            numeros = extraer_numeros_validos(tarjeta)
            if numeros and len(numeros) >= 2:
                resultados.append({
                    "sorteo_nombre": nombre,
                    "numeros": numeros,
                    "fecha": fecha_cuba(),
                    "fuente": "enloteria"
                })
                print(f"  OK {nombre} -> {', '.join(numeros)}")
            else:
                print(f"  Omitido (sin números válidos): {nombre}")
        except Exception as e:
            print(f"  Error en tarjeta: {e}")
    return resultados

def scrape_especifica(page, url, nombre_forzado):
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(5000)  # 5 segundos para páginas específicas
        soup = BeautifulSoup(page.content(), "html.parser")
        numeros = extraer_numeros_validos(soup)[:3]
        if numeros and len(numeros) >= 2:
            print(f"  OK {nombre_forzado} -> {', '.join(numeros)}")
            return [{
                "sorteo_nombre": nombre_forzado,
                "numeros": numeros,
                "fecha": fecha_cuba(),
                "fuente": "enloteria"
            }]
        else:
            print(f"  Omitido (sin números válidos): {nombre_forzado}")
    except Exception as e:
        print(f"  Error en {nombre_forzado}: {e}")
    return []

def main():
    todos_nuevos = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        page.set_default_timeout(60000)

        try:
            todos_nuevos.extend(scrape_principal(page))
        except Exception as e:
            print(f"Error principal: {e}")

        try:
            todos_nuevos.extend(scrape_especifica(page, URL_QUEMAITO, "El Quemaito Mayor"))
        except Exception as e:
            print(f"Error Quemaito: {e}")

        try:
            todos_nuevos.extend(scrape_especifica(page, URL_QUINIELON, "El Quinielon Dia"))
        except Exception as e:
            print(f"Error Quinielon: {e}")

        browser.close()

    # --- Acumulación en JSON ---
    guardados = []
    if os.path.exists(ARCHIVO_JSON):
        try:
            with open(ARCHIVO_JSON, "r", encoding="utf-8") as f:
                guardados = json.load(f)
        except Exception:
            guardados = []

    dicc = {f"{r['sorteo_nombre']}|{r['fecha']}": r for r in guardados}
    for nuevo in todos_nuevos:
        dicc[f"{nuevo['sorteo_nombre']}|{nuevo['fecha']}"] = nuevo

    finales = list(dicc.values())
    with open(ARCHIVO_JSON, "w", encoding="utf-8") as f:
        json.dump(finales, f, ensure_ascii=False, indent=2)

    print(f"Total sorteos en JSON: {len(finales)}")
    print(f"Fecha de hoy: {fecha_cuba()}")

if __name__ == "__main__":
    main()
