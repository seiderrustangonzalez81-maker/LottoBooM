import json
import re
from datetime import datetime
import requests
from bs4 import BeautifulSoup

URL_CONECTATE = "https://www.conectate.com.do/loterias/pagina/ultimos-resultados"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
}

def extraer_picks(texto):
    nums = re.findall(r"\b\d{1,5}\b", texto)
    nums = [n for n in nums if not (len(n) == 4 and n.startswith("20"))]
    return nums

def scrape_conectate():
    print("Descargando Conectate...")
    resp = requests.get(URL_CONECTATE, headers=HEADERS, timeout=30)
    resp.raise_for_status()

    with open("debug_conectate.html", "w", encoding="utf-8") as f:
        f.write(resp.text)

    soup = BeautifulSoup(resp.text, "html.parser")
    resultados = []

    for tabla in soup.find_all("table"):
        caption = tabla.find("caption")
        encabezados = tabla.find_all("th")
        nombre = None
        if caption:
            nombre = caption.get_text(strip=True)
        elif encabezados:
            nombre = encabezados[0].get_text(strip=True)
        if not nombre:
            continue

        for fila in tabla.find_all("tr"):
            celdas = [c.get_text(" ", strip=True) for c in fila.find_all("td")]
            if not celdas:
                continue
            texto_fila = " ".join(celdas)
            nums = extraer_picks(texto_fila)
            if len(nums) < 2:
                continue

            picks = {"pick2": None, "pick3": None, "pick4": None, "pick5": None}
            for n in nums:
                if len(n) == 2 and not picks["pick2"]:
                    picks["pick2"] = n
                elif len(n) == 3 and not picks["pick3"]:
                    picks["pick3"] = n
                elif len(n) == 4 and not picks["pick4"]:
                    picks["pick4"] = n
                elif len(n) == 5 and not picks["pick5"]:
                    picks["pick5"] = n

            resultados.append({
                "sorteo_nombre": nombre,
                "fecha": datetime.now().strftime("%Y-%m-%d"),
                "hora": datetime.now().strftime("%H:%M:%S"),
                "pick2": picks["pick2"],
                "pick3": picks["pick3"],
                "pick4": picks["pick4"],
                "pick5": picks["pick5"],
                "fuente": "conectate",
            })

    print(f"Resultados extraidos: {len(resultados)}")
    return resultados

def main():
    todos = []
    try:
        todos.extend(scrape_conectate())
    except Exception as e:
        print(f"Error Conectate: {e}")

    with open("resultados.json", "w", encoding="utf-8") as f:
        json.dump(todos, f, ensure_ascii=False, indent=2)
    print(f"Guardados {len(todos)} en resultados.json")

if __name__ == "__main__":
    main()
