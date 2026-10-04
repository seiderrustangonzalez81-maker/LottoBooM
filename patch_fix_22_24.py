from pathlib import Path
import re

p = Path("/home/LottoBooM/jugadas/templates/jugadas/apostar.html")
src = p.read_text(encoding="utf-8")

# ═══════════════════════════════════════════════════════════════
# FIX 2.2 — Bypass recalcGlobal con regex flexible
# ═══════════════════════════════════════════════════════════════
# Buscar "let ok = cliente && ordenSorteos.length > 0 && items.length > 0;"
patron_ok = re.compile(
    r"(\s+)(let ok = cliente && ordenSorteos\.length > 0 && items\.length > 0;)",
)

m = patron_ok.search(src)
if not m:
    print("ERROR 2.2: no encontre 'let ok = cliente...'")
else:
    indent = m.group(1)
    linea_ok = m.group(2)
    # Ver si ya está parcheado
    siguiente = src[m.end():m.end()+200]
    if "ES_SOLO_EDITAR" in siguiente[:150]:
        print("SKIP 2.2: ya parcheado")
    else:
        # Buscar el próximo "if (ok){" y reemplazarlo por "if (ok && ES_SOLO_EDITAR){} else if (ok){"
        patron_if = re.compile(r"(\s+)if \(ok\)\{", re.MULTILINE)
        if patron_if.search(src[m.end():m.end()+500]):
            def fix_if(mm):
                ind = mm.group(1)
                return f"{ind}if (ok && ES_SOLO_EDITAR){{\n{ind}  // modo editar: no cobra\n{ind}}} else if (ok){{"
            # Aplicar solo al siguiente if(ok) después de la línea let ok
            pos_if = patron_if.search(src, m.end())
            if pos_if:
                src = src[:pos_if.start()] + f"{indent}if (ok && ES_SOLO_EDITAR){{\n{indent}  // modo editar: no cobra\n{indent}}} else if (ok){{" + src[pos_if.end():]
                print("OK 2.2: bypass aplicado")
            else:
                print("ERROR 2.2: no encontre 'if (ok){' después")
        else:
            print("ERROR 2.2: no encontre 'if (ok){' cerca")

# Guardar
p.write_text(src, encoding="utf-8")

# ═══════════════════════════════════════════════════════════════
# FIX 2.4 — Cliente dinámico con regex flexible
# ═══════════════════════════════════════════════════════════════
# Buscar la línea "selCli.value = String(data.cliente_id);"
patron_selcli = re.compile(
    r"(\s+)(selCli\.value = String\(data\.cliente_id\);\s*\n\s+selCli\.dispatchEvent\(new Event\('change'\)\);)",
)

m2 = patron_selcli.search(src)
if not m2:
    print("ERROR 2.4: no encontre 'selCli.value = String(data.cliente_id)'")
else:
    # Ver si ya está parcheado
    antes = src[max(0, m2.start()-300):m2.start()]
    if "no en dropdown" in antes or "_existeCli" in antes:
        print("SKIP 2.4: ya parcheado")
    else:
        indent = m2.group(1)
        bloque_nuevo = f"""{indent}var _existeCli = false;
{indent}for (var _i = 0; _i < selCli.options.length; _i++){{
{indent}  if (String(selCli.options[_i].value) === String(data.cliente_id)){{
{indent}    _existeCli = true; break;
{indent}  }}
{indent}}}
{indent}if (!_existeCli){{
{indent}  console.log('[apostar] Cliente ' + data.cliente_id + ' no en dropdown, añadiendo...');
{indent}  var _opt = document.createElement('option');
{indent}  _opt.value = String(data.cliente_id);
{indent}  _opt.textContent = (data.cliente_nombre || 'Cliente') + ' (edit)';
{indent}  _opt.dataset.nombre = data.cliente_nombre || 'Cliente';
{indent}  _opt.dataset.telefono = '';
{indent}  _opt.dataset.saldo = '0';
{indent}  _opt.dataset.bonos = '0';
{indent}  _opt.dataset.rol = 'cliente';
{indent}  selCli.appendChild(_opt);
{indent}}}
{indent}{m2.group(2)}"""
        src = src[:m2.start()] + bloque_nuevo + src[m2.end():]
        print("OK 2.4: cliente dinámico aplicado")

p.write_text(src, encoding="utf-8")

# Reporte final
print(f"\nES_SOLO_EDITAR: {src.count('ES_SOLO_EDITAR')}")
print(f"_existeCli: {src.count('_existeCli')}")
