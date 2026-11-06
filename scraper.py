import json
import re
from datetime import datetime
from playwright.sync_api import sync_playwright

URL_CONECTATE = "https://www.conectate.com.do/loterias/pagina/ultimos-resultados"

def main():
    resultados = []
    print("🔍 Iniciando búsqueda SOLO de Anguila en Conectate...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        try:
            page.goto(URL_CONECTATE, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(8000) # Esperar a que carguen los números
            
            # Buscamos todas las filas de la tabla
            filas = page.locator("tr").all()
            for fila in filas:
                try:
                    texto = fila.inner_text().strip()
                    # Si la fila menciona Anguila
                    if "Anguila" in texto:
                        lineas = [l.strip() for l in texto.split("\n") if l.strip()]
                        nombre = lineas[0] # Ej: "Anguila 8 AM"
                        
                        # Buscamos los códigos (Ej: F41, C184, C247) o números puros
                        # Esta regex captura 1 letra seguida de números, o números solos de 1 a 3 dígitos
                        nums = re.findall(r'[A-Z]\d{1,3}|\b\d{1,3}\b', texto)
                        
                        # Filtramos la fecha (que suele tener 4 dígitos o barras) y la hora
                        nums_limpios = [n for n in nums if not (len(n) == 4 and n.startswith("20")) and ":" not in n]
                        
                        # Si encontramos al menos 3 resultados (Fijo, Corrida 1, Corrida 2)
                        if len(nums_limpios) >= 3:
                            resultados.append({
                                "sorteo_nombre": nombre,
                                "numeros": nums_limpios[-3:], # Tomamos los últimos 3
                                "fecha": datetime.now().strftime("%Y-%m-%d"),
                                "fuente": "conectate"
                            })
                except Exception as e:
                    pass # Ignorar filas vacías o con error
                    
        except Exception as e:
            print(f"❌ Error: {e}")
            
        browser.close()

    # Guardar el archivo
    with open("resultados.json", "w", encoding="utf-8") as f:
        json.dump(resultados, f, ensure_ascii=False, indent=2)
        
    print(f"💾 Guardados {len(resultados)} resultados de Anguila.")

if __name__ == "__main__":
    main()
