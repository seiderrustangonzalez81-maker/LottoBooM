from datetime import datetime
from playwright.sync_api import sync_playwright

URL_CONECTATE = "https://www.conectate.com.do/loterias/pagina/ultimos-resultados"

def main():
    print("🕵️ Entrando a Conectate para espiar qué muestra...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        try:
            page.goto(URL_CONECTATE, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(8000) # Esperar 8 segundos
            
            # Guardar el HTML (la foto de la página)
            html = page.content()
            with open("espiando_conectate.html", "w", encoding="utf-8") as f:
                f.write(html)
                
            # Guardar solo el texto visible (lo que vería un humano)
            texto = page.inner_text("body")
            with open("texto_conectate.txt", "w", encoding="utf-8") as f:
                f.write(texto)
                
            print("✅ Archivos guardados.")
        except Exception as e:
            print(f"❌ Error: {e}")
            
        browser.close()

if __name__ == "__main__":
    main()
