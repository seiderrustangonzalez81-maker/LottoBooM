from pathlib import Path
import os, django, json

# ─── Setup Django ───
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "LottoBooM.settings")
django.setup()

from sorteos.models import Sorteo

CAMBIOS = {
    "Real Noche":      {"domingo": "20:00"},
    "Loteka 1:30 PM":  {"domingo": "19:50"},
}

print("════════════ 1. BD ════════════")
for nombre, cambios in CAMBIOS.items():
    s = Sorteo.objects.filter(nombre=nombre).first()
    if not s:
        print(f"  ⚠️  No encontré '{nombre}'")
        continue

    horarios = dict(s.horarios or {})
    for temporada in ("invierno", "verano"):
        if temporada not in horarios:
            continue
        for dia, hora in cambios.items():
            horarios[temporada][dia] = hora
    s.horarios = horarios
    s.save(update_fields=['horarios'])
    print(f"  ✅ {nombre}:")
    for temporada in ("invierno", "verano"):
        print(f"      {temporada}.domingo = {horarios[temporada]['domingo']}")

# ══════════════════════════════════════════════════════════════════
print("\n════════════ 2. FIXTURE ════════════")
fixture_path = Path("/home/LottoBooM/sorteos/fixtures/sorteos.json")
if not fixture_path.exists():
    print("  SKIP: no existe fixture")
else:
    data = json.loads(fixture_path.read_text(encoding="utf-8"))
    cambios_aplicados = 0
    for item in data:
        if item.get("model") != "sorteos.sorteo":
            continue
        nombre = item["fields"].get("nombre", "")
        if nombre not in CAMBIOS:
            continue
        horarios = item["fields"].get("horarios", {})
        for temporada in ("invierno", "verano"):
            if temporada not in horarios:
                continue
            for dia, hora in CAMBIOS[nombre].items():
                horarios[temporada][dia] = hora
        item["fields"]["horarios"] = horarios
        print(f"  ✅ {nombre} (pk={item['pk']}) actualizado")
        cambios_aplicados += 1

    if cambios_aplicados:
        fixture_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        print(f"  Fixture guardado con {cambios_aplicados} cambio(s)")
    else:
        print("  Sin cambios en el fixture")

print("\n✅ Listo")
