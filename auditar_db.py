import sqlite3

# Conectarse a la base de datos
conn = sqlite3.connect('/home/LottoBooM/db.sqlite3')
cursor = conn.cursor()

# Obtener todas las tablas
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tablas = cursor.fetchall()

print("=== AUDITORÍA DE TABLAS (Registros encontrados) ===")
for tabla in tablas:
    nombre = tabla[0]
    # Ignorar tablas internas de sqlite
    if nombre.startswith('sqlite_'):
        continue
    try:
        cursor.execute(f"SELECT count(*) FROM '{nombre}';")
        count = cursor.fetchone()[0]
        # Mostrar solo las tablas que nos interesan (finanzas, jugadas, usuarios)
        if any(x in nombre for x in ['rol', 'jugada', 'boleta', 'pago', 'fondo', 'bono', 'deuda', 'postpago', 'recarga', 'retiro', 'premio', 'user', 'perfil', 'cuadre']):
            print(f"{nombre:<40} | Registros: {count}")
    except Exception as e:
        print(f"Error en {nombre}: {e}")

conn.close()
