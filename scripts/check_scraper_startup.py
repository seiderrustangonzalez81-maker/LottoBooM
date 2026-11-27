#!/usr/bin/env python3
"""Guardia estática para evitar leer dia_operativo antes de inicializarlo."""

import ast
from pathlib import Path

source = Path("scraper.py").read_text(encoding="utf-8")
module = ast.parse(source, filename="scraper.py")
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
