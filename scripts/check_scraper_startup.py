#!/usr/bin/env python3
"""Guardias estáticas del scraper y del catálogo importado por el cargador."""

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

source = ROOT / "scraper.py"
module = ast.parse(source.read_text(encoding="utf-8"), filename="scraper.py")
main = next(
    (node for node in module.body
     if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
     and node.name == "main"),
    None,
)
if main is None:
    raise SystemExit("ERROR: no se encontró main() en scraper.py")

assignment_index = next(
    (
        index
        for index, statement in enumerate(main.body)
        if isinstance(statement, (ast.Assign, ast.AnnAssign))
        and any(
            isinstance(target, ast.Name) and target.id == "dia_operativo"
            for target in (
                statement.targets if isinstance(statement, ast.Assign)
                else [statement.target]
            )
        )
    ),
    None,
)

read_indices = [
    index
    for index, statement in enumerate(main.body)
    if any(
        isinstance(node, ast.Name)
        and node.id == "dia_operativo"
        and isinstance(node.ctx, ast.Load)
        for node in ast.walk(statement)
    )
]

if assignment_index is None:
    raise SystemExit("ERROR: dia_operativo no se inicializa directamente en main()")
if not read_indices:
    raise SystemExit("ERROR: no se encontró ninguna lectura de dia_operativo en main()")
if assignment_index >= min(read_indices):
    raise SystemExit(
        "ERROR: dia_operativo se lee antes de inicializarse en main()"
    )

print("OK: dia_operativo se inicializa antes de su primera lectura en main().")

# El cargador de la matriz importa este módulo antes de acceder a Django/DB.
# Validamos aquí el import y la estructura sin ejecutar el cargador destructivo.
try:
    from sorteos.constants import MATRIZ
except Exception as exc:
    raise SystemExit(f"ERROR: no se pudo importar sorteos.constants.MATRIZ: {exc}") from exc

if not isinstance(MATRIZ, dict) or not MATRIZ:
    raise SystemExit("ERROR: MATRIZ debe ser un diccionario no vacío")

if any(
    not isinstance(nombre, str)
    or not isinstance(formas, list)
    or any(not isinstance(forma, str) for forma in formas)
    for nombre, formas in MATRIZ.items()
):
    raise SystemExit("ERROR: MATRIZ debe mapear nombres de sorteos a listas de formas")

print(f"OK: MATRIZ importada y validada ({len(MATRIZ)} sorteos).")
