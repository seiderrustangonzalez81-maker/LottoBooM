import json
import os
import time
import re
import requests
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

TZ_CUBA = ZoneInfo("America/Havana")
TZ_ESTE = ZoneInfo("America/New_York")
TZ_RD = ZoneInfo("America/Santo_Domingo")

# Cuba decidió mantener UTC-4 durante el período indicado.
# El override evita depender de que la imagen de Ubuntu/GitHub tenga
# actualizada la base IANA para esta decisión temporal.
CUBA_UTC4_DESDE_UTC = datetime(2026, 11, 1, 5, 0, tzinfo=timezone.utc)
CUBA_UTC4_HASTA_UTC = datetime(2027, 11, 7, 5, 0, tzinfo=timezone.utc)  # límite exclusivo
CUBA_UTC4 = timezone(timedelta(hours=-4), name="Cuba-UTC-4")

# Hora local oficial usada para calcular la fecha de cada sorteo estadounidense.
# Tennessee se usa Central (zona de Nashville); Florida se usa Eastern,
# que es la zona con la que se publican los horarios de los sorteos.
ZONAS_ESTADOS = {
    "Florida": ZoneInfo("America/New_York"),
    "Texas": ZoneInfo("America/Chicago"),
    "New York": ZoneInfo("America/New_York"),
    "New Jersey": ZoneInfo("America/New_York"),
    "Georgia": ZoneInfo("America/New_York"),
    "Tennessee": ZoneInfo("America/Chicago"),
}

URL_MAIN = "https://enloteria.com/resultados-loterias-hoy"
URL_QUEMAITO = "https://enloteria.com/resultados-el-quemaito-mayor-hoy"
URL_QUINIELON = "https://enloteria.com/resultados-el-quinielon-dia-hoy"
ARCHIVO_JSON = "resultados.json"


# Matriz maestra de los sorteos que la aplicación espera (51 nombres).
# Se usa para auditar cobertura: no bloquea la publicación de resultados parciales.
SORTEOS_ESPERADOS = [
    "Anguila 8 AM", "Anguila 9 AM", "Haití 1", "Anguila 10 AM",
    "Tennessee 10:20 AM", "Haití 2", "Anguila 11 AM", "Texas 11 AM",
    "Haití 3", "Lotedom", "Quemaito", "Anguila 12 PM", "Primera",
    "Quinielón", "Suerte 12:30 PM", "King Lottery 12:30 PM",
    "Georgia 12:30 PM", "Real 12:50 PM", "New Yol Real 12:50 PM",
    "New Jersey 12:50 PM", "Anguila 1 PM", "Tennessee 1:20 PM",
    "Texas 1:20 PM", "Florida 1:35 PM", "Anguila 2 PM",
    "Gana Más 2:30 PM", "New York 2:30 PM", "Anguila 3 PM",
    "Anguila 4 PM", "Anguila 5 PM", "Haití 4", "Suerte 6 PM",
    "Anguila 6 PM", "Haití 5", "Anguila 7 PM", "Primera 7 PM",
    "Georgia 7 PM", "Texas 7 PM", "Tennessee 7:20 PM",
    "King Lottery 7:30 PM", "Haití 6", "Loteka 7:50 PM", "Tok 3",
    "Anguila 8 PM", "Nacional", "Leidsa 8:55 PM", "Pega 3+",
    "Anguila 9 PM", "Florida 9:50 PM", "New York 10:30 PM",
    "New Jersey 10:50 PM", "Texas 11 PM", "Georgia 11:40 PM",
]
URL_CONECTATE = "https://www.conectate.com.do/loterias/"

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
    "Texas 1:20 PM": {"pick3": ["https://www.lotteryusa.com/texas/midday-pick-3/"]},
    "Texas 10:12 PM": {"pick3": ["https://www.lotteryusa.com/texas/pick-3/"]},
    "New York 2:30 PM": {"pick3": ["https://www.lotteryusa.com/new-york/midday-numbers/"],
        "pick4": ["https://www.lotteryusa.com/new-york/midday-win-4/"]},
    "New York 10:30 PM": {"pick3": ["https://www.lotteryusa.com/new-york/numbers/"],
        "pick4": ["https://www.lotteryusa.com/new-york/win-4/"]},
    "New Jersey 12:50 PM": {
        "pick3": ["https://www.lotteryusa.com/new-jersey/midday-pick-3/"],
        "pick4": ["https://www.lotteryusa.com/new-jersey/midday-pick-4/"],
    },
    "New Jersey 10:57 PM": {
        "pick3": ["https://www.lotteryusa.com/new-jersey/pick-3/"],
        "pick4": ["https://www.lotteryusa.com/new-jersey/pick-4/"],
    },
    "Georgia 12:30 PM": {
        "pick3": ["https://www.lotteryusa.com/georgia/midday-3/"],
        "pick4": ["https://www.lotteryusa.com/georgia/midday-4/"],
    },
    "Georgia 6:59 PM": {
        "pick3": ["https://www.lotteryusa.com/georgia/cash-3-evening/"],
        "pick4": ["https://www.lotteryusa.com/georgia/cash-4-evening/"],
    },
    "Georgia 11:34 PM": {
        "pick3": ["https://www.lotteryusa.com/georgia/cash-3/"],
        "pick4": ["https://www.lotteryusa.com/georgia/cash-4/"],
    },
    # Tennessee Morning (la matriz de la app lo etiqueta 10:20 AM).
    # LotteryUSA publica Cash 3 Morning y Cash 4 Morning.
    "Tennessee 10:20 AM": {
        "pick3": ["https://www.lotteryusa.com/tennessee/morning-cash-3/"],
        "pick4": ["https://www.lotteryusa.com/tennessee/morning-cash-4/"],
    },
    "Tennessee 1:20 PM": {
        "pick3": ["https://www.lotteryusa.com/tennessee/midday-cash-3/"],
        "pick4": ["https://www.lotteryusa.com/tennessee/midday-cash-4/"],
    },
    "Tennessee 6:30 PM": {
        "pick3": ["https://www.lotteryusa.com/tennessee/cash-3/"],
        "pick4": ["https://www.lotteryusa.com/tennessee/cash-4/"],
    },
}
NOMBRES_IGNORADOS = {
    "Georgia Día", "Georgia Tarde", "Florida Tarde", "Florida Noche",
    "New York Tarde", "New Jersey Tarde", "Texas Tarde", "Tennessee Día",
}

def obtener_hora_cuba(ahora_utc=None):
    """Hora cubana correcta, usando UTC-4 durante la decisión temporal vigente."""
    ahora_utc = ahora_utc or datetime.now(timezone.utc)
    if ahora_utc.tzinfo is None:
        ahora_utc = ahora_utc.replace(tzinfo=timezone.utc)
    instante_utc = ahora_utc.astimezone(timezone.utc)
    if CUBA_UTC4_DESDE_UTC <= instante_utc < CUBA_UTC4_HASTA_UTC:
        return ahora_utc.astimezone(CUBA_UTC4)
    return ahora_utc.astimezone(TZ_CUBA)

def convertir_a_cuba(fecha_hora_aware):
    """Convierte un instante con zona horaria a la hora vigente de Cuba."""
    return obtener_hora_cuba(fecha_hora_aware.astimezone(timezone.utc))

def fecha_cuba():
    return obtener_hora_cuba().strftime("%Y-%m-%d")

def fecha_este():
    return datetime.now(TZ_ESTE).strftime("%Y-%m-%d")

HORAS_POR_PALABRA = {
    'MADRUGADA': 3, 'DIA': 12, 'DÍA': 12, 'MEDIODIA': 12, 'MEDIODÍA': 12,
    'TARDE': 15, 'NOCHE': 21,
}

def parsear_hora_sorteo(nombre):
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

def fecha_operativa_cuba(instante):
    """Día operativo: 01:00 a 00:59 del día calendario siguiente, hora Cuba."""
    hora_cuba = convertir_a_cuba(instante) if instante.tzinfo else instante.replace(tzinfo=TZ_CUBA)
    return (hora_cuba - timedelta(hours=1)).date().isoformat()


def fecha_operativa_actual(ahora=None):
    ahora = ahora or obtener_hora_cuba()
    return fecha_operativa_cuba(ahora)


def calcular_fecha_sorteo_enloteria(nombre):
    ahora_cuba = obtener_hora_cuba()
    hora_sorteo = parsear_hora_sorteo(nombre)
    if hora_sorteo:
        hora, minuto = hora_sorteo
        candidato = ahora_cuba.replace(hour=hora, minute=minuto, second=0, microsecond=0)
        if candidato > ahora_cuba:
            candidato -= timedelta(days=1)
        return fecha_operativa_cuba(candidato)
    return fecha_operativa_cuba(ahora_cuba)


def zona_horaria_sorteo_usa(nombre_db):
    for estado, zona in ZONAS_ESTADOS.items():
        if nombre_db.startswith(estado):
            return zona
    return TZ_ESTE


def calcular_fechas_esperadas_usa(nombre_db):
    """Retorna fecha local de la tarjeta y día operativo Cuba del sorteo."""
    hora_sorteo = parsear_hora_sorteo(nombre_db)
    zona = zona_horaria_sorteo_usa(nombre_db)
    ahora_local = datetime.now(zona)
    if not hora_sorteo:
        instante_sorteo = datetime.combine(ahora_local.date(), datetime.min.time(), tzinfo=zona)
    else:
        hora, minuto = hora_sorteo
        hoy_sorteo = ahora_local.replace(hour=hora, minute=minuto, second=0, microsecond=0)
        ayer_sorteo = hoy_sorteo - timedelta(days=1)
        # Elegir la ocurrencia que pertenece al día operativo vigente en Cuba.
        dia_operativo = fecha_operativa_actual()
        candidatos = (hoy_sorteo, ayer_sorteo)
        validos = [x for x in candidatos if fecha_operativa_cuba(x) == dia_operativo]
        instante_sorteo = validos[0] if validos else (hoy_sorteo if ahora_local >= hoy_sorteo else ayer_sorteo)
    fecha_local = instante_sorteo.date()
    fecha_cuba_sorteo = fecha_operativa_cuba(instante_sorteo)
    return fecha_local.strftime("%Y-%m-%d"), fecha_cuba_sorteo


def calcular_fecha_esperada_usa(nombre_db):
    # Mantiene la fecha almacenada alineada con la fecha cubana del instante del sorteo.
    return calcular_fechas_esperadas_usa(nombre_db)[1]

def normalizar_nombre(nombre):
    return " ".join(nombre.split())


# Alias confirmados contra sorteos/fixtures/sorteos.json.
# Se conserva nombre_fuente para poder auditar cada coincidencia.
ALIASES_NOMBRES_SORTEOS = {
    **{f"anguilla {h}{ampm.lower()}": f"Anguila {h} {ampm}" for h, ampm in [
        ("8", "AM"), ("9", "AM"), ("10", "AM"), ("11", "AM"),
        ("12", "PM"), ("1", "PM"), ("2", "PM"), ("3", "PM"),
        ("4", "PM"), ("5", "PM"), ("6", "PM"), ("7", "PM"),
        ("8", "PM"), ("9", "PM"), ("10", "PM"),
    ]},
    "haiti bolet 9:30 am": "Haití 1",
    "haiti bolet 10:30 am": "Haití 2",
    "haiti bolet 11:30 am": "Haití 3",
    "haiti bolet 5:30 pm": "Haití 4",
    "haiti bolet 6:30 pm": "Haití 5",
    "haiti bolet 7:30 pm": "Haití 6",
    "el quemaito mayor": "Quemaito",
    "el quinielon dia": "Quinielón",
    "la primera": "Primera",
    "la primera noche": "Primera 7 PM",
    "lotedom": "Lotedom",
    "la suerte": "Suerte 12:30 PM",
    "la suerte 6pm": "Suerte 6 PM",
    "king lottery dia": "King Lottery 12:30 PM",
    "king lottery noche": "King Lottery 7:30 PM",
    "real": "Real 12:50 PM",
    "nacional noche": "Nacional",
    "nacional gana mas": "Gana Más 2:30 PM",
    "leidsa": "Leidsa 8:55 PM",
    "florida 9:45 pm": "Florida 9:50 PM",
    "new jersey 10:57 pm": "New Jersey 10:50 PM",
    "georgia 6:59 pm": "Georgia 7 PM",
    "georgia 11:34 pm": "Georgia 11:40 PM",
    "texas 10:12 pm": "Texas 11 PM",
    "tennessee 6:30 pm": "Tennessee 7:20 PM",
}


def canonizar_nombre_sorteo(nombre):
    import unicodedata
    clave = unicodedata.normalize("NFKD", str(nombre or "").casefold())
    clave = "".join(c for c in clave if not unicodedata.combining(c))
    clave = re.sub(r"[^a-z0-9]+", " ", clave).strip()
    return ALIASES_NOMBRES_SORTEOS.get(clave, normalizar_nombre(str(nombre or "")))

def extraer_numeros_validos(tarjeta_o_soup):
    bolas = tarjeta_o_soup.find_all(class_="result-number")
    if not bolas:
        for clase in ("result-number__ball", "draw-result-number", "result__number", "numero-resultado"):
            bolas = tarjeta_o_soup.find_all(class_=clase)
            if bolas:
                break
    numeros = []
    for b in bolas:
        texto = b.get_text(strip=True)
        if texto.isdigit() and len(texto) >= 2:
            numeros.append(texto)
    return numeros[:4]

def scroll_hasta_estabilizar(page, max_intentos=20, pausa_ms=3000):
    previas = -1
    comprobaciones_estables = 0
    actuales = 0
    for _ in range(max_intentos):
        actuales = page.locator('div[data-lottery-name]').count()
        if actuales == previas:
            comprobaciones_estables += 1
        else:
            comprobaciones_estables = 0
        if comprobaciones_estables >= 3:
            print(f"  ✅ Scroll completado. Tarjetas: {actuales}")
            return
        previas = actuales
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(pausa_ms)
    print(f"  ⚠️ Máximo de scrolls alcanzado. Tarjetas: {actuales}")

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

    for tarjeta in tarjetas:
        try:
            nombre = normalizar_nombre(tarjeta.get("data-lottery-name", "").strip())
            if not nombre or nombre in NOMBRES_IGNORADOS:
                continue
            numeros = extraer_numeros_validos(tarjeta)
            if numeros and len(numeros) >= 2:
                resultados.append({
                    "sorteo_nombre": canonizar_nombre_sorteo(nombre),
                    "nombre_fuente": nombre,
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
                "sorteo_nombre": canonizar_nombre_sorteo(nombre_forzado),
                "nombre_fuente": nombre_forzado,
                "numeros": numeros,
                "fecha": calcular_fecha_sorteo_enloteria(canonizar_nombre_sorteo(nombre_forzado)),
                "fuente": "enloteria",
            }]
    except Exception as e:
        print(f"  Error en scrape_especifica {nombre_forzado}: {e}")
    return []

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
    for dia in ['Sunday,', 'Monday,', 'Tuesday,', 'Wednesday,', 'Thursday,', 'Friday,', 'Saturday,']:
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

# ⬅️ CORREGIDO: ahora recibe `page` de Playwright y navega con él (evita los 403)
def scrape_lotteryusa(page):
    print("Extrayendo USA (lotteryusa.com) con Playwright...")
    resultados = []
    print(f"  Fecha actual Este (EE.UU.): {fecha_este()}")
    print(f"  Fecha actual Cuba: {fecha_cuba()}")

    for nombre_db, juegos in URLS_MULTI.items():
        fecha_esperada_local, fecha_esperada_cuba = calcular_fechas_esperadas_usa(nombre_db)
        resultado_sorteo = {
            "sorteo_nombre": canonizar_nombre_sorteo(nombre_db), "nombre_fuente": nombre_db, "fecha": fecha_esperada_cuba, "fuente": "lotteryusa",
            "pick2": "", "pick3": "", "pick4": "", "pick5": "",
            "fijo": "", "corrido_1": "", "corrido_2": "",
        }

        exito_total = False
        for juego, urls in juegos.items():
            exito_juego = False
            for url in urls:
                if exito_juego:
                    break
                for intento in range(3):
                    try:
                        # ⬅️ CORREGIDO: Playwright en vez de requests
                        page.goto(url, wait_until="domcontentloaded", timeout=30000)
                        page.wait_for_timeout(3000)  # pausa para JS
                        soup = BeautifulSoup(page.content(), 'html.parser')
                        tarjeta = _extraer_tarjeta_lotteryusa(soup)
                        if not tarjeta:
                            continue

                        fecha_tarjeta = _extraer_fecha_lotteryusa(tarjeta, nombre_db)

                        # ⬅️ CORREGIDO: comparar contra `fecha_esperada` (hora del sorteo),
                        # NO contra "hoy en ET". Permite capturar el sorteo nocturno
                        # de Georgia (11:34 PM) aunque el run caiga después de medianoche.
                        if fecha_tarjeta != fecha_esperada_local:
                            print(f"  ⏳ [{nombre_db} - {juego}] Tarjeta muestra {fecha_tarjeta}; se esperaba {fecha_esperada_local}. Reintento {intento + 1}/3.")
                            time.sleep(2)
                            continue

                        numeros = _extraer_numeros_lotteryusa(tarjeta)
                        cantidad_requerida = {"pick2": 2, "pick3": 3, "pick4": 4, "pick5": 5}[juego]
                        if len(numeros) < cantidad_requerida:
                            print(f"  ⚠️ [{nombre_db} - {juego}] Resultado incompleto ({len(numeros)}/{cantidad_requerida}); no se guarda este campo.")
                            continue

                        if juego == "pick2":
                            resultado_sorteo["pick2"] = "".join(numeros[:2])
                        elif juego == "pick3":
                            resultado_sorteo["pick3"] = "".join(numeros[:3])
                            if len(numeros) >= 3:
                                # FIX: Fijo = últimos 2 dígitos del pick3
                                resultado_sorteo["fijo"] = str(numeros[1]) + str(numeros[2])
                        elif juego == "pick4":
                            resultado_sorteo["pick4"] = "".join(numeros[:4])
                            if len(numeros) >= 4:
                                # FIX: Corridos = primeros 2 y últimos 2 del pick4
                                resultado_sorteo["corrido_1"] = str(numeros[0]) + str(numeros[1])
                                resultado_sorteo["corrido_2"] = str(numeros[2]) + str(numeros[3])
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
            juegos_faltantes = [j for j in juegos if not resultado_sorteo.get(j)]
            if juegos_faltantes:
                print(f"  ⚠️ {nombre_db}: resultados parciales; faltan {', '.join(juegos_faltantes)}. Se preservarán los valores anteriores si existen.")
            else:
                print(f"  ✅ {nombre_db}: todos los juegos extraídos.")
            resultados.append(resultado_sorteo)
        else:
            print(f"  ⚠️ No se pudo extraer ningún dato nuevo para {nombre_db}.")

    return resultados

def combinar_resultados(anterior, nuevo):
    """Combina resultados parciales sin borrar campos que ya estaban válidos."""
    combinado = dict(anterior)
    for clave, valor in nuevo.items():
        if valor not in (None, "", [], {}):
            combinado[clave] = valor
    return combinado


def informar_cobertura(resultados):
    """Resumen de cobertura contra la matriz de sorteos, normalizando nombres."""
    obtenidos = {normalizar_nombre(r.get("sorteo_nombre", "")).casefold() for r in resultados}
    esperados = {normalizar_nombre(n).casefold() for n in SORTEOS_ESPERADOS}
    faltan = [n for n in SORTEOS_ESPERADOS if normalizar_nombre(n).casefold() not in obtenidos]
    print(f"\n=== AUDITORÍA MATRIZ ({len(SORTEOS_ESPERADOS)} sorteos configurados) ===")
    print(f"Nombres distintos obtenidos: {len(obtenidos & esperados)}/{len(SORTEOS_ESPERADOS)}")
    if faltan:
        print("Pendientes/no detectados (no significa que no haya resultado; puede faltar fuente/configuración):")
        for nombre in faltan:
            print(f"  - {nombre}")
    else:
        print("✅ Se detectaron todos los nombres de la matriz.")

    # Auditoría separada: identifica los sorteos estadounidenses que sí están
    # configurados explícitamente en LotteryUSA. La lista de matriz no sustituye
    # esta configuración y así se evita asumir que un nombre ya se está scrapeando.
    configurados = {normalizar_nombre(n).casefold() for n in URLS_MULTI}
    usa_esperados = [n for n in SORTEOS_ESPERADOS if any(n.startswith(e) for e in ZONAS_ESTADOS)]
    sin_config = [n for n in usa_esperados if normalizar_nombre(n).casefold() not in configurados]
    print(f"Sorteos USA esperados con configuración directa: {len(usa_esperados)-len(sin_config)}/{len(usa_esperados)}")
    if sin_config:
        print("USA sin configuración directa:")
        for nombre in sin_config:
            print(f"  - {nombre}")


def main():
    todos_nuevos = []

    now_cuba = obtener_hora_cuba()
    dia_operativo = fecha_operativa_actual(now_cuba)
    hoy_cuba = now_cuba.strftime("%Y-%m-%d")
    ahora_utc = datetime.now(timezone.utc)
    now_et = ahora_utc.astimezone(TZ_ESTE)
    hoy_et = now_et.strftime("%Y-%m-%d")

    print("=== INICIO SCRAPER ===")
    print("===== DIAGNÓSTICO HORARIO =====")
    print(f"UTC: {ahora_utc.isoformat()}")
    print(f"Cuba: {now_cuba.isoformat()}")
    print(f"Nueva York: {now_et.isoformat()}")
    print(f"República Dominicana: {ahora_utc.astimezone(TZ_RD).isoformat()}")
    print(f"Fecha operativa Cuba: {dia_operativo} (01:00–00:59)")
    print(f"Fecha Este: {hoy_et}")
    print("===============================")

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

        try:
            res = scrape_lotteryusa(page)
            print(f"  → {len(res)} sorteos de lotteryusa")
            todos_nuevos.extend(res)
        except Exception as e:
            print(f"Error en lotteryusa: {e}")

        browser.close()

    informar_cobertura(todos_nuevos)

    guardados = []
    if os.path.exists(ARCHIVO_JSON):
        try:
            with open(ARCHIVO_JSON, "r", encoding="utf-8") as f:
                guardados = json.load(f)
            if not isinstance(guardados, list):
                guardados = []
        except Exception as e:
            print(f"⚠️ No se pudo leer JSON previo: {e}")
            guardados = []

    # Un único día operativo Cuba: desde 01:00 inclusive hasta 00:59
    # del día calendario siguiente. No mezclar registros de días operativos.
    dia_operativo = fecha_operativa_actual(now_cuba)
    fechas_validas = {dia_operativo}
    dic = {}
    for r in guardados:
        if r.get("fecha") in fechas_validas and r.get("sorteo_nombre"):
            clave = f"{r['sorteo_nombre']}|{r['fecha']}"
            dic[clave] = r

    for nuevo in todos_nuevos:
        fecha = nuevo.get("fecha")
        if fecha not in fechas_validas:
            print(f"⏭️ Fecha demasiado antigua/futura: {nuevo.get('sorteo_nombre')} | {fecha}")
            continue
        clave = f"{nuevo['sorteo_nombre']}|{fecha}"
        if clave in dic:
            dic[clave] = combinar_resultados(dic[clave], nuevo)
        else:
            dic[clave] = nuevo

    finales_filtrados = list(dic.values())
    if not finales_filtrados:
        print("⚠️ No hay resultados del día operativo. Se publicará [] para no conservar datos de una fecha anterior.")

    # Escritura atómica: evita dejar un JSON truncado si la ejecución falla.
    archivo_temporal = ARCHIVO_JSON + ".tmp"
    with open(archivo_temporal, "w", encoding="utf-8") as f:
        json.dump(finales_filtrados, f, ensure_ascii=False, indent=2)
    os.replace(archivo_temporal, ARCHIVO_JSON)

    print(f"✅ Guardados {len(finales_filtrados)} resultados del día operativo Cuba ({dia_operativo}; ventana 01:00–00:59).")
    print("\n=== RESUMEN ===")
    print(f"Total sorteos en JSON: {len(finales_filtrados)}")
    print(f"Fecha Cuba: {hoy_cuba}")
    print(f"Fecha ET: {hoy_et}")
    informar_cobertura(finales_filtrados)

if __name__ == "__main__":
    main()
