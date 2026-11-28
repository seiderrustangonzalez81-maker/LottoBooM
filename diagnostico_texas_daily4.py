from datetime import datetime, timedelta

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

import scraper


PRUEBAS = {
    "Texas 1:20 PM": "https://www.lotteryusa.com/texas/midday-4/",
    "Texas 10:12 PM": "https://www.lotteryusa.com/texas/daily-4/",
}


def comprobar_configuracion():
    print("\n===== CONFIGURACION =====")

    for nombre, url in PRUEBAS.items():
        juegos = scraper.URLS_MULTI.get(nombre, {})

        assert "pick3" in juegos, f"{nombre}: falta Pick 3"
        assert "pick4" in juegos, f"{nombre}: falta Pick 4"
        assert url in juegos["pick4"], f"{nombre}: URL Pick 4 incorrecta"

        print(f"OK {nombre}: Pick 3 conservado y Pick 4 configurado")


def comprobar_tarjeta(soup, nombre, fecha_esperada):
    tarjetas = soup.select("tr.c-draw-card")
    print("Tarjetas encontradas:", len(tarjetas))

    for tarjeta in tarjetas:
        fecha = scraper._extraer_fecha_lotteryusa(tarjeta, nombre)

        if fecha != fecha_esperada:
            continue

        numeros = scraper._extraer_numeros_lotteryusa(tarjeta)

        assert len(numeros) == 4, (
            f"{nombre}: se esperaban 4 bolas; encontradas: {numeros}"
        )
        assert all(n.isdigit() and len(n) == 1 for n in numeros), (
            f"{nombre}: bolas inválidas: {numeros}"
        )

        pick4 = "".join(numeros)
        corrido_1 = numeros[0] + numeros[1]
        corrido_2 = numeros[2] + numeros[3]

        print("Fecha:", fecha)
        print("Bolas:", numeros)
        print("Pick 4:", pick4)
        print("Corrido 1:", corrido_1)
        print("Corrido 2:", corrido_2)

        bonus = tarjeta.select("li.c-result__bonus li.c-ball")
        if bonus:
            print("Fireball separado:", [b.get_text(strip=True) for b in bonus])

        print(f"VALIDADO: {nombre}")
        return True

    fechas = [
        scraper._extraer_fecha_lotteryusa(t, nombre)
        for t in tarjetas
    ]
    print("Fecha esperada:", fecha_esperada)
    print("Fechas disponibles:", fechas)
    return False


def sorteo_puede_seguir_pendiente(nombre):
    zona = scraper.zona_horaria_sorteo_usa(nombre)
    hora = scraper.parsear_hora_sorteo(nombre)

    if not hora:
        return False

    ahora = datetime.now(zona)
    limite = ahora.replace(
        hour=hora[0],
        minute=hora[1],
        second=0,
        microsecond=0,
    ) + timedelta(minutes=30)

    return ahora < limite


def main():
    comprobar_configuracion()
    estados = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        try:
            page = browser.new_page()

            for nombre, url in PRUEBAS.items():
                print("\n" + "=" * 55)
                print("PRUEBA:", nombre)
                print("URL:", url)

                fecha_local, fecha_cuba = (
                    scraper.calcular_fechas_esperadas_usa(nombre)
                )

                print("Fecha LotteryUSA esperada:", fecha_local)
                print("Fecha operativa Cuba:", fecha_cuba)

                response = page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=60000,
                )

                assert response is not None, f"{nombre}: sin respuesta HTTP"
                assert response.status == 200, (
                    f"{nombre}: HTTP {response.status}"
                )

                print("HTTP:", response.status)
                print("Título:", page.title())

                page.wait_for_timeout(4000)

                soup = BeautifulSoup(page.content(), "html.parser")
                validado = comprobar_tarjeta(soup, nombre, fecha_local)

                if validado:
                    estados[nombre] = "VALIDADO"
                elif sorteo_puede_seguir_pendiente(nombre):
                    estados[nombre] = "PENDIENTE"
                    print("El sorteo todavía puede no estar publicado.")
                else:
                    raise AssertionError(
                        f"{nombre}: falta el resultado después del margen "
                        "de publicación."
                    )

        finally:
            browser.close()

    print("\n===== RESULTADO FINAL =====")
    for nombre, estado in estados.items():
        print(f"{nombre}: {estado}")

    if all(estado == "VALIDADO" for estado in estados.values()):
        print("AMBOS SORTEOS VALIDADOS.")
    elif any(estado == "VALIDADO" for estado in estados.values()):
        print("PRUEBA PARCIAL: queda al menos un sorteo pendiente.")
    else:
        print("NINGUN SORTEO VALIDADO.")


if __name__ == "__main__":
    main()
