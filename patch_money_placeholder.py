from pathlib import Path

# Archivos a patchear
FILES = [
    "/home/LottoBooM/roles/templates/roles/recarga_directa.html",
    "/home/LottoBooM/roles/templates/roles/cuadre_diario.html",
    "/home/LottoBooM/roles/templates/roles/solicitar.html",
    "/home/LottoBooM/jugadas/templates/jugadas/superparlet.html",
    "/home/LottoBooM/usuarios/templates/usuarios/solicitar_retiro.html",
    "/home/LottoBooM/templates/roles/recarga_directa.html",
    "/home/LottoBooM/templates/roles/solicitar.html",
    "/home/LottoBooM/templates/roles/solicitar_retiro.html",
]

total = 0
for path in FILES:
    p = Path(path)
    if not p.exists():
        print(f"  SKIP {path} (no existe)")
        continue

    src = p.read_text(encoding="utf-8")
    original = src

    # Cambiar placeholder="0.00" y "0,00" → "0"
    src = src.replace('placeholder="0.00"', 'placeholder="0"')
    src = src.replace('placeholder="0,00"', 'placeholder="0"')
    # Cambiar value="0.00" → value="0"
    src = src.replace('value="0.00"', 'value="0"')
    src = src.replace('value="0,00"', 'value="0"')

    if src != original:
        p.write_text(src, encoding="utf-8")
        n = original.count('placeholder="0.00"') + original.count('placeholder="0,00"') + original.count('value="0.00"')
        total += n
        print(f"  OK {path}: {n} cambio(s)")
    else:
        print(f"  SKIP {path}: sin cambios")

print()
print(f"Total cambios: {total}")
