import json
import os
import time
import re
import requests
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# ═══════════════════════════════════════════════════════════════
# ZONAS HORARIAS
#   Cuba: UTC-4 hasta 07/11/2027 (America/Havana)
#   Este EE.UU.: UTC-5 en invierno, UTC-4 en verano (America/New_York)
# ═══════════════════════════════════════════════════════════════
TZ_CUBA = ZoneInfo("America/Havana")
TZ_ESTE = ZoneInfo("America/New_York")

URL_MAIN = "https://enloteria.com/resultados-loterias-hoy"
URL_QUEMAITO = "https://enloteria.com/resultados-el-quemaito-mayor-hoy"
URL_QUINIELON = "https://enloteria.com/resultados-el-quinielon-dia-hoy"
ARCHIVO_JSON = "resultados.json"

# ═══════════════════════════════════════════════════════════════
# URLs LOTTERYUSA (12 rutas validadas)
# ═══════════════════════════════════════════════════════════════
URLS_MULTI = {
    "Florida 1:35 PM": {
        "pick2": ["https://www.lotteryusa.com/florida/pick-2-midday/"],
        "pick3": ["https://www.lotteryusa.com/florida/midday-pick-3/"],
        "pick4": ["https://www.lotteryusa.com/florida/midday-pick-4/"],
        "pick5": ["https://www.lotteryusa.com/florida/pick-5-midday/"],
    },
    "Florida 9:45 PM": {
        "pick2": ["https://www.lotteryusa.com/florida/pick-2/"],
        "pick3": ["https://www.lotteryusa.com/florida/pick-3/"],
        "pick4": ["https://www.lotteryusa.com/florida/pick-4/"],
        "pick5": ["https://www.lotteryusa.com/florida/pick-5/"],
    },
    "Texas 1:20 PM": {
        "pick3": ["https://www.lotteryusa.com/texas/midday-pick-3/"]
    },
    "Texas 10:12 PM": {
        "pick3": ["https://www.lotteryusa.com/texas/pick-3/"]
    },
    "New York 2:30 PM": {
        "pick3": ["https://www.lotteryusa.com/new-york/midday-numbers/"]
    },
    "New York 10:30 PM": {
        "pick3": ["https://www.lotteryusa.com/new-york/numbers/"]
    },
    "New Jersey 12:50 PM": {
        "pick3": ["https://www.lotteryusa.com/new-jersey/midday-pick-3/"],
        "pick4": ["https://www.lotteryusa.com/new-jersey/midday-pick-4/"]
    },
    "New Jersey 10:57 PM": {
        "pick3": ["https://www.lotteryusa.com/new-jersey/pick-3/"],
        "pick4": ["https://www.lotteryusa.com/new-jersey/pick-4/"]
    },
    "Georgia 12:30 PM": {
        "pick3": ["https://www.lotteryusa.com/georgia/cash-3-midday/"],
        "pick4": ["https://www.lotteryusa.com/georgia/cash-4-midday/"]
    },
    "Georgia 11:40 PM": {
        "pick3": ["https://www.lotteryusa.com/georgia/cash-3-evening/"],
        "pick4": ["https://www.lotteryusa.com/georgia/cash-4-evening/"]
    },
    "Tennessee 1:20 PM": {
        "pick3": ["https://www.lotteryusa.com/tennessee/cash-3-midday/"],
        "pick4": ["https://www.lotteryusa.com/tennessee/cash-4-midday/"]
    },
    "Tennessee 6:30 PM": {
        "pick3": ["https://www.lotteryusa.com/tennessee/cash-3/"],
        "pick4": ["https://www.lotteryusa.com/tennessee/cash-4/"]
    },
}

# ═══════════════════════════════════════════════════════════════
# NOMBRES DE ENLOTERIA-USA A IGNORAR
# ═══════════════════════════════════════════════════════════════
NOMBRES_IGNORADOS = {
    "Georgia Día", "Georgia Tarde",
    "Florida Tarde", "Florida Noche",
    "New York Tarde",
    "New Jersey Tarde",
    "Texas Tarde",
    "Tennessee Día",
}

# ═══════════════════════════════════════════════════════════════
# UTILIDADES DE FECHA/HORA
# ═══════════════════════════════════════════════════════════════
def fecha_cuba():
    return datetime.now(TZ_CUBA).strftime("%Y-%m-%d")

def fecha_este():
    return datetime.now(TZ_ESTE).strftime("%Y-%m-%d")

HORAS_POR_PALABRA = {
    'MADRUGADA': 3,
    'DIA': 12, 'DÍA': 12, 'MEDIODIA': 12, 'MEDIODÍA': 12,
    'TARDE': 15,
    'NOCHE': 21,
    'MAYOR': 21,
}

def parsear_hora_sorteo(nombre):
    """Extrae la hora del sorteo del nombre. Retorna (hora, minuto) o None."""
    m = re.search(r'(\d{1,2})(?::(\d{2}))?\s*(AM|PM)', nombre, re.IGNORECASE)
    if m:
        hora = int(m.group(1))
        minuto = int(m.group(2)) if m.group(2) else 0
        ampm = m.group(3).upper()
        if ampm == 'PM' and hora != 12:
            hora += 12
        elif ampm == 'AM' and hora == 12:
            hora = 0
        return (hora, minuto)
    nombre_upper = nombre.upper()
    for palabra, hora in HORAS_POR_PALABRA.items():
        if palabra in nombre_upper:
            return (hora, 0)
    return None

def calcular_fecha_sorteo_enloteria(nombre):
    """Calcula la fecha correcta del sorteo en enloteria según su hora."""
    ahora_cuba = datetime.now(TZ_CUBA)
    hora_sorteo = parsear_hora_sorteo(nombre)

    if hora_sorteo:
        hora, minuto = hora_sorteo
        hoy_sorteo = ahora_cuba.replace(hour=hora, minute=minuto, second=0, microsecond=0)
        if ahora_cuba >= hoy_sorteo:
            return ahora_cuba.strftime("%Y-%m-%d")
        else:
            return (ahora_cuba - timedelta(days=1)).strftime("%Y-%m-%d")

    if ahora_cuba.hour < 6:
        return (ahora_cuba - timedelta(days=1)).strftime("%Y-%m-%d")
    return ahora_cuba.strftime("%Y-%m-%d")

def calcular_fecha_esperada_usa(nombre_db):
    """
    Calcula la fecha del sorteo en la zona Eastern basándose en la hora
    programada del nombre.

    Motivo: para sorteos nocturnos (ej. Georgia 11:34 PM), la tarjeta de
    lotteryusa muestra el PRÓXIMO sorteo, no el último resultado. Si se
    confía en esa fecha, un resultado del 7 de noviembre se archivaría
    como 8 de noviembre. Con este cálculo, la fecha asignada es siempre
    la del día en que ocurrió realmente el sorteo.

    Regla:
      - Si en el Este ya pasó la hora del sorteo hoy -> hoy
      - Si aún no ha pasado -> ayer
    """
    hora_sorteo = parsear_hora_sorteo(nombre_db)
    if not hora_sorteo:
        return fecha_este()

    ahora_este = datetime.now(TZ_ESTE)
    hora, minuto = hora_sorteo
    hoy_sorteo = ahora_este.replace(hour=hora, minute=minuto, second=0, microsecond=0)

    if ahora_este >= hoy_sorteo:
        return ahora_este.strftime("%Y-%m-%d")
    else:
        return (ahora_este - timedelta(days=1)).strftime("%Y-%m-%d")

def normalizar_nombre(nombre):
    """Normaliza espacios múltiples y recorta."""
    return " ".join(nombre.split())

def extraer_numeros_validos(tarjeta_o_soup):
    """
    Extrae números de una tarjeta de enloteria.
    ...
    """
    # ─── OPCIÓN PRINCIPAL ───
    bolas = tarjeta_o_soup.find_all(class_="result-number")

    # ─── FALLBACK (plan B) ─── ESTO ES LO QUE YA ESTÁ
    if not bolas:
        for clase in ("result-number__ball", "draw-result-number",
                      "result__number", "numero-resultado"):
            bolas = tarjeta_o_soup.find_all(class_=clase)
            if bolas:
                break

    numeros = []
    for b in bolas:
        texto = b.get_text(strip=True)
        if texto.isdigit() and len(texto) >= 2:
            numeros.append(texto)
    return numeros[:4]

# ═══════════════════════════════════════════════════════════════
# 1. SCRAPING ENLOTERIA (scroll dinámico)
# ═══════════════════════════════════════════════════════════════
def scroll_hasta_estabilizar(page, max_intentos=20, pausa_ms=3000):
    previas = 0
    for _ in range(max_intentos):
        actuales = page.locator('div[data-lottery-name]').count()
        if actuales == previas:
            print(f"  ✅ Scroll completado. Tarjetas: {actuales}")
            return
        previas = actuales
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(pausa_ms)
    print(f"  ⚠️ Máximo de scrolls alcanzado. Tarjetas: {previas}")

def scrape_principal(page):
    print("Extrayendo enloteria (principal)...")
    resultados = []
    try:
        page.goto(URL_MAIN, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(5000)
        scroll_hasta_estabilizar(page)
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(1000)
    except Exception as e:
        print(f"  Error en scroll principal: {e}")

    soup = BeautifulSoup(page.content(), "html.parser")
    tarjetas = soup.find_all("div", attrs={"data-lottery-name": True})
    print(f"  Tarjetas encontradas: {len(tarjetas)}")

      # ─── DEBUG TEMPORAL: HTML completo de la primera tarjeta ───
    total_result_number = len(soup.find_all(class_="result-number"))
    print(f"  DEBUG class='result-number' (cualquier tag): {total_result_number}")
    if tarjetas:
        primera = tarjetas[0]
        print(f"  DEBUG HTML COMPLETO primera tarjeta:")
        print(str(primera))
        print(str(primera))  # <-- Sin recortar
    # ─── FIN DEBUG TEMPORAL ───

    for tarjeta in tarjetas:
        try:
            nombre = normalizar_nombre(tarjeta.get("data-lottery-name", "").strip())
            if not nombre:
                continue
            if nombre in NOMBRES_IGNORADOS:
                continue
            numeros = extraer_numeros_validos(tarjeta)
            if numeros and len(numeros) >= 2:
                resultados.append({
                    "sorteo_nombre": nombre,
                    "numeros": numeros,
                    "fecha": calcular_fecha_sorteo_enloteria(nombre),
                    "fuente": "enloteria",
                })
        except Exception as e:
            print(f"  Error procesando tarjeta: {e}")
    return resultados

def scrape_especifica(page, url, nombre_forzado):
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(4000)
        soup = BeautifulSoup(page.content(), "html.parser")
        numeros = extraer_numeros_validos(soup)[:3]
        if numeros and len(numeros) >= 2:
            return [{
                "sorteo_nombre": nombre_forzado,
                "numeros": numeros,
                "fecha": calcular_fecha_sorteo_enloteria(nombre_forzado),
                "fuente": "enloteria",
            }]
    except Exception as e:
        print(f"  Error en scrape_especifica {nombre_forzado}: {e}")
    return []

# ═══════════════════════════════════════════════════════════════
# 2. SCRAPING LOTTERYUSA (retry + fallbacks + log detallado)
# ═══════════════════════════════════════════════════════════════
def _extraer_tarjeta_lotteryusa(soup):
    tarjeta = soup.find('tr', class_='c-draw-card')
    if tarjeta:
        return tarjeta
    for sel in [
        {'name': 'tr', 'attrs': {'class': lambda c: c and 'c-draw-card' in c}},
        {'name': 'div', 'attrs': {'class': lambda c: c and 'c-draw-card' in c}},
        {'name': 'tr', 'attrs': {'class': lambda c: c and 'draw-card' in c}},
        {'name': 'div', 'attrs': {'class': lambda c: c and 'draw-card' in c}},
    ]:
        tarjeta = soup.find(**sel)
        if tarjeta:
            return tarjeta
    return None

def _extraer_fecha_lotteryusa(tarjeta, nombre_db):
    fecha_nodo = tarjeta.find('time', class_='c-draw-card__draw-date')
    if not fecha_nodo:
        fecha_nodo = tarjeta.find('time')
    if not fecha_nodo:
        for tag in tarjeta.find_all(['span', 'div', 'p']):
            if re.search(r'[A-Z][a-z]{2}\s+\d{1,2},\s+\d{4}', tag.get_text(strip=True)):
                fecha_nodo = tag
                break
    if not fecha_nodo:
        return None

    fecha_texto = fecha_nodo.get_text(strip=True)
    for dia in ['Sunday,', 'Monday,', 'Tuesday,', 'Wednesday,',
                'Thursday,', 'Friday,', 'Saturday,']:
        fecha_texto = fecha_texto.replace(dia, '').strip()
    try:
        return datetime.strptime(fecha_texto, '%b %d, %Y').strftime('%Y-%m-%d')
    except ValueError:
        print(f"  ⚠️ Fecha inválida '{fecha_texto}' en {nombre_db}")
        return None

def _extraer_numeros_lotteryusa(tarjeta):
    nodos = tarjeta.select('ul.c-result.c-draw-card__ball-list > li.c-ball')
    if nodos:
        return [n.get_text(strip=True) for n in nodos]
    for sel in ['li.c-ball', 'li.c-result__ball', '.c-ball', '.ball']:
        nodos = tarjeta.select(sel)
        if nodos:
            return [n.get_text(strip=True) for n in nodos]
    return []

def scrape_lotteryusa():
    print("Extrayendo USA (lotteryusa.com)...")
    resultados = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    print(f"  Fecha actual Este (EE.UU.): {fecha_este()}")
    print(f"  Fecha actual Cuba: {fecha_cuba()}")

    for nombre_db, juegos in URLS_MULTI.items():
        fecha_esperada = calcular_fecha_esperada_usa(nombre_db)
        resultado_sorteo = {
            "sorteo_nombre": nombre_db,
            "fecha": fecha_esperada,
            "fuente": "lotteryusa",
            "pick2": "", "pick3": "", "pick4": "", "pick5": "",
            "fijo": "", "corrido_1": "", "corrido_2": "",
        }
        
        exito_total = False
        
        for juego, urls in juegos.items():
            exito_juego = False
            for url in urls:
                if exito_juego: break
                for intento in range(3):
                    try:
                        resp = requests.get(f"{url}?nocache={int(time.time(, timeout=20))}", headers=headers, timeout=25)
                        if resp.status_code == 404:
                            break # Pasar a la URL de respaldo
                            
                        resp.raise_for_status()
                        soup = BeautifulSoup(resp.text, 'html.parser')
                        tarjeta = _extraer_tarjeta_lotteryusa(soup)
                        
                        if not tarjeta:
                            continue
                            
                        fecha_tarjeta = _extraer_fecha_lotteryusa(tarjeta, nombre_db)
                        fecha_hoy_et = datetime.now(ZoneInfo('America/New_York')).strftime('%Y-%m-%d')
                if fecha_tarjeta != fecha_hoy_et:
                            exito_juego = True # El juego existe pero no es de hoy
                            break
                            
                        numeros = _extraer_numeros_lotteryusa(tarjeta)
                        if not numeros:
                            continue
                            
                        if juego == "pick2":
                            resultado_sorteo["pick2"] = "".join(numeros[:2])
                        elif juego == "pick3":
                            resultado_sorteo["pick3"] = "".join(numeros[:3])
                            if len(numeros) >= 3:
                                resultado_sorteo["fijo"] = str(numeros[0]).zfill(2)
                                resultado_sorteo["corrido_1"] = str(numeros[1]).zfill(2)
                                resultado_sorteo["corrido_2"] = str(numeros[2]).zfill(2)
                        elif juego == "pick4":
                            resultado_sorteo["pick4"] = "".join(numeros[:4])
                        elif juego == "pick5":
                            resultado_sorteo["pick5"] = "".join(numeros[:5])
                            
                        print(f"  ✅ OK {nombre_db} - {juego} -> {', '.join(numeros)}")
                        exito_juego = True
                        exito_total = True
                        break 
                    except Exception as e:
                        print(f"  ❌ [{nombre_db} - {juego}] Error intento {intento+1} ({url}): {e}")
                        time.sleep(2)
        
        if exito_total:
            resultados.append(resultado_sorteo)
        else:
            print(f"  ⚠️ No se pudo extraer ningún dato nuevo para {nombre_db}. Se conservará el anterior.")

    return resultados

def main():
    todos_nuevos = []
    hoy_cuba = fecha_cuba()
    ayer_cuba = (datetime.now(TZ_CUBA) - timedelta(days=1)).strftime("%Y-%m-%d")

    print("=== INICIO SCRAPER ===")
    print(f"Fecha Cuba: {hoy_cuba}")
    print(f"Fecha Este: {fecha_este()}")

    # --- Playwright (enloteria) ---
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        page.set_default_timeout(60000)
        try:
            res = scrape_principal(page)
            print(f"  → {len(res)} sorteos de principal")
            todos_nuevos.extend(res)
        except Exception as e:
            print(f"Error principal: {e}")
        try:
            res = scrape_especifica(page, URL_QUEMAITO, "El Quemaito Mayor")
            if res:
                print("  → El Quemaito Mayor OK")
            todos_nuevos.extend(res)
        except Exception as e:
            print(f"Error Quemaito: {e}")
        try:
            res = scrape_especifica(page, URL_QUINIELON, "El Quinielon Dia")
            if res:
                print("  → El Quinielon Dia OK")
            todos_nuevos.extend(res)
        except Exception as e:
            print(f"Error Quinielon: {e}")
        browser.close()

    # --- Requests (lotteryusa) ---
    try:
        res = scrape_lotteryusa()
        print(f"  → {len(res)} sorteos de lotteryusa")
        todos_nuevos.extend(res)
    except Exception as e:
        print(f"Error en lotteryusa: {e}")

    # --- Acumulación en JSON (conserva hoy y ayer) ---
    guardados = []
    if os.path.exists(ARCHIVO_JSON):
        try:
            with open(ARCHIVO_JSON, "r", encoding="utf-8") as f:
                guardados = json.load(f)
        except Exception:
            guardados = []

    dic = {}
    for r in guardados:
        if r.get("fecha") in (hoy_cuba, ayer_cuba):
            dic[f"{r['sorteo_nombre']}|{r['fecha']}"] = r
    for n in todos_nuevos:
        dic[f"{n['sorteo_nombre']}|{n['fecha']}"] = n

    # === FILTRO FINAL: Solo mantener resultados de HOY en ET ===
    hoy_et = datetime.now(ZoneInfo('America/New_York')).strftime('%Y-%m-%d')
    finales_filtrados = [r for r in dic.values() if r.get('fecha') == hoy_et]

    # Si no hay resultados de hoy, el JSON queda vacio (mejor que mostrar datos viejos)
    with open(ARCHIVO_JSON, "w", encoding="utf-8") as f:
        json.dump(finales_filtrados, f, ensure_ascii=False, indent=2)

    print(f"Filtro aplicado: {len(finales_filtrados)} resultados de hoy ({hoy_et}) guardados.")

    print("\n=== RESUMEN ===")
    print(f"Total sorteos en JSON: {len(finales)}")
    print(f"Fecha Cuba: {hoy_cuba}")

if __name__ == "__main__":
    main()
