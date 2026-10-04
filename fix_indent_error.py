from pathlib import Path
import re

p = Path("/home/LottoBooM/jugadas/views.py")
src = p.read_text(encoding="utf-8")

# Buscar el bloque huérfano mal indentado
# El patrón es: 'es_modo_editar': es_modo_editar, seguido de 'es_modo_reenviar'
patron = re.compile(
    r"\n(\s*)'es_modo_editar':\s*es_modo_editar,\s*\n\s*'es_modo_reenviar':\s*es_modo_reenviar,",
    re.MULTILINE,
)

matches = list(patron.finditer(src))
print(f"Encontrados: {len(matches)} bloques huérfanos")

for m in reversed(matches):
    # Ver contexto previo
    antes = src[max(0, m.start()-100):m.start()]
    print(f"\nContexto antes:\n{repr(antes[-150:])}")
    # Ver contexto después
    despues = src[m.end():m.end()+100]
    print(f"Contexto después:\n{repr(despues[:150])}")
    # Eliminar el bloque huérfano
    src = src[:m.start()] + src[m.end():]
    print(f"  → Bloque eliminado en pos {m.start()}")

p.write_text(src, encoding="utf-8")

import ast
try:
    ast.parse(src)
    print("\n✅ Sintaxis CORREGIDA")
except SyntaxError as e:
    print(f"\n❌ Aún error: linea {e.lineno}: {e.msg}")
    print(f"   Contexto: {e.text}")
