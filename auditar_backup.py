import sqlite3

conn = sqlite3.connect('backups/db_2026-11-07_0446_FINAL.db')
cursor = conn.cursor()

cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tablas = cursor.fetchall()

print("=== AUDITORÍA DEL BACKUP FINAL ===")
for tabla in tablas:
    nombre = tabla[0]
    if nombre.startswith('sqlite_'):
        continue
    try:
        cursor.execute(f"SELECT count(*) FROM '{nombre}';")
        count = cursor.fetchone()[0]
        if any(x in nombre for x in ['rol', 'jugada', 'boleta', 'pago', 'fondo', 'bono', 'deuda', 'postpago', 'recarga', 'retiro', 'premio', 'user', 'perfil', 'cuadre', 'transferencia', 'ajuste']):
            print(f"{nombre:<40} | Registros: {count}")
    except Exception as e:
        pass

conn.close()
