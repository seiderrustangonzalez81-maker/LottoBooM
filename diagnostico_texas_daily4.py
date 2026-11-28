from playwright.sync_api import sync_playwright

URL = "https://www.lotteryusa.com/texas/daily-4/"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    try:
        response = page.goto(
            URL,
            wait_until="domcontentloaded",
            timeout=60000,
        )
        print("HTTP:", response.status if response else "Sin respuesta")
        print("TITULO:", page.title())

        page.wait_for_timeout(5000)

        print("\n===== ENLACES DE NAVEGACION =====")
        enlaces = page.locator("a")
        for i in range(enlaces.count()):
            enlace = enlaces.nth(i)
            texto = enlace.inner_text().strip()
            href = enlace.get_attribute("href") or ""
            if any(x in (texto + " " + href).lower()
                   for x in ("day", "night", "morning", "evening")):
                print("TEXTO:", texto, "| HREF:", href)

        tarjetas = page.locator("tr.c-draw-card")
        total = tarjetas.count()
        print("\nTARJETAS COMPLETAS:", total)

        for i in range(total):
            tarjeta = tarjetas.nth(i)
            print("\n========== TARJETA", i + 1, "==========")
            print("CLASE:", tarjeta.get_attribute("class"))
            print("TEXTO:", tarjeta.inner_text().strip())

            fechas = tarjeta.locator("time")
            for j in range(fechas.count()):
                print("FECHA HTML:", fechas.nth(j).evaluate(
                    "(e) => e.outerHTML"
                ))

            listas = tarjeta.locator(
                "ul.c-result.c-draw-card__ball-list"
            )
            for j in range(listas.count()):
                lista = listas.nth(j)
                print("LISTA DE BOLAS HTML:", lista.evaluate(
                    "(e) => e.outerHTML"
                ))
                bolas = lista.locator(":scope > li.c-ball")
                print("BOLAS:", [
                    bolas.nth(k).inner_text().strip()
                    for k in range(bolas.count())
                ])
    finally:
        browser.close()
