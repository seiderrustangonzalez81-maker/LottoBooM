#!/usr/bin/env python3
"""Scrape Enloteria and LotteryUSA results into resultados.json.

This is intentionally the lightweight curl_cffi version used by the existing
GitHub Actions workflow. Dates written to JSON are Cuba dates, matching the
Django loader's date filter. No missing result is fabricated.
"""

import json
import os
import re
import tempfile
import time
from datetime import date, datetime, time as datetime_time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
from curl_cffi import requests

TZ_CUBA = ZoneInfo("America/Havana")
TZ_ESTE = ZoneInfo("America/New_York")

URL_MAIN = "https://enloteria.com/resultados-loterias-hoy"
URL_QUEMAITO = "https://enloteria.com/resultados-el-quemaito-mayor-hoy"
URL_QUINIELON = "https://enloteria.com/resultados-el-quinielon-dia-hoy"
ARCHIVO_JSON = Path(__file__).with_name("resultados.json")

# Keep only source URLs already present in the working lightweight scraper.
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
    "New York 2:30 PM": {
        "pick3": ["https://www.lotteryusa.com/new-york/midday-numbers/"],
        "pick4": ["https://www.lotteryusa.com/new-york/midday-win-4/"],
    },
    "New York 10:30 PM": {
        "pick3": ["https://www.lotteryusa.com/new-york/numbers/"],
        "pick4": ["https://www.lotteryusa.com/new-york/win-4/"],
    },
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
    "Tennessee 1:20 PM": {
        "pick3": ["https://www.lotteryusa.com/tennessee/midday-cash-3/"],
        "pick4": ["https://www.lotteryusa.com/tennessee/midday-cash-4/"],
    },
    "Tennessee 6:30 PM": {
        "pick3": ["https://www.lotteryusa.com/tennessee/cash-3/"],
        "pick4": ["https://www.lotteryusa.com/tennessee/cash-4/"],
    },
}

HORAS_POR_PALABRA = {
    "MADRUGADA": (3, 0), "DIA": (12, 0), "DÍA": (12, 0),
    "MEDIODIA": (12, 0), "MEDIODÍA": (12, 0), "TARDE": (15, 0),
    "NOCHE": (21, 0), "MAYOR": (21, 0),
}
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9,es;q=0.8",
}
DATE_RE = re.compile(r"\b[A-Z][a-z]{2}\s+\d{1,2},\s+\d{4}\b")


def parsear_hora_sorteo(nombre):
    match = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(AM|PM)", nombre, re.I)
    if match:
        hour, minute = int(match.group(1)), int(match.group(2) or 0)
        ampm = match.group(3).upper()
        if not 1 <= hour <= 12 or minute > 59:
            return None
        if ampm == "PM" and hour != 12:
            hour += 12
        elif ampm == "AM" and hour == 12:
            hour = 0
        return hour, minute
    upper = nombre.upper()
    return next((value for word, value in HORAS_POR_PALABRA.items() if word in upper), None)


def fecha_enloteria(nombre, ahora=None):
    ahora = ahora or datetime.now(TZ_CUBA)
    hora = parsear_hora_sorteo(nombre)
    if hora:
        sorteo_hoy = ahora.replace(hour=hora[0], minute=hora[1], second=0, microsecond=0)
        fecha = ahora.date() if ahora >= sorteo_hoy else ahora.date() - timedelta(days=1)
    else:
        fecha = ahora.date() - timedelta(days=1) if ahora.hour < 6 else ahora.date()
    return fecha.isoformat()


def fechas_usa(nombre, ahora=None):
    hora = parsear_hora_sorteo(nombre)
    if hora is None:
        raise ValueError(f"Falta hora de sorteo configurada: {nombre}")
    ahora = ahora or datetime.now(TZ_ESTE)
    sorteo_hoy = datetime.combine(ahora.date(), datetime_time(*hora), tzinfo=TZ_ESTE)
    sorteo = sorteo_hoy if ahora >= sorteo_hoy else sorteo_hoy - timedelta(days=1)
    return sorteo.date(), sorteo.astimezone(TZ_CUBA).date()


def fetch_url(url, timeout=20):
    for intento in range(3):
        try:
            response = requests.get(url, headers=HEADERS, impersonate="chrome", timeout=timeout)
            if response.status_code == 200:
                return response.text
            print(f"  ⚠️ HTTP {response.status_code}: {url} (intento {intento + 1})")
        except Exception as exc:
            print(f"  ⚠️ Error {url} (intento {intento + 1}): {exc}")
        if intento < 2:
            time.sleep(1)
    return None


def extraer_numeros(soup, min_digitos=1, limite=5):
    for clase in ("result-number", "result-number__ball", "draw-result-number",
                  "result__number", "numero-resultado", "c-ball", "ball"):
        nodes = soup.find_all(class_=clase)
        values = [node.get_text(strip=True) for node in nodes]
        values = [value for value in values if value.isdigit() and len(value) >= min_digitos]
        if values:
            return values[:limite]
    return []


def scrape_principal():
    print("📡 Enloteria: principal")
    html = fetch_url(URL_MAIN)
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.find_all("div", attrs={"data-lottery-name": True})
    print(f"  → Tarjetas: {len(cards)}")
    results = []
    for card in cards:
        name = " ".join(card.get("data-lottery-name", "").split())
        numbers = extraer_numeros(card, min_digitos=2, limite=4)
        if name and len(numbers) >= 2:
            results.append({"sorteo_nombre": name, "numeros": numbers,
                            "fecha": fecha_enloteria(name), "fuente": "enloteria"})
    return results


def scrape_especifica(url, name):
    html = fetch_url(url)
    if not html:
        return []
    numbers = extraer_numeros(BeautifulSoup(html, "html.parser"), min_digitos=2, limite=3)
    if len(numbers) < 2:
        print(f"  ⚠️ {name}: sin números")
        return []
    print(f"  ✅ {name}")
    return [{"sorteo_nombre": name, "numeros": numbers,
             "fecha": fecha_enloteria(name), "fuente": "enloteria"}]


def extraer_tarjeta_usa(soup):
    return soup.find("tr", class_=re.compile(r"(?:c-)?draw-card")) or soup.find(
        "div", class_=re.compile(r"(?:c-)?draw-card")
    )


def extraer_fecha_usa(card):
    node = card.find("time")
    if node:
        iso = node.get("datetime", "").strip()
        if iso:
            try:
                return date.fromisoformat(iso[:10])
            except ValueError:
                pass
        text = node.get_text(" ", strip=True)
    else:
        text = card.get_text(" ", strip=True)
    match = DATE_RE.search(text)
    if not match:
        return None
    try:
        return datetime.strptime(match.group(0), "%b %d, %Y").date()
    except ValueError:
        return None


def extraer_bolas_usa(card):
    for selector in ("li.c-ball", "li.c-result__ball", ".c-ball", ".ball"):
        nodes = card.select(selector)
        if nodes:
            values = [node.get_text(strip=True) for node in nodes]
            return [value for value in values if value.isdigit()]
    return []


def scrape_lotteryusa():
    print("📡 LotteryUSA")
    results = []
    for name, games in URLS_MULTI.items():
        expected_et, expected_cuba = fechas_usa(name)
        record = {
            "sorteo_nombre": name, "fecha": expected_cuba.isoformat(),
            "fuente": "lotteryusa", "pick2": "", "pick3": "", "pick4": "",
            "pick5": "", "fijo": "", "corrido_1": "", "corrido_2": "",
        }
        for game, urls in games.items():
            for url in urls:
                html = fetch_url(url)
                if not html:
                    continue
                card = extraer_tarjeta_usa(BeautifulSoup(html, "html.parser"))
                if not card:
                    continue
                draw_date = extraer_fecha_usa(card)
                # No use a result if its date cannot be verified or is stale.
                if draw_date is None or draw_date != expected_et:
                    print(f"  ⏭️ {name}/{game}: fecha fuente={draw_date}; esperada={expected_et}")
                    break
                numbers = extraer_bolas_usa(card)
                if not numbers:
                    continue
                if game == "pick2":
                    record["pick2"] = "".join(numbers[:2])
                elif game == "pick3":
                    record["pick3"] = "".join(numbers[:3])
                    if len(numbers) >= 3:
                        record["fijo"] = numbers[1] + numbers[2]
                elif game == "pick4":
                    record["pick4"] = "".join(numbers[:4])
                    if len(numbers) >= 4:
                        record["corrido_1"] = numbers[0] + numbers[1]
                        record["corrido_2"] = numbers[2] + numbers[3]
                elif game == "pick5":
                    record["pick5"] = "".join(numbers[:5])
                print(f"  ✅ {name} {game}")
                break
        if any(record[key] for key in ("pick2", "pick3", "pick4", "pick5")):
            results.append(record)
        else:
            print(f"  ⚠️ {name}: sin resultado confirmado para {expected_et}")
    return results


def leer_previos():
    if not ARCHIVO_JSON.exists():
        return []
    try:
        with ARCHIVO_JSON.open("r", encoding="utf-8") as source:
            data = json.load(source)
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"No se puede leer resultados.json; no se reemplaza: {exc}") from exc
    if not isinstance(data, list):
        raise RuntimeError("resultados.json no contiene una lista; no se reemplaza")
    return [item for item in data if isinstance(item, dict)]


def fusionar(previos, nuevos, hoy_cuba, hoy_et):
    merged = {}
    for item in previos:
        name, source = item.get("sorteo_nombre"), item.get("fuente")
        try:
            item_date = date.fromisoformat(item.get("fecha", ""))
        except (TypeError, ValueError):
            continue
        if not name or source not in {"enloteria", "lotteryusa"}:
            continue
        if source == "lotteryusa" and item_date == hoy_et:
            # Migrate today's legacy ET-date records to the Cuba date expected
            # by load_results. Existing new-format records are already Cuba dates.
            draw_time = parsear_hora_sorteo(name)
            if draw_time:
                item_date = datetime.combine(item_date, datetime_time(*draw_time), tzinfo=TZ_ESTE).astimezone(TZ_CUBA).date()
        if item_date != hoy_cuba:
            continue
        normalized = {**item, "fecha": hoy_cuba.isoformat()}
        merged[(name, source)] = normalized
    for item in nuevos:
        name, source = item.get("sorteo_nombre"), item.get("fuente")
        if name and source in {"enloteria", "lotteryusa"} and item.get("fecha") == hoy_cuba.isoformat():
            # Fresh data replaces stale values for the same draw/source.
            merged[(name, source)] = item
    return list(merged.values())


def guardar_atomico(data):
    fd, temp_path = tempfile.mkstemp(prefix="resultados-", suffix=".json", dir=ARCHIVO_JSON.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            json.dump(data, output, ensure_ascii=False, indent=2)
            output.write("\n")
        os.replace(temp_path, ARCHIVO_JSON)
    except Exception:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise


def main():
    hoy_cuba = datetime.now(TZ_CUBA).date()
    hoy_et = datetime.now(TZ_ESTE).date()
    print(f"=== SCRAPER LIGERO === Cuba={hoy_cuba} | Este={hoy_et}")
    nuevos = scrape_principal()
    nuevos.extend(scrape_especifica(URL_QUEMAITO, "El Quemaito Mayor"))
    nuevos.extend(scrape_especifica(URL_QUINIELON, "El Quinielon Dia"))
    nuevos.extend(scrape_lotteryusa())

    finales = fusionar(leer_previos(), nuevos, hoy_cuba, hoy_et)
    if not finales:
        raise RuntimeError("No hay resultados válidos nuevos ni previos; JSON no reemplazado")
    guardar_atomico(finales)
    print(f"✅ Guardados {len(finales)} resultados de la fecha Cuba {hoy_cuba}; extraídos ahora: {len(nuevos)}")


if __name__ == "__main__":
    main()
