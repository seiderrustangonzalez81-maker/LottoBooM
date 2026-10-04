from pathlib import Path

p = Path("/home/LottoBooM/sorteos/fixtures/sorteos.json")
src = p.read_text(encoding="utf-8")

if "Loteka 1:30 PM" in src:
    print("SKIP: ya aplicado")
    raise SystemExit(0)

# 1. Cambiar nombre — 6 espacios de indentación
viejo_nombre = '"nombre": "Loteka 7:50 PM",'
nuevo_nombre = '"nombre": "Loteka 1:30 PM",'

if viejo_nombre not in src:
    print("ERROR: no encontré el nombre exacto")
    raise SystemExit(1)
src = src.replace(viejo_nombre, nuevo_nombre, 1)

# 2. Cambiar horarios — buscar el bloque específico de Loteka (18:50/19:50 en TODOS los días)
viejo_horarios = '"horarios": {"invierno": {"lunes": "18:50", "martes": "18:50", "miercoles": "18:50", "jueves": "18:50", "viernes": "18:50", "sabado": "18:50", "domingo": "18:50"}, "verano": {"lunes": "19:50", "martes": "19:50", "miercoles": "19:50", "jueves": "19:50", "viernes": "19:50", "sabado": "19:50", "domingo": "19:50"}},'

nuevo_horarios = '"horarios": {"invierno": {"lunes": "13:30", "martes": "13:30", "miercoles": "13:30", "jueves": "13:30", "viernes": "13:30", "sabado": "13:30", "domingo": "13:30"}, "verano": {"lunes": "13:30", "martes": "13:30", "miercoles": "13:30", "jueves": "13:30", "viernes": "13:30", "sabado": "13:30", "domingo": "13:30"}},'

# Este bloque aparece 2 veces (Loteka pk=42 y Tok 3 pk=43). Solo quiero el primero.
count = src.count(viejo_horarios)
print(f"Bloques idénticos encontrados: {count}")
if count == 0:
    print("ERROR: no encontré el bloque de horarios")
    raise SystemExit(1)

# Reemplazar solo el primero (que es Loteka, pk=42)
src = src.replace(viejo_horarios, nuevo_horarios, 1)

# 3. Validar JSON
import json
try:
    data = json.loads(src)
    print("OK: JSON válido")
except json.JSONDecodeError as e:
    print(f"ERROR: JSON inválido después del cambio: {e}")
    raise SystemExit(1)

# 4. Confirmar que el pk 42 tiene los nuevos valores
for item in data:
    if item.get("pk") == 42:
        print(f"  pk=42 · nombre='{item['fields']['nombre']}'")
        print(f"  horarios: {item['fields']['horarios']}")

p.write_text(src, encoding="utf-8")
print("OK: fixture actualizado")
