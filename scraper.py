#!/usr/bin/env python3
"""Scrape lottery results into resultados.json for the Django loader.

All output dates are normalized to America/Havana so load_results can apply
one consistent date rule. Missing draws are never fabricated; existing valid
results for the current Havana date are retained when a source is temporarily
unavailable.
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
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

TZ_CUBA = ZoneInfo("America/Havana")
TZ_ESTE = ZoneInfo("America/New_York")

URL_MAIN = "https://enloteria.com/resultados-loterias-hoy"
URL_QUEMAITO = "https://enloteria.com/resultados-el-quemaito-mayor-hoy"
URL_QUINIELON = "https://enloteria.com/resultados-el-quinielon-dia-hoy"
ARCHIVO_JSON = Path(__file__).with_name("resultados.json")

# Keep the verified LotteryUSA source URLs and the public names consumed by
# sorteos/management/commands/load_results.py. Do not invent source URLs.
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
    "MADRUGADA": (3, 0),
    "DIA": (12, 0),
    "DÍA": (12, 0),
    "MEDIODIA": (12, 0),
    "MEDIODÍA": (12, 0),
    "TARDE": (15, 0),
    "NOCHE": (21, 0),
    "MAYOR": (21, 0),
}
DATE_RE = re.compile(r"\b[A-Z][a-z]{2}\s+\d{1,2},\s+\d{4}\b")


def parsear_hora_sorteo(nombre):
    match = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(AM|PM)", nombre, re.IGNORECASE)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2) or 0)
        ampm = match.group(3).upper()
        if hour < 1 or hour > 12 or minute > 59:
            return None
        if ampm == "PM" and hour != 12:
            hour += 12
        elif ampm == "AM" and hour == 12:
            hour = 0
        return hour, minute
    upper_name = nombre.upper()
    for word, hour in HORAS_POR_PALABRA.items():
        if word in upper_name:
            return hour
    return None


def calcular_fecha_enloteria(nombre, ahora=None):
    ahora = ahora or datetime.now(TZ_CUBA)
    hora_sorteo = parsear_hora_sorteo(nombre)
    if hora_sorteo:
        hora, minuto = hora_sorteo
        fecha_sorteo = ahora.replace(hour=hora, minute=minuto, second=0, microsecond=0)
        return (ahora.date() if ahora >= fecha_sorteo else ahora.date() - timedelta(days=1)).isoformat()
    fecha = ahora.date() - timedelta(days=1) if ahora.hour < 6 else ahora.date()
    return fecha.isoformat()


def fecha_esperada_usa(nombre, ahora=None):
    hora = parsear_hora_sorteo(nombre)
    if hora is None:
        raise ValueError(f"No hay hora configurada para el sorteo LotteryUSA: {nombre}")
    ahora = ahora or datetime.now(TZ_ESTE)
    hora_sorteo = datetime.combine(ahora.date(), datetime_time(*hora), tzinfo=TZ_ESTE)
    sorteo_et = hora_sorteo if ahora >= hora_sorteo else hora_sorteo - timedelta(days=1)
    return sorteo_et.date(), sorteo_et.astimezone(TZ_CUBA).date()


def extraer_numeros(soup, min_digitos=1):
    for clase in (
        "result-number",
        "result-number__ball",
        "draw-result-number",
        "result__number",
        "numero-resultado",
        "c-ball",
        "ball",
    ):
        nodes = soup.find_all(class_=clase)
        numbers = []
        for node in nodes:
            value = node.get_text(strip=True)
            if value.isdigit() and len(value) >= min_digitos:
                numbers.append(value)
        if numbers:
            return numbers[:5]
    return []


def scrape_principal(page):
    print("📡 Enloteria: página principal")
    try:
        page.goto(URL_MAIN, wait_until="domcontentloaded", timeout=60_000)
        page.wait_for_timeout(4_000)
        stable_rounds = 0
        last_count = -1
        for _ in range(12):
            count = page.locator("div[data-lottery-name]").count()
            if count == last_count:
                stable_rounds += 1
                if stable_rounds >= 2:
                    break
            else:
                stable_rounds = 0
                last_count = count
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(1_500)
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(500)
    except (PlaywrightTimeoutError, Exception) as exc:
        print(f"  ⚠️ No se completó la carga/scroll de Enloteria: {exc}")

    soup = BeautifulSoup(page.content(), "html.parser")
    cards = soup.find_all("div", attrs={"data-lottery-name": True})
    print(f"  → Tarjetas: {len(cards)}")
    results = []
    for card in cards:
        try:
            name = " ".join(card.get("data-lottery-name", "").split())
            numbers = extraer_numeros(card, min_digitos=2)
            if name and len(numbers) >= 2:
                results.append({
                    "sorteo_nombre": name,
                    "numeros": numbers[:4],
                    "fecha": calcular_fecha_enloteria(name),
                    "fuente": "enloteria",
                })
        except Exception as exc:
            print(f"  ⚠️ Error leyendo tarjeta Enloteria: {exc}")
    return results


def scrape_especifica(page, url, nombre):
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=40_000)
        page.wait_for_timeout(2_000)
        soup = BeautifulSoup(page.content(), "html.parser")
        numbers = extraer_numeros(soup, min_digitos=2)[:3]
        if len(numbers) >= 2:
            print(f"  ✅ {nombre}")
            return [{
                "sorteo_nombre": nombre,
                "numeros": numbers,
                "fecha": calcular_fecha_enloteria(nombre),
                "fuente": "enloteria",
            }]
    except Exception as exc:
        print(f"  ⚠️ {nombre}: {exc}")
    return []


def extraer_tarjeta_lotteryusa(soup):
    for tag in ("tr", "div"):
        card = soup.find(tag, class_=re.compile(r"(?:c-)?draw-card"))
        if card:
            return card
    return None


def extraer_fecha_lotteryusa(card):
    time_node = card.find("time")
    if time_node:
        iso_value = time_node.get("datetime", "").strip()
        if iso_value:
            try:
                return date.fromisoformat(iso_value[:10])
            except ValueError:
                pass
        text = time_node.get_text(" ", strip=True)
    else:
        text = card.get_text(" ", strip=True)
    match = DATE_RE.search(text)
    if not match:
        return None
    try:
        return datetime.strptime(match.group(0), "%b %d, %Y").date()
    except ValueError:
        return None


def extraer_bolas_lotteryusa(card):
    for selector in (
        "ul.c-result.c-draw-card__ball-list > li.c-ball",
        "li.c-ball",
        "li.c-result__ball",
        ".c-ball",
        ".ball",
    ):
        nodes = card.select(selector)
        if nodes:
            values = [node.get_text(strip=True) for node in nodes]
            return [value for value in values if value.isdigit()]
    return []


def scrape_lotteryusa(page):
    print("📡 LotteryUSA")
    results = []
    for name, games in URLS_MULTI.items():
        expected_et, expected_cuba = fecha_esperada_usa(name)
        record = {
            "sorteo_nombre": name,
            "fecha": expected_cuba.isoformat(),
            "fuente": "lotteryusa",
            "pick2": "",
            "pick3": "",
            "pick4": "",
            "pick5": "",
            "fijo": "",
            "corrido_1": "",
            "corrido_2": "",
        }
        any_game = False
        for game, urls in games.items():
            game_done = False
            for url in urls:
                for attempt in range(2):
                    try:
                        page.goto(url, wait_until="domcontentloaded", timeout=35_000)
                        page.wait_for_timeout(1_500)
                        soup = BeautifulSoup(page.content(), "html.parser")
                        card = extraer_tarjeta_lotteryusa(soup)
                        if not card:
                            break
                        card_date = extraer_fecha_lotteryusa(card)
                        if card_date is None:
                            print(f"  ⚠️ {name}/{game}: no se pudo leer fecha de tarjeta; no se carga")
                            break
                        if card_date != expected_et:
                            print(f"  ⏭️ {name}/{game}: tarjeta {card_date}, se espera {expected_et}")
                            break
                        numbers = extraer_bolas_lotteryusa(card)
                        if not numbers:
                            if attempt == 0:
                                time.sleep(1)
                                continue
                            break
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
                        any_game = game_done = True
                        break
                    except Exception as exc:
                        print(f"  ⚠️ {name}/{game}, intento {attempt + 1}: {exc}")
                        if attempt == 0:
                            time.sleep(1)
                if game_done:
                    break
        if any_game:
            results.append(record)
        else:
            print(f"  ⚠️ {name}: sin resultado confirmado para {expected_et}")
    return results


def leer_resultados_previos():
    if not ARCHIVO_JSON.exists():
        return []
    try:
        with ARCHIVO_JSON.open("r", encoding="utf-8") as source:
            data = json.load(source)
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"No se puede leer {ARCHIVO_JSON}; se conserva sin cambios: {exc}") from exc
    if not isinstance(data, list):
        raise RuntimeError(f"{ARCHIVO_JSON} debe contener una lista; se conserva sin cambios")
    return [item for item in data if isinstance(item, dict)]


def fusionar_resultados(previous, fresh, today_cuba, today_et):
    merged = {}
    for item in previous:
        name, source = item.get("sorteo_nombre"), item.get("fuente")
        try:
            item_date = date.fromisoformat(item.get("fecha", ""))
        except (TypeError, ValueError):
            continue
        if not name or source not in {"enloteria", "lotteryusa"}:
            continue
        if source == "enloteria":
            if item_date != today_cuba:
                continue
        else:
            # Older scraper versions wrote the ET calendar date. Convert that
            # legacy value using the configured draw time before preserving it.
            if item_date == today_et:
                draw_hour = parsear_hora_sorteo(name)
                if draw_hour:
                    item_date = datetime.combine(item_date, datetime_time(*draw_hour), tzinfo=TZ_ESTE).astimezone(TZ_CUBA).date()
            if item_date != today_cuba:
                continue
            item = {**item, "fecha": today_cuba.isoformat()}
        key = (name, item_date.isoformat(), source)
        merged[key] = item

    for item in fresh:
        if not isinstance(item, dict):
            continue
        name, source = item.get("sorteo_nombre"), item.get("fuente")
        try:
            item_date = date.fromisoformat(item.get("fecha", ""))
        except (TypeError, ValueError):
            continue
        if not name or source not in {"enloteria", "lotteryusa"} or item_date != today_cuba:
            continue
        key = (name, item_date.isoformat(), source)
        merged[key] = item
    return list(merged.values())


def write_json_atomically(data):
    ARCHIVO_JSON.parent.mkdir(parents=True, exist_ok=True)
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
    now_cuba = datetime.now(TZ_CUBA)
    today_cuba = now_cuba.date()
    today_et = datetime.now(TZ_ESTE).date()
    print("=== INICIO SCRAPER ÚNICO (Playwright) ===")
    print(f"Fecha Cuba: {today_cuba} | Fecha Este: {today_et}")

    fresh = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )
        page = context.new_page()
        page.set_default_timeout(45_000)
        try:
            fresh.extend(scrape_principal(page))
            fresh.extend(scrape_especifica(page, URL_QUEMAITO, "El Quemaito Mayor"))
            fresh.extend(scrape_especifica(page, URL_QUINIELON, "El Quinielon Dia"))
            fresh.extend(scrape_lotteryusa(page))
        finally:
            context.close()
            browser.close()

    previous = leer_resultados_previos()
    final = fusionar_resultados(previous, fresh, today_cuba, today_et)
    if not final:
        raise RuntimeError("No se obtuvieron ni se pudieron conservar resultados válidos; JSON no reemplazado")
    write_json_atomically(final)
    print(f"✅ JSON actualizado: {len(final)} registros vigentes; {len(fresh)} registros recién extraídos")
    if not fresh:
        print("⚠️ Ninguna fuente entregó datos nuevos; se conservaron los resultados válidos anteriores")


if __name__ == "__main__":
    main()
