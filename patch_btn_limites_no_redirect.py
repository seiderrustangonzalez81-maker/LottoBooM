from pathlib import Path

p = Path("/home/LottoBooM/jugadas/templates/jugadas/apostar.html")
src = p.read_text(encoding="utf-8")

# Añadir preventDefault/stopPropagation al handler del botón límites
viejo = """  // ═══ BOTON LIMITES ═══
  document.addEventListener('click', function(e){
    var btn = e.target.closest && e.target.closest('#lottortLimitesBtn');
    if (!btn) return;
    if (!cliente || !ordenSorteos.length) return;"""

nuevo = """  // ═══ BOTON LIMITES ═══
  document.addEventListener('click', function(e){
    var btn = e.target.closest && e.target.closest('#lottortLimitesBtn');
    if (!btn) return;
    // ═══ GARANTIZAR QUE NO HAYA REDIRECT ═══
    e.preventDefault();
    e.stopPropagation();
    e.stopImmediatePropagation();
    // ═══ MANTENER EL FOCO EN LA PAGINA (no sacar al usuario) ═══
    if (!cliente || !ordenSorteos.length){
      if (typeof toast === 'function') toast('Selecciona cliente y un sorteo primero', 'warning');
      return;
    }"""

if "e.stopImmediatePropagation()" in src and "lottortLimitesBtn" in src:
    print("SKIP: ya aplicado")
elif viejo in src:
    src = src.replace(viejo, nuevo, 1)
    print("OK: preventDefault + stopPropagation añadidos al botón límites")
else:
    # Buscar variante
    import re
    patron = re.compile(
        r"(\s+// ═+ BOTON LIMITES ═+\s*\n\s+document\.addEventListener\('click', function\(e\)\{\s*\n\s+var btn = e\.target\.closest && e\.target\.closest\('#lottortLimitesBtn'\);\s*\n\s+if \(!btn\) return;)",
        re.MULTILINE,
    )
    m = patron.search(src)
    if m:
        # Insertar después del `if (!btn) return;`
        insert_after = m.end()
        src = src[:insert_after] + """
    // ═══ GARANTIZAR QUE NO HAYA REDIRECT ═══
    e.preventDefault();
    e.stopPropagation();
    e.stopImmediatePropagation();""" + src[insert_after:]
        print("OK: aplicado via regex")
    else:
        print("ERROR: no encontre el bloque del botón límites")
        print("Corre: grep -n 'BOTON LIMITES' -A 5 jugadas/templates/jugadas/apostar.html")

p.write_text(src, encoding="utf-8")

# Verificar
ok1 = "e.stopImmediatePropagation()" in src
print("")
print("--- VERIFICACION ---")
print("stopImmediatePropagation:", "OK" if ok1 else "NO")
print("lottortLimitesBtn:", src.count('lottortLimitesBtn'))
