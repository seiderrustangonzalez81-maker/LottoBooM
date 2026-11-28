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

        tarjetas = page.locator('[class*="draw-card"]')
        total = tarjetas.count()
        print("TARJETAS ENCONTRADAS:", total)

        for i in range(total):
            tarjeta = tarjetas.nth(i)
            print("\n========== TARJETA", i + 1, "==========")
            print("TAG:", tarjeta.evaluate("(e) => e.tagName"))
            print("CLASE:", tarjeta.get_attribute("class"))
            print("TEXTO:", tarjeta.inner_text().strip())

            fechas = tarjeta.locator("time")
            for j in range(fechas.count()):
                print("FECHA HTML:", fechas.nth(j).evaluate(
                    "(e) => e.outerHTML"
                ))

            bolas = tarjeta.locator(
                "li.c-ball, li.c-result__ball, .c-ball, .ball"
            )
            print("NUMEROS:", [
                bolas.nth(j).inner_text().strip()
                for j in range(bolas.count())
            ])
    finally:
        browser.close()
