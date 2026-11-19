import json
import os
import re
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
# IMPORTANTE: Usamos curl_cffi en vez de requests
from curl_cffi import requests 

TZ_CUBA = ZoneInfo("America/Havana")
TZ_ESTE = ZoneInfo("America/New_York")

URL_MAIN = "https://enloteria.com/resultados-loterias-hoy"
URL_QUEMAITO = "https://enloteria.com/resultados-el-quemaito-mayor-hoy"
URL_QUINIELON = "https://enloteria.com/resultados-el-quinielon-dia-hoy"
ARCHIVO_JSON = "resultados.json"

URLS_MULTI = {
    "Florida 1:35 PM": {"pick2": ["https://www.lotteryusa.com/florida/pick-2-midday/"], "pick3": ["https://www.lotteryusa.com/florida/midday-pick-3/"], "pick4": ["https://www.lotteryusa.com/florida/midday-pick-4/"], "pick5": ["https://www.lotteryusa.com/florida/pick-5-midday/"]},
    "Florida 9:45 PM": {"pick2": ["https://www.lotteryusa.com/florida/pick-2/"], "pick3": ["https://www.lotteryusa.com/florida/pick-3/"], "pick4": ["https://www.lotteryusa.com/florida/pick-4/"], "pick5": ["https://www.lotteryusa.com/florida/pick-5/"]},
    "Texas 1:20 PM": {"pick3": ["https://www.lotteryusa.com/texas/midday-pick-3/"]},
    "Texas 10:12 PM": {"pick3": ["https://www.lotteryusa.com/texas/pick-3/"]},
    "New York 2:30 PM": {"pick3": ["https://www.lotteryusa.com/new-york/midday-numbers/"], "pick4": ["https://www.lotteryusa.com/new-york/midday-win-4/"]},
    "New York 10:30 PM": {"pick3": ["https://www.lotteryusa.com/new-york/numbers/"], "pick4": ["https://www.lotteryusa.com/new-york/win-4/"]},
    "New Jersey 12:50 PM": {"pick3": ["https://www.lotteryusa.com/new-jersey/midday-pick-3/"], "pick4": ["https://www.lotteryusa.com/new-jersey/midday-pick-4/"]},
    "New Jersey 10:57 PM": {"pick3": ["https://www.lotteryusa.com/new-jersey/pick-3/"], "pick4": ["https://www.lotteryusa.com/new-jersey/pick-4/"]},
    "Georgia 12:30 PM": {"pick3": ["https://www.lotteryusa.com/georgia/midday-3/"], "pick4": ["https://www.lotteryusa.com/georgia/midday-4/"]},
    "Georgia 6:59 PM": {"pick3": ["https://www.lotteryusa.com/georgia/cash-3-evening/"], "pick4": ["https://www.lotteryusa.com/georgia/cash-4-evening/"]},
    "Georgia 11:34 PM": {"pick3": ["https://www.lotteryusa.com/georgia/cash-3/"], "pick4": ["https://www.lotteryusa.com/georgia/cash-4/"]},
    "Tennessee 1:20 PM": {"pick3": ["https://www.lotteryusa.com/tennessee/midday-cash-3/"], "pick4": ["https://www.lotteryusa.com/tennessee/midday-cash-4/"]},
    "Tennessee 6:30 PM": {"pick3": ["https://www.lotteryusa.com/tennessee/cash-3/"], "pick4": ["https://www.lotteryusa.com/tennessee/cash-4/"]},
}
NOMBRES_IGNORADOS = {"Georgia Día", "Georgia Tarde", "Florida Tarde", "Florida Noche", "New York Tarde", "New Jersey Tarde", "Texas Tarde", "Tennessee Día"}

HORAS_POR_PALABRA = {'MADRUGADA': 3, 'DIA': 12, 'DÍA': 12, 'MEDIODIA': 12, 'MEDIODÍA': 12, 'TARDE': 15, 'NOCHE': 21, 'MAYOR': 21}

def parsear_hora_sorteo(nombre):
    m = re.search(r'(\d{1,2})(?::(\d{2}))?\s*(AM|PM)', nombre, re.IGNORECASE)
    if m:
        hora, minuto, ampm = int(m.group(1)), int(m.group(2) or 0), m.group(3).upper()
        if ampm == 'PM' and hora != 12: hora += 12
        elif ampm == 'AM' and hora == 12: hora = 0
        return (hora, minuto)
    for palabra, hora in HORAS_POR_PALABRA.items():
        if palabra in nombre.upper(): return (hora, 0)
    return None

def calcular_fecha_sorteo_enloteria(nombre):
    ahora_cuba = datetime.now(TZ_CUBA)
    hora_sorteo = parsear_hora_sorteo(nombre)
    if hora_sorteo:
        hoy_sorteo = ahora_cuba.replace(hour=hora_sorteo[0], minute=hora_sorteo[1], second=0, microsecond=0)
        return ahora_cuba.strftime("%Y-%m-%d") if ahora_cuba >= hoy_sorteo else (ahora_cuba - timedelta(days=1)).strftime("%Y-%m-%d")
    return (ahora_cuba - timedelta(days=1)).strftime("%Y-%m-%d") if ahora_cuba.hour < 6 else ahora_cuba.strftime("%Y-%m-%d")

def calcular_fecha_esperada_usa(nombre_db):
    hora_sorteo = parsear_hora_sorteo(nombre_db)
    if not hora_sorteo: return datetime.now(TZ_CUBA).strftime("%Y-%m-%d")
    ahora_este = datetime.now(TZ_ESTE)
    hoy_sorteo = ahora_este.replace(hour=hora_sorteo[0], minute=hora_sorteo[1], second=0, microsecond=0)
    dt_sorteo = hoy_sorteo if ahora_este >= hoy_sorteo else hoy_sorteo - timedelta(days=1)
    return dt_sorteo.astimezone(TZ_CUBA).strftime("%Y-%m-%d")

def fetch_url(url, timeout=20):
    """Descarga usando curl_cffi simulando ser Chrome para evadir bloqueos"""
    for intento in range(4):
        try:
            # EL TRUCO MAGICO: impersonate="chrome"
            resp = requests.get(url, impersonate="chrome", timeout=timeout)
            if resp.status_code == 200:
                return resp.text
            print(f"  ⚠️ {url} -> HTTP {resp.status_code} (intento {intento+1})")
        except Exception as e:
            print(f"  ❌ {url} -> {e} (intento {intento+1})")
        time.sleep(2) # Pausa para no saturar
    return None

def extraer_numeros_validos(soup):
    for clase in ["result-number", "result-number__ball", "draw-result-number", "result__number", "numero-resultado", "c-ball", "ball"]:
        bolas = soup.find_all(class_=clase)
        if bolas:
            return [b.get_text(strip=True) for b in bolas if b.get_text(strip=True).isdigit() and len(b.get_text(strip=True)) >= 1][:4]
    return []

def scrape_principal():
    print("📡 Extrayendo enloteria (principal)...")
    html = fetch_url(URL_MAIN)
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    resultados = []
    
    # Búsqueda más flexible por si cambiaron el HTML
    tarjetas = soup.find_all("div", attrs={"data-lottery-name": True})
    if not tarjetas:
        # Fallback: buscar divs que parezcan tarjetas de lotería
        tarjetas = soup.find_all("div", class_=re.compile(r'card|lottery|result', re.I))
        
    print(f"  → Tarjetas encontradas: {len(tarjetas)}")
    
    for tarjeta in tarjetas:
        try:
            nombre = tarjeta.get("data-lottery-name", "")
            if not nombre:
                # Intentar sacar el nombre de un título dentro de la tarjeta
                titulo = tarjeta.find(['h2', 'h3', 'h4', 'span', 'p'], class_=re.compile(r'title|name', re.I))
                if titulo: nombre = titulo.get_text(strip=True)
                
            nombre = " ".join(nombre.strip().split())
            if not nombre or nombre in NOMBRES_IGNORADOS: continue
            
            numeros = extraer_numeros_validos(tarjeta)
            if len(numeros) >= 2:
                resultados.append({
                    "sorteo_nombre": nombre,
                    "numeros": numeros,
                    "fecha": calcular_fecha_sorteo_enloteria(nombre),
                    "fuente": "enloteria",
                })
        except Exception as e:
            pass
    return resultados

def scrape_especifica(url, nombre_forzado):
    html = fetch_url(url)
    if not html:
        return []
    numeros = extraer_numeros_validos(BeautifulSoup(html, "html.parser"))[:3]
    if len(numeros) >= 2:
        return [{"sorteo_nombre": nombre_forzado, "numeros": numeros, "fecha": calcular_fecha_sorteo_enloteria(nombre_forzado), "fuente": "enloteria"}]
    return []

def _extraer_tarjeta_lotteryusa(soup):
    return soup.find('tr', class_=re.compile(r'c-draw-card|draw-card')) or soup.find('div', class_=re.compile(r'c-draw-card|draw-card'))

def _extraer_fecha_lotteryusa(tarjeta):
    fecha_nodo = tarjeta.find('time') or next((tag for tag in tarjeta.find_all(['span', 'div', 'p']) if re.search(r'[A-Z][a-z]{2}\s+\d{1,2},\s+\d{4}', tag.get_text(strip=True))), None)
    if not fecha_nodo: return None
    fecha_texto = re.sub(r'(Sunday|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday),', '', fecha_nodo.get_text(strip=True)).strip()
    try:
        return datetime.strptime(fecha_texto, '%b %d, %Y').strftime('%Y-%m-%d')
    except ValueError:
        return None

def scrape_lotteryusa():
    print("📡 Extrayendo USA (lotteryusa.com)...")
    resultados = []
    for nombre_db, juegos in URLS_MULTI.items():
        fecha_esperada = calcular_fecha_esperada_usa(nombre_db)
        resultado_sorteo = {"sorteo_nombre": nombre_db, "fecha": fecha_esperada, "fuente": "lotteryusa", "pick2": "", "pick3": "", "pick4": "", "pick5": "", "fijo": "", "corrido_1": "", "corrido_2": ""}
        exito_alguna = False
        
        for juego, urls in juegos.items():
            for url in urls:
                html = fetch_url(url)
                if not html: continue
                soup = BeautifulSoup(html, 'html.parser')
                tarjeta = _extraer_tarjeta_lotteryusa(soup)
                if not tarjeta: continue
                
                fecha_tarjeta = _extraer_fecha_lotteryusa(tarjeta)
                if fecha_tarjeta and fecha_tarjeta != fecha_esperada:
                    break
                    
                nodos = tarjeta.select('li.c-ball, li.c-result__ball, .c-ball, .ball')
                numeros = [n.get_text(strip=True) for n in nodos]
                if not numeros: continue
                
                if juego == "pick2": resultado_sorteo["pick2"] = "".join(numeros[:2])
                elif juego == "pick3":
                    resultado_sorteo["pick3"] = "".join(numeros[:3])
                    if len(numeros) >= 3: resultado_sorteo["fijo"] = str(numeros[1]) + str(numeros[2])
                elif juego == "pick4":
                    resultado_sorteo["pick4"] = "".join(numeros[:4])
                    if len(numeros) >= 4:
                        resultado_sorteo["corrido_1"] = str(numeros[0]) + str(numeros[1])
                        resultado_sorteo["corrido_2"] = str(numeros[2]) + str(numeros[3])
                elif juego == "pick5": resultado_sorteo["pick5"] = "".join(numeros[:5])
                
                exito_alguna = True
                break # Pasa al siguiente juego (ej. de pick3 a pick4)
                
        if exito_alguna:
            resultados.append(resultado_sorteo)
            print(f"  ✅ {nombre_db}")
        else:
            print(f"  ⚠️ {nombre_db} (sin datos)")
    return resultados

def main():
    print("=== 🚀 INICIO SCRAPER LIGERO (curl_cffi) ===")
    hoy_cuba = datetime.now(TZ_CUBA).strftime("%Y-%m-%d")
    hoy_et = datetime.now(TZ_ESTE).strftime("%Y-%m-%d")
    todos_nuevos = []

    res = scrape_principal()
    print(f"  → {len(res)} sorteos de enloteria")
    todos_nuevos.extend(res)

    for url, nombre in [(URL_QUEMAITO, "El Quemaito Mayor"), (URL_QUINIELON, "El Quinielon Dia")]:
        res = scrape_especifica(url, nombre)
        if res:
            print(f"  → {nombre} OK")
            todos_nuevos.extend(res)

    res = scrape_lotteryusa()
    print(f"  → {len(res)} sorteos de lotteryusa")
    todos_nuevos.extend(res)

    dic = {}
    if os.path.exists(ARCHIVO_JSON):
        try:
            with open(ARCHIVO_JSON, "r", encoding="utf-8") as f:
                for r in json.load(f):
                    if r.get("fecha") in (hoy_cuba, hoy_et):
                        dic[f"{r['sorteo_nombre']}|{r['fecha']}"] = r
        except Exception:
            pass

    for n in todos_nuevos:
        dic[f"{n['sorteo_nombre']}|{n['fecha']}"] = n

    finales = [r for r in dic.values() if r.get('fecha') == (hoy_cuba if r.get('fuente') == 'enloteria' else hoy_et)]

    with open(ARCHIVO_JSON, "w", encoding="utf-8") as f:
        json.dump(finales, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Guardados {len(finales)} resultados vigentes en {ARCHIVO_JSON}")

if __name__ == "__main__":
    main()
