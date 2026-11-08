import os
import re
import requests

print("--- INICIANDO DIAGNÓSTICO DE LottoBooM ---")

# 1. Buscar la base de datos en settings.py
print("\n1. BUSCANDO BASE DE DATOS...")
if os.path.exists('settings.py'):
    with open('settings.py', 'r', encoding='utf-8') as f:
        contenido = f.read()
        db_info = re.search(r'DATABASES\s*=\s*{.*?}', contenido, re.DOTALL)
        if db_info:
            print("Base de datos encontrada:")
            print(db_info.group(0))
else:
    print("No encontré settings.py en esta carpeta. (Asegúrate de estar en la carpeta correcta).")

# 2. Buscar tus modelos en sorteos/models.py
print("\n2. BUSCANDO MODELOS Y CAMPOS...")
ruta_modelos = os.path.join('sorteos', 'models.py')
if os.path.exists(ruta_modelos):
    print(f"Revisando {ruta_modelos}:")
    with open(ruta_modelos, 'r', encoding='utf-8') as f:
        for linea in f:
            if 'class ' in linea or 'models.' in linea:
                print("   ", linea.strip())
else:
    print("No encontré sorteos/models.py")

# 3. Probar conexión a las páginas de loterías
print("\n3. PROBANDO CONEXIÓN A LAS WEBS...")
urls = {
    "Enloreria": "https://enloreria.com",
    "Conectate": "https://conectate.com.do"
}

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
for nombre, url in urls.items():
    try:
        respuesta = requests.get(url, headers=headers, timeout=10)
        print(f"   [OK] {nombre} responde con código: {respuesta.status_code} (Tamaño: {len(respuesta.text)} letras)")
    except Exception as e:
        print(f"   [ERROR] No se pudo conectar a {nombre}: {e}")

print("\n--- FIN DEL DIAGNÓSTICO ---")
